import serial
from threading import Thread
from typing import Optional, Union
from string import digits
import time
import random
import sys
from brewbot.ard import msg_types, Buffer, MsgText, MsgBufDump, MsgAnalogOffset, MsgFail, MsgAwaitConfig, MsgSetState, \
    MsgConfigGetAnalogOffset, MsgConfigSession, MsgConfigPinmode, MsgConfigFinalize, MsgRead, MsgHeartbeat, MsgWrite
from contextlib import contextmanager

STATE_IDLE = 0xF0
STATE_INIT_CONFIG = 0xF1
STATE_CONFIG = 0xF2
STATE_INIT_MAIN = 0xF3
STATE_MAIN = 0xF4
STATE_FAIL = 0xF5

PIN_DIGITAL = 0x0
PIN_ANALOG = 0x1
PIN_INPUT = 0x0
PIN_OUTPUT = 0x1

SUPER_SESSION = 0xFFFF

HIGH = 'high'
LOW = 'low'


class MessageDispatcher:
    def __init__(self, ard: Optional["ArduinoRemote"] = None):
        self.msg_handles = {typ.msg_code: [lambda _: None] for typ in msg_types}
        self.msg_handles[None] = [lambda _: None]
        self.ard = ard

    def handle_msg(self, msg):
        if msg is None:
            handles = self.msg_handles[None]
        else:
            handles = self.msg_handles[msg.msg_code]

        return [handle(msg) for handle in handles]

    def append_handle(self, msg_typ, handle):
        self.msg_handles[msg_typ.msg_code].append(handle)

    def set_handle(self, msg_typ, handle):
        self.clear_handles(msg_typ)
        self.append_handle(msg_typ, handle)

    def remove_handles(self, msg_typ, handle):
        self.msg_handles[msg_typ.msg_code].remove(handle)

    def clear_handles(self, msg_typ):
        self.msg_handles[msg_typ.msg_code] = []

    @classmethod
    def default_dispatcher(cls, ard: Optional["ArduinoRemote"] = None):
        disp = MessageDispatcher(ard)
        disp.set_handle(MsgText, lambda msg: print(msg.text, end=""))
        disp.set_handle(MsgBufDump, lambda msg: print(msg.buf))

        def set_analog_offset(msg):
            if disp.ard is not None:
                disp.ard.analog_offset = msg.offset

        disp.set_handle(MsgAnalogOffset, set_analog_offset)

        return disp


class ArduinoRemote:
    def __init__(self, pin_config, port='/dev/ttyACM0', baudrate=115200, session=None, in_buf_size=128,
                 heartbeat_rate=0.1, read_interval=0.005, min_read_sleep=0.001, read_serial_timeout=0.1,
                 file=sys.stdout):
        self.port = port
        self.baudrate = baudrate
        self.in_buf_size = in_buf_size

        for pin in pin_config.keys():
            if not ArduinoRemote.is_valid_pin(pin):
                raise ValueError(f"invalid pin format: {pin}")

        self.buf = Buffer(in_buf_size)
        self.analog_offset = 0
        if session is None:
            self.session = random.randint(0x01, 0xFE)
        else:
            self.session = session

        self.arduino = serial.Serial(port=port, baudrate=baudrate)
        self.read_thread = None
        self.read_stop_signal = False
        self.pin_values = {}
        self.pin_config = pin_config
        self.pin_map = {}
        self.heartbeat_rate = heartbeat_rate
        self.read_interval = read_interval
        self.min_read_sleep = min_read_sleep
        self.read_serial_timeout = read_serial_timeout
        self.file = file

    @contextmanager
    def cm(self):
        try:
            self.reset_remote()
            if any([c[0] == PIN_INPUT for c in self.pin_config.values()]):
                self.start_read_thread()
            yield self
        finally:
            self.stop_remote()

    @classmethod
    def is_valid_pin(cls, pin):
        if isinstance(pin, int):
            return pin >= 0
        elif isinstance(pin, str):
            if len(pin) >= 1 and all([c in digits for c in pin]):
                return cls.is_valid_pin(int(pin))
            elif len(pin) >= 2 and pin[0].lower() == 'a' and all([c in digits for c in pin[1:]]):
                return cls.is_valid_pin(int(pin[1:]))
            else:
                return False
        else:
            return False

    def as_internal_pin(self, pin):
        if isinstance(pin, int):
            return pin
        elif isinstance(pin, str):
            if len(pin) >= 1 and all([c in digits for c in pin]):
                return int(pin)
            elif len(pin) >= 2 and pin[0].lower() == 'a' and all([c in digits for c in pin[1:]]):
                return self.analog_offset + int(pin[1:])
            else:
                raise ValueError(f"cannot convert string to internal pin: {pin}")
        else:
            raise ValueError(f"cannot convert type to internal pin: {type(pin)}")

    def map_to_internal_pin(self, pin_key):
        res = [ip for pk, ip in self.pin_map.items() if pk == pin_key]
        if len(res) == 0:
            return None
        elif len(res) == 1:
            return res[0]
        else:
            raise ValueError("Duplicate pin key")

    def map_to_pin_key(self, internal_pin):
        res = [pk for pk, ip in self.pin_map.items() if ip == internal_pin]
        if len(res) == 0:
            return None
        elif len(res) == 1:
            return res[0]
        else:
            raise ValueError("Duplicate internal pin")

    def read_serial(self, sessions, timeout=None):
        if timeout is None:
            timeout = self.read_serial_timeout

        n_avail_bytes = None
        read_fails = 0
        read_serial_start = time.time()

        while ((n_avail_bytes is None or n_avail_bytes != 0) or len(self.buf) != 0) \
                and (timeout is None or time.time() - read_serial_start < timeout):
            msg_sent = False
            n_avail_bytes = self.arduino.in_waiting
            if n_avail_bytes > 0:
                n_read_bytes = min(n_avail_bytes, self.buf.free)

                if n_read_bytes > 0:
                    read_bytes = self.arduino.read(n_read_bytes)
                    self.buf.append(read_bytes)
            else:
                n_read_bytes = 0

            if len(self.buf) != 0:
                msgs = [self.read_msg(msg_type, session=session) for msg_type in msg_types for session in sessions]
                msgs = [msg for msg in msgs if msg is not None]

                for msg in msgs:
                    msg_sent = True
                    yield msg

            if len(self.buf) != 0 and not msg_sent and n_read_bytes == 0:
                read_fails += 1
                if read_fails >= 3:
                    skipped_byte = self.buf.consume(1)
                    if self.file is not None:
                        # print(f"skipped {skipped_byte}", file=self.file)
                        pass
                    read_fails = 0
                time.sleep(0.005)
            else:
                read_fails = 0

    def send_msg(self, msg, session=None):
        if session is None:
            session = self.session

        self.arduino.write(session.to_bytes(2, 'big') + bytes([msg.msg_code]) + msg.to_bytes())

    def read_msg(self, msg_type, session=None, max_idx=0):
        if session is None:
            session = SUPER_SESSION

        query_seq = session.to_bytes(2, 'big') + bytes([msg_type.msg_code])
        idx = self.buf.find(query_seq, max_idx=max_idx)
        if idx is not None and len(self.buf) >= msg_type.payload_size + 3:
            self.buf.consume(idx)
            data = self.buf.consume(msg_type.payload_size + 3)
            return msg_type.parse_data(data[3:])
        else:
            return None

    def reset_remote(self, retry=0, max_retries=10):
        if 0 < retry < max_retries:
            if self.file is not None:
                print(f"Retry {retry}/{max_retries}", file=self.file)
        elif retry >= max_retries:
            raise ValueError("exceeded maximum retries")

        self.pin_values = {}

        config_state = 'init_reset'
        received_await_config = False
        analog_offset = 0

        disp = MessageDispatcher.default_dispatcher(self)

        timeout = None
        config_msgs = None

        def handle_fail(_: MsgFail):
            nonlocal config_state
            if self.file is not None:
                print("Arduino in failure state", file=self.file)

            config_state = 'init_reset'
        disp.set_handle(MsgFail, handle_fail)

        def handle_await_config(_: MsgAwaitConfig):
            nonlocal received_await_config
            received_await_config = True

        disp.set_handle(MsgAwaitConfig, handle_await_config)

        def handle_analog_offset(_msg: MsgAnalogOffset):
            nonlocal analog_offset
            analog_offset = _msg.offset

        disp.set_handle(MsgAnalogOffset, handle_analog_offset)

        while config_state != 'main':
            for msg in self.read_serial(sessions=[SUPER_SESSION]):
                disp.handle_msg(msg)

            # send
            if config_state == 'init_reset':
                self.clear_serial_buffer()
                self.buf.clear()
                self.send_msg(MsgSetState(STATE_INIT_CONFIG), session=SUPER_SESSION)
                config_msgs = []
                config_state = 'await_config'
                received_await_config = False
                analog_offset = 0
                timeout = time.time() + 1.0
            elif config_state == 'await_config':
                if received_await_config:
                    config_state = 'send_get_analog_offset'
                elif timeout is not None and time.time() >= timeout:
                    config_state = 'init_reset'
            elif config_state == 'send_get_analog_offset':
                self.send_msg(MsgConfigGetAnalogOffset(), session=SUPER_SESSION)
                config_state = 'wait_analog_offset'
                timeout = time.time() + 1.0
            elif config_state == 'wait_analog_offset':
                if analog_offset is not None:
                    self.analog_offset = analog_offset
                    config_state = 'prepare_config'
                elif timeout is not None and time.time() >= timeout:
                    config_state = 'init_reset'
            elif config_state == 'prepare_config':
                config_msgs = [MsgConfigSession(self.session)]
                self.pin_values = {}
                self.pin_map = {pk: self.as_internal_pin(pk) for pk in self.pin_config.keys()}

                for pin, (pin_mode, ana_digi) in self.pin_config.items():
                    int_pin = self.map_to_internal_pin(pin)
                    config_msgs.append(MsgConfigPinmode(int_pin, pin_mode, ana_digi))
                    self.pin_values[pin] = None

                config_state = 'send_config'
            elif config_state == 'send_config':
                if config_msgs is not None and len(config_msgs) != 0:
                    self.send_msg(config_msgs.pop(0), session=SUPER_SESSION)
                    time.sleep(0.01)
                elif config_msgs is not None and len(config_msgs) == 0:
                    self.send_msg(MsgConfigFinalize(), session=SUPER_SESSION)
                    config_state = 'main'
            else:
                raise ValueError(f"invalid state: {config_state}")

            time.sleep(0.001)

    def start_read_thread(self):
        if self.read_thread is not None:
            return

        self.read_stop_signal = False

        def read_loop():
            disp = MessageDispatcher.default_dispatcher(self)
            last_heartbeat_sent = None
            last_read = None

            def handle_read(_msg):
                pin_key = self.map_to_pin_key(_msg.pin)
                if pin_key is not None:
                    self.pin_values[pin_key] = _msg.value

            disp.set_handle(MsgRead, handle_read)

            while not self.read_stop_signal:
                # update sensor values
                t = time.time()
                if last_read is None or (last_read + self.read_interval) < t:
                    for msg in self.read_serial(sessions=[SUPER_SESSION, self.session]):
                        disp.handle_msg(msg)

                    last_read = t

                # send heartbeat
                t = time.time()
                if last_heartbeat_sent is None or (last_heartbeat_sent + self.heartbeat_rate) < t:
                    self.send_msg(MsgHeartbeat(), session=self.session)
                    last_heartbeat_sent = t

                # determine sleep time
                t = time.time()
                next_read = last_read + self.read_interval
                next_heartbeat = last_heartbeat_sent + self.heartbeat_rate
                sleep_time = min(next_read - t, next_heartbeat - t)
                if self.min_read_sleep is not None:
                    sleep_time = max(sleep_time, self.min_read_sleep)

                time.sleep(sleep_time)

        self.read_thread = Thread(target=read_loop, daemon=True)
        self.read_thread.start()

    def stop_read_thread(self):
        if self.read_thread is None:
            return

        self.read_stop_signal = True
        self.read_thread.join()
        time.sleep(self.read_interval)

        while self.arduino.in_waiting != 0:
            self.clear_serial_buffer()
            time.sleep(self.read_interval)

    def stop_remote(self):
        self.stop_read_thread()
        self.send_msg(MsgSetState(STATE_IDLE), session=SUPER_SESSION)

    def set_pin(self, pin: Union[str, int], value):
        if pin not in self.pin_config.keys():
            raise ValueError(f"pin is not configured: {pin}")

        int_pin = self.map_to_internal_pin(pin)
        if int_pin is None:
            raise ValueError(f"Could not convert pin key to internal pin: {pin}")

        (pin_mode, ana_digi) = self.pin_config[pin]

        if pin_mode != PIN_OUTPUT:
            raise ValueError(f"pin is not an output pin: {pin}")

        if isinstance(value, str):
            if value.lower() == HIGH and ana_digi == PIN_DIGITAL:
                value = 1
            elif value.lower() == HIGH and ana_digi == PIN_ANALOG:
                value = 0xFF
            elif value.lower() == LOW and ana_digi in [PIN_DIGITAL, PIN_ANALOG]:
                value = 0
            else:
                raise ValueError(f"Unknown value: {value}")

        if ana_digi == PIN_DIGITAL:
            value = min(max(value, 0), 1)
        elif ana_digi == PIN_ANALOG:
            value = min(max(value, 0), 0xFF)
        else:
            raise ValueError(f"Unknown ana_digi: {ana_digi}")

        self.pin_values[pin] = value
        self.send_msg(MsgWrite(int_pin, value), session=self.session)

    @property
    def session_bytes(self):
        return self.session.to_bytes(2, 'big')

    def clear_serial_buffer(self):
        n_avail_bytes = self.arduino.in_waiting
        while n_avail_bytes != 0:
            self.arduino.read(n_avail_bytes)
            n_avail_bytes = self.arduino.in_waiting
