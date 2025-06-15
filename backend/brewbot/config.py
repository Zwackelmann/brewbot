from typing import Optional, Any

import yaml
from typing_extensions import Annotated
from pydantic import BaseModel, Field, BeforeValidator, PrivateAttr
from brewbot.util import encode_on_off, parse_on_off, load_object
from cantools.database import Database, load_file as load_dbc_file, Message

CONFIG_PATH = 'conf/config.yaml'

signal_encoders = {
    "float": lambda x: x,
    "flag": encode_on_off
}

signal_decoders = {
    "float": lambda x: x,
    "flag": parse_on_off
}

class CanBusConfig(BaseModel):
    channel: str
    interface: str
    receive_timeout: float


class CanConfig(BaseModel):
    dbc_file: str
    process_interval: float
    bus: Optional[CanBusConfig] = None


class SignalDefConfig(BaseModel):
    key: str
    signal_name: str
    tpe_name: str = Field(alias="tpe")

    @property
    def encode_signal(self):
        return signal_encoders[self.tpe_name]

    @property
    def decode_signal(self):
        return signal_decoders[self.tpe_name]


class MsgTypeConfig(BaseModel):
    key: str
    priority: int
    signals: list[SignalDefConfig]

    def encode(self, d):
        return {s.signal_name: s.encode_signal(d[s.key]) for s in self.signals}

    def decode(self, can_msg):
        return {s.key: s.decode_signal(can_msg[s.signal_name]) for s in self.signals}


def check_node_message_direction(direction: str) -> str:
    if direction not in ["tx", "rx"]:
        raise ValueError(f"Direction must be tx or rx. Instead found {direction}")
    return direction


class NodeMessageConfig(BaseModel):
    key: str
    msg_type_ref: str
    direction: Annotated[str, BeforeValidator(check_node_message_direction)]
    frequency: Optional[float] = None

    _msg_types_by_name: dict[str, MsgTypeConfig] = PrivateAttr()

    @property
    def msg_type(self) -> MsgTypeConfig:
        return self._msg_types_by_name[self.msg_type_ref]

    def bind(self, msg_types: list[MsgTypeConfig]):
        self._msg_types_by_name = {t.key: t for t in msg_types}


class NodeTypeConfig(BaseModel):
    key: str
    messages: list[NodeMessageConfig]
    mock_class: Optional[str] = None
    node_state_class: Optional[str] = None

    def bind(self, msg_types: list[MsgTypeConfig]):
        for msg in self.messages:
            msg.bind(msg_types)


class NodeMessageBinding(BaseModel):
    ref_key: str
    dbc_msg: str
    src_addr: Optional[int] = None


class BoundMessage:
    node_message: NodeMessageConfig
    node_message_binding: NodeMessageBinding
    dbc: Database

    def __init__(self, node_message: NodeMessageConfig, node_message_binding: NodeMessageBinding, dbc: Database):
        self.node_message = node_message
        self.node_message_binding = node_message_binding
        self.dbc = dbc

        if node_message.key != node_message_binding.ref_key:
            raise ValueError("message def key and message binding key do not match")

    @property
    def key(self) -> str:
        return self.node_message.key

    @property
    def direction(self) -> str:
        return self.node_message.direction

    @property
    def frequency(self) -> Optional[float]:
        return self.node_message.frequency

    @property
    def dbc_msg(self) -> Message:
        return self.dbc.get_message_by_name(self.node_message_binding.dbc_msg)

    @property
    def signals(self) -> list[SignalDefConfig]:
        return self.node_message.msg_type.signals

    @property
    def priority(self) -> int:
        return self.node_message.msg_type.priority

    @property
    def src_addr(self) -> Optional[int]:
        return self.node_message_binding.src_addr

    def encode(self, d: dict):
        return self.node_message.msg_type.encode(d)

    def decode(self, can_msg: dict):
        return self.node_message.msg_type.decode(can_msg)

    def __repr__(self):
        return (
            f"BoundMessage("
            f"key={self.key!r}, "
            f"direction={self.direction!r}, "
            f"dbc_mcs={self.dbc_msg!r}, "
            f"signals={self.signals!r}, "
            f"priority={self.priority!r}"
            f")"
        )

    def __str__(self):
        return repr(self)


class NodeConfig(BaseModel):
    key: str
    name: str
    node_type_ref: str
    node_addr: int
    message_bindings: list[NodeMessageBinding]
    params: Optional[dict] = Field(default_factory=lambda: {})
    debug: dict
    node_mock_class: Optional[str] = Field(default=None, alias="mock_class")
    node_node_state_class: Optional[str] = Field(default=None, alias="node_state_class")

    # Private attributes to store the computed messages.
    _messages: list[BoundMessage] = PrivateAttr()
    _messages_by_key: dict[str, BoundMessage] = PrivateAttr()
    _node_types_by_key: dict[str, NodeTypeConfig] = PrivateAttr()

    def bind(self, node_types: list[NodeTypeConfig], dbc: Database):
        self._node_types_by_key = {n.key: n for n in node_types}

        messages = []
        messages_by_key = {}

        for node_msg in self.node_type.messages:
            msg_bindings = [b for b in self.message_bindings if b.ref_key == node_msg.key]
            if len(msg_bindings) == 0:
                raise ValueError(f"node {self.key} did not bind message with key: {node_msg.key}")
            elif len(msg_bindings) > 1:
                raise ValueError(f"node {self.key} has ambiguous message bind for key: {node_msg.key}")
            else:
                bound_msg = BoundMessage(node_msg, msg_bindings[0], dbc)
                messages.append(bound_msg)
                messages_by_key[node_msg.key] = bound_msg

        self._messages = messages
        self._messages_by_key = messages_by_key

    @property
    def node_type(self) -> NodeTypeConfig:
        return self._node_types_by_key[self.node_type_ref]

    @property
    def messages(self) -> list[BoundMessage]:
        return self._messages

    def message(self, key: str) -> BoundMessage:
        try:
            return self._messages_by_key[key]
        except KeyError:
            raise KeyError(f"No message found with key: {key}")

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


class Config:
    conf_dict: dict
    can: CanConfig
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
        self.can = CanConfig(**conf_dict['can'])
        self.dbc = load_dbc_file(self.can.dbc_file)

        self.message_types = []
        self._message_types_by_key = {}
        for mt_conf in conf_dict['message_types']:
            msg_type = MsgTypeConfig(**mt_conf)
            self.message_types.append(msg_type)
            self._message_types_by_key[msg_type.key] = msg_type

        self.node_types = []
        self._node_types_by_key = {}
        for node_type_conf in conf_dict['node_types']:
            node_type = NodeTypeConfig(**node_type_conf)
            node_type.bind(self.message_types)
            self.node_types.append(node_type)
            self._node_types_by_key[node_type.key] = node_type

        self.nodes = []
        self._nodes_by_key = {}
        for node_conf in conf_dict['nodes']:
            node = NodeConfig(**node_conf)
            node.bind(self.node_types, self.dbc)
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


def load_config_dict(path=CONFIG_PATH):
    with open(path) as f:
        return yaml.safe_load(f)

def load_config(path=CONFIG_PATH):
    conf_dict = load_config_dict(path)
    return Config(conf_dict)
