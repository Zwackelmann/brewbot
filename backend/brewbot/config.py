from typing import Optional, Any

import yaml
from typing_extensions import Annotated
from pydantic import BaseModel, Field, BeforeValidator, PrivateAttr
from brewbot.util import encode_on_off, parse_on_off, load_object, int_range
from cantools.database import Database, load_string as load_dbc_string
from cantools.database.can.message import Message

CONFIG_PATH = 'conf/config.yaml'

signal_encoders = {
    "int": lambda x: x,
    "float": lambda x: x,
    "flag": encode_on_off
}

signal_decoders = {
    "int": lambda x: x,
    "float": lambda x: x,
    "flag": parse_on_off
}

class CanBusConfig(BaseModel):
    channel: str
    interface: str
    receive_timeout: float


class CanPortConfig(BaseModel):
    process_interval: float
    bus: Optional[CanBusConfig] = None
    device_connect_interval: float


class SignalDefConfig(BaseModel):
    key: str
    dbc_name: str
    start_bit: int
    signal_size: int
    signed: bool = False
    value_scale: float = 1.0
    value_offset: float = 0.0
    value_min_raw: Optional[float] = Field(default=None, alias="value_min")
    value_max_raw: Optional[float] = Field(default=None, alias="value_max")
    unit: str = ""
    c_type: str
    py_type: str

    @property
    def encode_signal(self):
        return signal_encoders[self.py_type]

    @property
    def decode_signal(self):
        return signal_decoders[self.py_type]

    @property
    def value_min(self):
        if self.value_min_raw is not None:
            return self.value_min_raw
        else:
            return int_range(self.signal_size, self.signed)[0] * self.value_scale

    @property
    def value_max(self):
        if self.value_max_raw is not None:
            return self.value_max_raw
        else:
            return int_range(self.signal_size, self.signed)[1] * self.value_scale


def check_direction(direction: str) -> str:
    if direction not in ["tx", "rx"]:
        raise ValueError(f"Direction must be tx or rx. Instead found {direction}")
    return direction


class MsgTypeConfig(BaseModel):
    key: str
    dbc_name: str
    priority: int
    pgn: int
    direction: Annotated[str, BeforeValidator(check_direction)]
    signals: list[SignalDefConfig]

    def encode(self, d):
        return {s.dbc_name: s.encode_signal(d[s.key]) for s in self.signals}

    def decode(self, can_msg):
        return {s.key: s.decode_signal(can_msg[s.dbc_name]) for s in self.signals}


class NodeMessageConfig(BaseModel):
    key: str
    msg_type_ref: str
    frequency: Optional[float] = None

    _msg_types_by_key: dict[str, MsgTypeConfig] = PrivateAttr()
    _dbc: Optional[Database] = PrivateAttr(default=None)

    @property
    def msg_type(self) -> MsgTypeConfig:
        return self._msg_types_by_key[self.msg_type_ref]

    def bind(self, msg_types: list[MsgTypeConfig], dbc: Database):
        self._msg_types_by_key = {t.key: t for t in msg_types}
        self._dbc = dbc

    @property
    def direction(self) -> str:
        return self.msg_type.direction

    @property
    def dbc_msg(self) -> Message:
        return self._dbc.get_message_by_name(self.msg_type.dbc_name)

    @property
    def signals(self) -> list[SignalDefConfig]:
        return self.msg_type.signals

    @property
    def priority(self) -> int:
        return self.msg_type.priority

    def encode(self, d: dict):
        return self.msg_type.encode(d)

    def decode(self, can_msg: dict):
        return self.msg_type.decode(can_msg)


class NodeTypeConfig(BaseModel):
    key: str
    messages: list[NodeMessageConfig]
    mock_class: Optional[str] = None
    node_state_class: Optional[str] = None

    _message_by_key: Optional[dict[str, NodeMessageConfig]] = PrivateAttr(default=None)

    def bind(self, msg_types: list[MsgTypeConfig], dbc: Database):
        for msg in self.messages:
            msg.bind(msg_types, dbc)

    def message(self, key: str) -> NodeMessageConfig:
        if self._message_by_key is None:
            self._message_by_key = {m.key: m for m in self.messages}

        return self._message_by_key[key]


class NodeConfig(BaseModel):
    key: str
    node_type_ref: str
    node_addr: int
    params: Optional[dict] = Field(default_factory=lambda: {})
    debug: dict
    node_mock_class: Optional[str] = Field(default=None, alias="mock_class")
    node_node_state_class: Optional[str] = Field(default=None, alias="node_state_class")

    _node_type_by_key: Optional[dict[str, NodeTypeConfig]] = PrivateAttr(default=None)

    def bind(self, node_types: list[NodeTypeConfig]):
        self._node_type_by_key = {n.key: n for n in node_types}

    @property
    def node_type(self) -> NodeTypeConfig:
        return self._node_type_by_key[self.node_type_ref]

    @property
    def messages(self) -> list[NodeMessageConfig]:
        return self.node_type.messages

    def message(self, key: str) -> NodeMessageConfig:
        return self.node_type.message(key)

    @property
    def mock_class(self) -> Optional[str]:
        if self.node_mock_class is not None:
            return self.node_mock_class
        else:
            return self.node_type.mock_class

    @property
    def node_state_class(self) -> Optional[str]:
        if self.node_node_state_class is not None:
            return self.node_node_state_class
        else:
            return self.node_type.node_state_class


class AssemblyTypeConfig(BaseModel):
    key: str
    assembly_class: str


class ParamConfig(BaseModel):
    name: str
    config_class: Optional[str] = Field(default=None)
    value: Any


class AssemblyConfig(BaseModel):
    key: str
    assembly_type_ref: str
    nodes_dict: Optional[dict] = Field(default=None, alias="nodes")
    params: list[ParamConfig] = Field(default_factory=lambda: [])

    # Private attributes to store the computed messages.
    _node_by_key: dict[str, NodeConfig] = PrivateAttr(default=None)
    _nodes: dict = PrivateAttr(default=None)
    _assembly_type_by_key: dict[str, AssemblyTypeConfig] = PrivateAttr(default=None)

    def bind(self, assembly_types: list[AssemblyTypeConfig], nodes: list[NodeConfig]):
        self._assembly_type_by_key = {at.key: at for at in assembly_types}
        self._node_by_key = {n.key: n for n in nodes}

    def resolve_node_refs(self, o):
        if isinstance(o, str):
            if o in self._node_by_key:
                return self._node_by_key[o]
            else:
                raise ValueError(f"node reference for assembly not found: {o}")
        elif isinstance(o, list):
            return [self.resolve_node_refs(i) for i in o]
        elif isinstance(o, dict):
            return {k: self.resolve_node_refs(v) for k, v in o.items()}
        else:
            raise ValueError(f"unexpected type in nodes dict: {type(o)}")

    @property
    def nodes(self):
        if self._nodes is None:
            self._nodes = self.resolve_node_refs(self.nodes_dict)

        return self._nodes

    @property
    def assembly_type(self):
        return self._assembly_type_by_key[self.assembly_type_ref]

    @property
    def assembly_class(self):
        return self.assembly_type.assembly_class

    @property
    def parsed_param(self):
        d = {}
        for param in self.params:
            if param.config_class is not None:
                if not isinstance(param.value, dict):
                    raise ValueError("param value must be dict when `config_class` is set")
                cls = load_object(param.config_class)
                value = cls(**param.value)
            else:
                value = param.value

            d[param.name] = value

        return d

    def __repr__(self):
        return (
            f"AssemblyConfig("
            f"key={self.key!r}, "
            f"assembly_type={self.assembly_type!r}, "
            f"nodes={self.nodes!r}, "
            f"params={self.params!r}"
            f")"
        )

    def __str__(self):
        return repr(self)


class ControllerConfig(BaseModel):
    p_gain: float
    d_gain: float
    max_cs: float
    pwm_interval: float
    low_jump_thres: float
    high_jump_thres: float


class DataCollectConfig(BaseModel):
    window: float
    collect_interval: float


class TempSignalControllerConfig(BaseModel):
    p_gain: float
    d_gain: float
    max_cs: float
    pwm_interval: float
    low_jump_thres: float
    high_jump_thres: float


class CanEnvConfig:
    conf_dict: dict
    port: CanPortConfig
    dbc: Database
    message_types: list[MsgTypeConfig]
    node_types: list[NodeTypeConfig]
    nodes: list[NodeConfig]
    assembly_types: list[AssemblyTypeConfig]
    assemblies: list[AssemblyConfig]

    _message_types_by_key: dict[str, MsgTypeConfig]
    _node_types_by_key: dict[str, NodeTypeConfig]
    _nodes_by_key: dict[str, NodeConfig]
    _assembly_type_by_key: dict[str, AssemblyTypeConfig]
    _assembly_by_key: dict[str, AssemblyConfig]

    def __init__(self, conf_dict):
        self.conf_dict = conf_dict
        self.port = CanPortConfig(**conf_dict['port'])

        self.message_types = []
        self._message_types_by_key = {}
        for mt_conf in conf_dict['message_types']:
            msg_type = MsgTypeConfig(**mt_conf)
            self.message_types.append(msg_type)
            self._message_types_by_key[msg_type.key] = msg_type

        self.dbc = gen_dbc(self)

        self.node_types = []
        self._node_types_by_key = {}
        for node_type_conf in conf_dict['node_types']:
            node_type = NodeTypeConfig(**node_type_conf)
            node_type.bind(self.message_types, self.dbc)
            self.node_types.append(node_type)
            self._node_types_by_key[node_type.key] = node_type

        self.nodes = []
        self._nodes_by_key = {}
        for node_conf in conf_dict['nodes']:
            node = NodeConfig(**node_conf)
            node.bind(self.node_types) #, self.dbc)
            self.nodes.append(node)
            self._nodes_by_key[node.key] = node

        self.assembly_types = []
        self._assembly_type_by_key = {}
        for at_conf in conf_dict['assembly_types']:
            at = AssemblyTypeConfig(**at_conf)
            self.assembly_types.append(at)
            self._assembly_type_by_key[at.key] = at

        self.assemblies = []
        self._assembly_by_key = {}
        for assembly_conf in conf_dict['assemblies']:
            assembly = AssemblyConfig(**assembly_conf)
            assembly.bind(self.assembly_types, self.nodes)
            self.assemblies.append(assembly)
            self._assembly_by_key[assembly.key] = assembly


    def message_type(self, key):
        return self._message_types_by_key[key]

    def node_type(self, key):
        return self._node_types_by_key[key]

    def node(self, key):
        return self._nodes_by_key[key]

    def assembly(self, key):
        return self._assembly_by_key[key]


def load_config_dict(path=CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def load_config(path=CONFIG_PATH) -> CanEnvConfig:
    conf_dict = load_config_dict(path)
    return CanEnvConfig(conf_dict)

def gen_dbc(conf):
    dbc_str_buf = ["""VERSION "1.0"

NS_ :
    NS_DESC_
    CM_
    BA_DEF_
    BA_
    VAL_
    CAT_DEF_
    CAT_
    FILTER
    BA_DEF_DEF_
    EV_DATA_
    ENVVAR_DATA_
    SGTYPE_
    SGTYPE_VAL_
    BA_DEF_SGTYPE_
    BA_SGTYPE_
    SIG_TYPE_REF_
    VAL_TABLE_
    SIG_GROUP_
    SIG_VALTYPE_
    SIGTYPE_VALTYPE_
    BO_TX_BU_
    BA_DEF_REL_
    BA_REL_
    BA_DEF_DEF_REL_
    BU_SG_REL_
    BU_EV_REL_
    BU_BO_REL_
    SG_MUL_VAL_

BS_:

BU_: MASTER SLAVE
"""]

    for msg_type_conf in conf.message_types:
        can_id = msg_type_conf.pgn | 0x80000000

        if msg_type_conf.direction == "rx":
            sender_node = "SLAVE"
            receiver_node = "MASTER"
        elif msg_type_conf.direction == "tx":
            sender_node = "MASTER"
            receiver_node = "SLAVE"
        else:
            raise ValueError("message direction was not 'rx' or 'tx'")

        dbc_str_buf.append("\n")
        dbc_str_buf.append(f"BO_ {can_id} {msg_type_conf.dbc_name}: 8 {sender_node}\n")

        for signal in msg_type_conf.signals:
            if abs(signal.value_scale - int(signal.value_scale)) < 1e-12:
                value_scale = int(signal.value_scale)
            else:
                value_scale = signal.value_scale

            if abs(signal.value_offset - int(signal.value_offset)) < 1e-12:
                value_offset = int(signal.value_offset)
            else:
                value_offset = signal.value_offset

            if abs(signal.value_min - int(signal.value_min)) < 1e-12:
                value_min = int(signal.value_min)
            else:
                value_min = signal.value_min

            if abs(signal.value_max - int(signal.value_max)) < 1e-12:
                value_max = int(signal.value_max)
            else:
                value_max = signal.value_max

            sign = "-" if signal.signed else "+"
            dbc_str_buf.append(f"  SG_ {signal.dbc_name} : {signal.start_bit}|{signal.signal_size}@1{sign} ({value_scale},{value_offset}) [{value_min}|{value_max}] \"{signal.unit}\" {receiver_node}\n")

    return load_dbc_string("".join(dbc_str_buf))
