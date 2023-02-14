from brewbot.ard.ard_remote import ArduinoRemote as ArduinoRemoteProd, MsgWrite
import sys

class ArduinoRemote(ArduinoRemoteProd):
    def __init__(self, pin_config, port='/dev/ttyACM0', baudrate=115200, session=None, in_buf_size=128,
                 heartbeat_rate=0.1, read_interval=0.005, min_read_sleep=0.001, read_serial_timeout=0.1,
                 file=sys.stdout):
        super().__init__(pin_config, port, baudrate, session, in_buf_size, heartbeat_rate, read_interval,
                         min_read_sleep, read_serial_timeout, file)

        self.pin_map = {pk: self.as_internal_pin(pk) for pk in self.pin_config.keys()}

    @property
    def arduino(self):
        raise NotImplemented()

    def send_msg(self, msg, session=None):
        pass

    def start_read_thread(self):
        pass

    def stop_read_thread(self):
        pass

    def reset_remote(self, retry=0, max_retries=10):
        pass

    def stop_remote(self):
        pass

    def read_serial(self, sessions, timeout=None):
        return []

    def clear_serial_buffer(self):
        pass
