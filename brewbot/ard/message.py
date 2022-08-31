from dataclasses import dataclass


@dataclass
class MsgAwaitConfig:
    msg_code = 0xF0
    payload_size = 0

    @classmethod
    def parse_data(cls, _):
        return MsgAwaitConfig()

    @classmethod
    def to_bytes(cls):
        return b''


@dataclass
class MsgWrite:
    msg_code = 0xF1
    payload_size = 3

    pin: int
    value: int

    @classmethod
    def parse_data(cls, data):
        return MsgWrite(pin=data[0], value=(data[1] << 8) | data[2])

    def to_bytes(self):
        return bytes([self.pin, (self.value >> 8) & 0xFF, self.value & 0xFF])


@dataclass
class MsgRead:
    msg_code = 0xF2
    payload_size = 3

    pin: int
    value: int

    @classmethod
    def parse_data(cls, data):
        return MsgRead(pin=data[0], value=(data[1] << 8) | data[2])

    def to_bytes(self):
        return bytes([self.pin, (self.value >> 8) & 0xFF, self.value & 0xFF])


@dataclass
class MsgFail:
    msg_code = 0xF3
    payload_size = 0

    @classmethod
    def parse_data(cls, _):
        return MsgFail()

    @classmethod
    def to_bytes(cls):
        return b''


@dataclass
class MsgSetState:
    state: int
    msg_code = 0xF4
    payload_size = 1

    @classmethod
    def parse_data(cls, data):
        return MsgSetState(state=data[0])

    def to_bytes(self):
        return bytes([self.state])


@dataclass
class MsgConfigSession:
    session: int
    msg_code = 0xF5
    payload_size = 2

    @classmethod
    def parse_data(cls, data):
        return MsgConfigSession(session=(data[0] << 8) | data[1])

    def to_bytes(self):
        return bytes([(self.session >> 8) & 0xFF, self.session & 0xFF])


@dataclass
class MsgConfigPinmode:
    pin: int
    mode: int
    ana_digi: int
    msg_code = 0xF6
    payload_size = 3

    @classmethod
    def parse_data(cls, data):
        return MsgConfigPinmode(pin=data[0], mode=(data[1] >> 4) & 0xF, ana_digi=data[1] & 0xF)

    def to_bytes(self):
        return bytes([self.pin, self.mode, self.ana_digi])


@dataclass
class MsgConfigGetAnalogOffset:
    msg_code = 0xF7
    payload_size = 0

    @classmethod
    def parse_data(cls, _):
        return MsgConfigGetAnalogOffset()

    def to_bytes(self):
        return b''


@dataclass
class MsgConfigFinalize:
    msg_code = 0xF8
    payload_size = 0

    @classmethod
    def parse_data(cls, _):
        return MsgConfigFinalize()

    def to_bytes(self):
        return b''


@dataclass
class MsgAnalogOffset:
    offset: int
    msg_code = 0xF9
    payload_size = 1

    @classmethod
    def parse_data(cls, data):
        return MsgAnalogOffset(offset=data[0])

    def to_bytes(self):
        return bytes([self.offset])


@dataclass
class MsgText:
    text: str
    msg_code = 0xFA
    payload_size = 29

    @classmethod
    def parse_data(cls, data):
        try:
            text = bytes([b for b in data if b != 0x00]).decode('ascii')
        except UnicodeDecodeError:
            text = f"<corrupt text string>({data})"
        return MsgText(text=text)

    def to_bytes(self):
        padding = self.payload_size - len(self.text)
        return self.text.encode('ascii') + bytes([0x00 for _ in range(padding)])


@dataclass
class MsgHeartbeat:
    msg_code = 0xFB
    payload_size = 0

    @classmethod
    def parse_data(cls, _):
        return MsgHeartbeat()

    @classmethod
    def to_bytes(cls):
        return b''


@dataclass
class MsgBufDump:
    buf: bytes
    msg_code = 0xFC
    payload_size = 32

    @classmethod
    def parse_data(cls, data):
        return MsgBufDump(buf=data)

    def to_bytes(self):
        raise NotImplemented()


msg_types = [MsgAwaitConfig, MsgWrite, MsgRead, MsgFail, MsgSetState, MsgConfigSession, MsgConfigPinmode,
             MsgConfigGetAnalogOffset, MsgConfigFinalize, MsgAnalogOffset, MsgText, MsgHeartbeat, MsgBufDump]
