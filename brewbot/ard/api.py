import os

from flask import Blueprint, request, Response, current_app
from brewbot.ard.ard_remote import ArduinoRemote, PIN_DIGITAL, PIN_ANALOG, PIN_OUTPUT, PIN_INPUT, HIGH, LOW
from brewbot.util import validate_int, list_files_with_prefix, _ConfMeta
from serial.serialutil import SerialException
import time

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

    port = "/".join(path_parts[:-1])
    baudrate = path_parts[-1]

    valid_prefixes = list_files_with_prefix(Conf.valid_port_prefixes)
    if port not in valid_prefixes:
        raise ValueError(f"post must have one of prefixes {port_prefixes} got {port}")

    return port, validate_int(baudrate, valid_interval=(9600, 115200), varname='baudrate')


def parse_arduino_remote_args(args):
    pin_config = args.get('pins', default='')
    in_buf_size = args.get('buf', default='128')
    heartbeat_rate = args.get('heartbeat', default='100')
    read_interval = args.get('readinterval', default='5')
    min_read_sleep = args.get('minreadsleep', default='1')
    read_serial_timeout = args.get('readserialtimeout', default='100')

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

    pin_mode = pin_config[1::3]
    d = {'in': PIN_INPUT,
         'out': PIN_OUTPUT}

    for pm in pin_mode:
        if pm not in d:
            raise ValueError(f"pin mode has to be one of {list(d.keys())} not {pm}")

    pin_mode = [d[pm] for pm in pin_mode]

    d = {'a': PIN_ANALOG,
         'd': PIN_DIGITAL}

    anadigi = pin_config[2::3]
    for ad in anadigi:
        if ad not in d:
            raise ValueError(f"anadigi has to be one of {list(d.keys())} not {ad}")

    anadigi = [d[ad] for ad in anadigi]

    pin_config = {p: (m, a) for p, m, a in zip(pins, pin_mode, anadigi)}

    return {'pin_config': pin_config, 'session': None, 'in_buf_size': in_buf_size, 'heartbeat_rate': heartbeat_rate,
            'read_interval': read_interval, 'min_read_sleep': min_read_sleep,
            'read_serial_timeout': read_serial_timeout}


def arduino_remote_vars(ard):
    return {'port': ard.port, 'baudrate': ard.baudrate, 'pin_config': ard.pin_config,
            'in_buf_size': ard.in_buf_size, 'heartbeat_rate': ard.heartbeat_rate,
            'read_interval': ard.read_interval, 'min_read_sleep': ard.min_read_sleep,
            'read_serial_timeout': ard.read_serial_timeout}


@api.route('/<path:path>/new')
def new(path):
    try:
        port, baudrate = parse_path(path)
        ard_kwargs = {**{'port': port, 'baudrate': baudrate}, **parse_arduino_remote_args(request.args)}
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if any([p == port for p, _ in arduino_remotes.keys()]):
        return {'status': 'fail', 'msg': 'port already in use'}, 400

    try:
        ard = ArduinoRemote(**ard_kwargs)
        ard.reset_remote()
        if any([c[0] == PIN_INPUT for c in ard.pin_config.values()]):
            ard.start_read_thread()

        arduino_remotes[(port, baudrate)] = ard
        return {'status': 'success', 'session': ard.session}, 200
    except (ValueError, SerialException) as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/shutdown')
def shutdown(path):
    try:
        port, baudrate = parse_path(path)
        ignore_not_exists = 'ignore-not-exists' in request.args
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if (port, baudrate) not in arduino_remotes:
        if ignore_not_exists:
            return {'status': 'success'}, 200
        else:
            return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[(port, baudrate)]

    try:
        ard.stop_remote()
        del arduino_remotes[(port, baudrate)]
        return {'status': 'success'}, 200
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400


@api.route('/<path:path>/pin/<pin>/<value>')
def set_pin(path, pin, value):
    try:
        port, baudrate = parse_path(path)
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if (port, baudrate) not in arduino_remotes:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[(port, baudrate)]

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
        port, baudrate = parse_path(path)
        stream = 'stream' in request.args
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if (port, baudrate) not in arduino_remotes:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400
    else:
        ard = arduino_remotes[(port, baudrate)]

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


# @api.route('/<path:path>/status')
def _status(path):
    try:
        port, baudrate = parse_path(path)
    except ValueError as ex:
        return {'status': 'fail', 'msg': str(ex)}, 400

    if (port, baudrate) in arduino_remotes:
        ard_status = arduino_remote_vars(arduino_remotes[(port, baudrate)])
        dm = {PIN_INPUT: 'in', PIN_OUTPUT: 'out'}
        da = {PIN_ANALOG: 'analog', PIN_DIGITAL: 'digital'}
        ard_status['pin_config'] = {k: {'mode': dm.get(m, m), 'ad': da.get(a, a)}
                                    for k, (m, a) in ard_status['pin_config'].items()}

        return {'status': 'success', 'remote': ard_status}, 200
    else:
        return {'status': 'fail', 'msg': 'remote not registered'}, 400


@api.route('/list-remotes')
def list_remotes():
    ard_status = [{
        'port': '/dev/abc', 'baudrate': 1000, 'pin_config': {'7': {'mode': 'in', 'ad': 'd'},
                                                             'a0': {'mode': 'out', 'ad': 'a'}},
        'in_buf_size': 128, 'heartbeat_rate': 0.01, 'read_interval': 0.05, 'min_read_sleep': 0.001,
        'read_serial_timeout': 0.1}, {
        'port': '/dev/xyz', 'baudrate': 2000, 'pin_config': {'8': {'mode': 'in', 'ad': 'd'},
                                                             'a1': {'mode': 'out', 'ad': 'a'}},
        'in_buf_size': 128, 'heartbeat_rate': 0.01, 'read_interval': 0.05, 'min_read_sleep': 0.001,
        'read_serial_timeout': 0.1}]

    return ard_status


# @api.route('/list-remotes')
# def list_remotes():
#     return {'status': 'success', 'remotes': [arduino_remote_vars(ard) for ard in arduino_remotes.values()]}, 200


@api.route('/list-ports')
def list_ports():
    # return {'status': 'success', 'ports': list_files_with_prefix(Conf.valid_port_prefixes)}, 200
    return {'status': 'success', 'ports': ['a', 'b', 'c']}, 200
