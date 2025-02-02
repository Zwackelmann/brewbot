from typing import Optional

import yaml
from typing_extensions import Annotated
from pydantic import BaseModel, Field, BeforeValidator, PrivateAttr
from brewbot.util import encode_on_off, parse_on_off
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


class CanConfig(BaseModel):
    dbc_file: str
    channel: str
    interface: str
    receive_timeout: float
    process_interval: float


class SignalDef(BaseModel):
    key: str
    signal_name: str
    tpe_name: str = Field(alias="tpe")

    @property
    def encode_signal(self):
        return signal_encoders[self.tpe_name]

    @property
    def decode_signal(self):
        return signal_decoders[self.tpe_name]


class MsgType(BaseModel):
    key: str
    priority: int
    signals: list[SignalDef]

    def encode(self, d):
        return {s.signal_name: s.encode_signal(d[s.key]) for s in self.signals}

    def decode(self, can_msg):
        return {s.key: s.decode_signal(can_msg[s.signal_name]) for s in self.signals}


def check_node_message_direction(direction: str) -> str:
    if direction not in ["tx", "rx"]:
        raise ValueError(f"Direction must be tx or rx. Instead found {direction}")
    return direction


class NodeMessage(BaseModel):
    key: str
    msg_type_ref: str
    direction: Annotated[str, BeforeValidator(check_node_message_direction)]

    _msg_types_by_name: dict[str, MsgType] = PrivateAttr()

    @property
    def msg_type(self) -> MsgType:
        return self._msg_types_by_name[self.msg_type_ref]

    def bind(self, msg_types: list[MsgType]):
        self._msg_types_by_name = {t.key: t for t in msg_types}


class NodeType(BaseModel):
    key: str
    messages: list[NodeMessage]

    def bind(self, msg_types: list[MsgType]):
        for msg in self.messages:
            msg.bind(msg_types)


class NodeMessageBinding(BaseModel):
    ref_key: str
    dbc_msg: str
    src_addr: Optional[int] = None


class BoundMessage:
    node_message: NodeMessage
    node_message_binding: NodeMessageBinding
    dbc: Database

    def __init__(self, node_message: NodeMessage, node_message_binding: NodeMessageBinding, dbc: Database):
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
    def dbc_msg(self) -> Message:
        return self.dbc.get_message_by_name(self.node_message_binding.dbc_msg)

    @property
    def signals(self) -> list[SignalDef]:
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

class Node(BaseModel):
    key: str
    name: str
    node_type_ref: str
    node_addr: int
    message_bindings: list[NodeMessageBinding]
    debug: dict

    # Private attributes to store the computed messages.
    _messages: list[BoundMessage] = PrivateAttr()
    _messages_by_key: dict[str, BoundMessage] = PrivateAttr()
    _node_types_by_key: dict[str: NodeType] = PrivateAttr()

    def bind(self, node_types: list[NodeType], dbc: Database):
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
    def node_type(self) -> NodeType:
        return self._node_types_by_key[self.node_type_ref]

    @property
    def messages(self) -> list[BoundMessage]:
        return self._messages

    def message(self, key: str) -> BoundMessage:
        try:
            return self._messages_by_key[key]
        except KeyError:
            raise KeyError(f"No message found with key: {key}")


class TempSignalControllerConfig(BaseModel):
    p_gain: float
    d_gain: float
    max_cs: float
    pwm_interval: float
    low_jump_thres: float
    high_jump_thres: float


class TempSignalConfig(BaseModel):
    window: float
    controller: TempSignalControllerConfig


class SignalConfig(BaseModel):
    temp: TempSignalConfig


class Config:
    conf_dict: dict
    can: CanConfig
    dbc: Database
    message_types: list[MsgType]
    node_types: list[NodeType]
    nodes: list[Node]
    signals: SignalConfig

    _message_types_by_key: dict[str, MsgType]
    _node_types_by_key: dict[str, NodeType]
    _nodes_by_key: dict[str, Node]

    def __init__(self, conf_dict):
        self.conf_dict = conf_dict
        self.can = CanConfig(**conf_dict['can'])
        self.dbc = load_dbc_file(self.can.dbc_file)

        self.message_types = []
        self._message_types_by_key = {}
        for mt_conf in conf_dict['message_types']:
            msg_type = MsgType(**mt_conf)
            self.message_types.append(msg_type)
            self._message_types_by_key[msg_type.key] = msg_type

        self.node_types = []
        self._node_types_by_key = {}
        for node_type_conf in conf_dict['node_types']:
            node_type = NodeType(**node_type_conf)
            node_type.bind(self.message_types)
            self.node_types.append(node_type)
            self._node_types_by_key[node_type.key] = node_type

        self.nodes = []
        self._nodes_by_key = {}
        for node_conf in conf_dict['nodes']:
            node = Node(**node_conf)
            node.bind(self.node_types, self.dbc)
            self.nodes.append(node)
            self._nodes_by_key[node.key] = node

        self.signals = SignalConfig(**conf_dict['signals'])

    def message_type(self, key):
        return self._message_types_by_key[key]

    def node_type(self, key):
        return self._node_types_by_key[key]

    def node(self, key):
        return self._nodes_by_key[key]


def load_config_dict(path=CONFIG_PATH):
    with open(path) as f:
        return yaml.safe_load(f)

def load_config(path=CONFIG_PATH):
    conf_dict = load_config_dict(path)
    return Config(conf_dict)
