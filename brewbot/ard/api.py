import os

from flask import Blueprint, request, Response, current_app
from brewbot.ard.ard_remote import PIN_DIGITAL, PIN_ANALOG, PIN_OUTPUT, PIN_INPUT, HIGH, LOW
from brewbot.util import validate_int, _ConfMeta
from serial.serialutil import SerialException
import time

# set environment variable "MOCK" to "1" to use implementations from `mock` package.
if "MOCK" in os.environ and os.environ["MOCK"] == '1':
    # Mock of `ArduinoRemote` will never attempt to access the serial port. All functions interacting with the serial
    # port will `pass` and/or return an empty result
    from brewbot.mock.ard.ard_remote import ArduinoRemote

    # Mock of `list_files_with_prefix` will return a list of files with that prefix adding a set list of suffixes
    from brewbot.mock.util import list_files_with_prefix
else:
    from brewbot.ard.ard_remote import ArduinoRemote
    from brewbot.util import list_files_with_prefix


api = Blueprint('api', __name__)


class __ConfMeta(_ConfMeta):
    def conf_dict(cls):
        return current_app.config

    @property
    def valid_port_prefixes(cls):
        return cls.get("VALID_PORT_PREFIXES", default=[])


class Conf(metaclass=__ConfMeta):
    pass


arduino_remotes = {}

_pin_mode_dict = {
    PIN_INPUT: 'in',
    PIN_OUTPUT: 'out'}

_pin_ad_dict = {
    PIN_ANALOG: 'a',
    PIN_DIGITAL: 'd'
}

def pin_mode_to_str(pin_mode: int) -> str:
    if pin_mode not in _pin_mode_dict:
        raise ValueError(f"pin mode has to be one of {list(_pin_mode_dict.keys())} not {pin_mode}")

    return _pin_mode_dict[pin_mode]

def pin_mode_from_str(pin_mode: str) -> int:
    r_dict = {v: k for k, v in _pin_mode_dict.items()}

    if pin_mode not in r_dict:
        raise ValueError(f"pin mode has to be one of {list(r_dict.keys())} not {pin_mode}")

    return r_dict[pin_mode]

def pin_ad_to_str(pin_ad: int) -> str:
    if pin_ad not in _pin_ad_dict:
        raise ValueError(f"pin ad has to be one of {list(_pin_ad_dict.keys())} not {pin_ad}")

    return _pin_ad_dict[pin_ad]

def pin_ad_from_str(pin_ad: str) -> int:
    r_dict = {v: k for k, v in _pin_ad_dict.items()}

    if pin_ad not in r_dict:
        raise ValueError(f"pin ad has to be one of {list(r_dict.keys())} not {pin_ad}")

    return r_dict[pin_ad]


def parse_path(path, port_prefixes=None):
    if len(path) == 0:
        raise ValueError('path is empty')

    if path[0] != '/':
        path = "/" + path

    if port_prefixes is None:
        port_prefixes = Conf.valid_port_prefixes

    if not isinstance(port_prefixes, list):
        port_prefixes = [port_prefixes]

    path_parts = os.path.abspath(path).split('/')
    if len(path_parts) < 2:
        raise ValueError('path is too short')

    port = "/".join(path_parts)

    valid_ports = list_files_with_prefix(Conf.valid_port_prefixes)
    if port not in valid_ports:
        raise ValueError(f"post must have one of prefixes {port_prefixes} got {port}")

    return port


def parse_arduino_remote_args(args):
    baudrate = args.get('baudrate', default='115200')
    pin_config = args.get('pins', default='')
    in_buf_size = args.get('buf', default='128')
    heartbeat_rate = args.get('heartbeat', default='100')
    read_interval = args.get('readinterval', default='5')
    min_read_sleep = args.get('minreadsleep', default='1')
    read_serial_timeout = args.get('readserialtimeout', default='100')

    baudrate = validate_int(baudrate, varname='baudrate')
    in_buf_size = validate_int(in_buf_size, valid_interval=(2**6, 2**12), varname='buf')
    heartbeat_rate = validate_int(heartbeat_rate, valid_interval=(1, None), varname='heartbeat') / 1000
    read_interval = validate_int(read_interval, valid_interval=(1, None), varname='readinterval') / 1000
    min_read_sleep = validate_int(min_read_sleep, valid_interval=(1, None), varname='minreadsleep') / 1000
    read_serial_timeout = validate_int(read_serial_timeout, valid_interval=(1, None),
                                       varname='readserialtimeout') / 1000

    pin_config = pin_config.split(',')
    pin_config = [p for p in pin_config if p is not None and len(p) != 0]

    if len(pin_config) % 3 != 0:
        raise ValueError("pin config parameters must be a multiple of 3")

    pins = [p.strip().lower() for p in pin_config[0::3]]
    for p in pins:
        if not ArduinoRemote.is_valid_pin(p):
            raise ValueError(f"invalid pin format: {p}")

    pin_mode = [pin_mode_from_str(pm) for pm in pin_config[1::3]]
    anadigi = [pin_ad_from_str(ad) for ad in pin_config[2::3]]
    pin_config = {p: (m, a) for p, m, a in zip(pins, pin_mode, anadigi)}

    return {'baudrate': baudrate, 'pin_config': pin_config, 'session': None, 'in_buf_size': in_buf_size,
            'heartbeat_rate': heartbeat_rate, 'read_interval': read_interval, 'min_read_sleep': min_read_sleep,
            'read_serial_timeout': read_serial_timeout}


def arduino_remote_vars(ard):
    pin_config = {pin: {'mode': pin_mode_to_str(m), 'ad': pin_ad_to_str(ad)} for pin, (m, ad) in ard.pin_config.items()}

    return {'port': ard.port, 'baudrate': ard.baudrate, 'pin_config': pin_config,
            'in_buf_size': ard.in_buf_size, 'heartbeat_rate': ard.heartbeat_rate,
            'read_interval': ard.read_interval, 'min_read_sleep': ard.min_read_sleep,
            'read_serial_timeout': ard.read_serial_timeout}


@api.route('/<path:path>/new')
def new(path):
    try:
        port = parse_path(path)
        ard_kwargs = {**{'port': port}, **parse_arduino_remote_args(request.args)}
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if any([p == port for p in arduino_remotes.keys()]):
        return {'status': 'fail', 'msg': 'port already in use'}, 400

    try:
        ard = ArduinoRemote(**ard_kwargs)
        ard.reset_remote()
        if any([c[0] == PIN_INPUT for c in ard.pin_config.values()]):
            ard.start_read_thread()

        arduino_remotes[port] = ard
        session = ard.session
        return {'status': 'success', 'session': session}, 200
    except (ValueError, SerialException) as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/shutdown')
def shutdown(path):
    try:
        port = parse_path(path)
        ignore_not_exists = 'ignore-not-exists' in request.args
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if port not in arduino_remotes:
        if ignore_not_exists:
            return {'status': 'success'}, 200
        else:
            return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[port]

    try:
        ard.stop_remote()
        del arduino_remotes[port]
        return {'status': 'success'}, 200
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/pin/<pin>/<value>')
def set_pin(path, pin, value):
    try:
        port = parse_path(path)
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if port not in arduino_remotes:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[port]

    if not ArduinoRemote.is_valid_pin(pin):
        return {'status': 'fail', 'msg': 'invalid pin format'}, 400

    if pin not in ard.pin_config or ard.pin_config[pin][0] != PIN_OUTPUT:
        return {'status': 'fail', 'msg': 'pin is not configured as an output pin'}, 400

    d = {'high': HIGH, 'low': LOW}
    if value in d:
        value = d[value]
    else:
        try:
            value = int(value)
        except ValueError:
            value = None

    if not (value is not None or isinstance(value, str) or (not isinstance(value, int) or 0 <= value < 2**10)):
        return {'status': 'fail', 'msg': 'invalid value'}, 400

    try:
        ard.set_pin(pin, value)
        return {'status': 'success'}, 200
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/pin/<pin>')
def get_pin(path, pin):
    try:
        port = parse_path(path)
        stream = 'stream' in request.args
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if port not in arduino_remotes:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[port]

    if not ArduinoRemote.is_valid_pin(pin):
        return {'status': 'fail', 'msg': 'invalid pin format'}, 400

    if pin not in ard.pin_config:
        return {'status': 'fail', 'msg': 'pin is not configured'}, 400

    if stream:
        def generate():
            while True:
                yield "a,b,c\n"
                time.sleep(0.5)

        return Response(response=generate(), mimetype='text/csv')
    else:
        try:
            pin_value = ard.pin_values.get(pin, None)
            return {'status': 'success', 'pin': pin, 'value': pin_value}, 200
        except ValueError as ex:
            return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/status')
def _status(path):
    try:
        port = parse_path(path)
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if port in arduino_remotes:
        ard_status = arduino_remote_vars(arduino_remotes[port])
        dm = {PIN_INPUT: 'in', PIN_OUTPUT: 'out'}
        da = {PIN_ANALOG: 'analog', PIN_DIGITAL: 'digital'}
        ard_status['pin_config'] = {k: {'mode': dm.get(m, m), 'ad': da.get(a, a)}
                                    for k, (m, a) in ard_status['pin_config'].items()}

        return {'status': 'success', 'remote': ard_status}, 200
    else:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400


@api.route('/list-remotes')
def list_remotes():
    return {'status': 'success', 'remotes': {ard.port: arduino_remote_vars(ard) for ard in arduino_remotes.values()}}, 200


@api.route('/list-ports')
def list_ports():
    return {'status': 'success', 'ports': list_files_with_prefix(Conf.valid_port_prefixes)}, 200
