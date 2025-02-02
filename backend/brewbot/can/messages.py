import can
from brewbot.can.util import pgn_to_can_id, can_id_to_pgn
from brewbot.util import encode_on_off
from brewbot.config import Node, BoundMessage


class MsgRegistry:
    msg_by_pgn: dict[int, (Node, BoundMessage)]
    nodes: list[Node]
    _nodes_by_key: dict[str, Node]

    def __init__(self, nodes: list[Node]):
        self.nodes = nodes
        self._nodes_by_key = {n.key: n for n in nodes}

        self.msg_by_pgn = {}
        for node in nodes:
            for msg_def in node.messages:
                if msg_def.direction == "rx":
                    self.msg_by_pgn.setdefault(msg_def.dbc_msg.frame_id, []).append((node, msg_def))

    def decode(self, msg: can.Message):
        if msg is None:
            return None

        pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(msg.arbitration_id)
        msg_def_candidates = self.msg_by_pgn.get(pgn)

        if msg_def_candidates is None:
            return None
        else:
            for node, msg_def in msg_def_candidates:
                if (node.node_addr is None or msg_dest_addr == 0xFF or msg_dest_addr == node.node_addr) \
                        and (msg_def.src_addr is None or msg_src_addr == msg_def.src_addr):
                    return node, msg_def, msg_def.decode(msg_def.dbc_msg.decode(msg.data))

        return None

    def encode(self, target_node_key: str, msg_key: str, msg: dict, src_node_key: str = 'master') -> can.Message:
        src_node: Node = self._nodes_by_key[src_node_key]
        target_node: Node = self._nodes_by_key[target_node_key]
        msg_def: BoundMessage = self._nodes_by_key[target_node_key].message(msg_key)
        data: bytes = msg_def.dbc_msg.encode(msg_def.encode(msg))

        return can.Message(
            arbitration_id=pgn_to_can_id(msg_def.dbc_msg.frame_id, msg_def.priority, src_node.node_addr, target_node.node_addr),
            data=data,
            is_extended_id=True,
            dlc=8
        )


def create_motor_cmd_msg(db, on, src_addr, dest_addr=None, priority=None):
    if dest_addr is None:
        dest_addr = 0xFF

    if priority is None:
        priority = 6

    msg = db.get_message_by_name("MOTOR_CMD")

    if on:
        signals = {"RELAY_STATE": 0x01}
    else:
        signals = {"RELAY_STATE": 0x00}

    return can.Message(
        arbitration_id=pgn_to_can_id(msg.frame_id, priority, src_addr, dest_addr),
        data=msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def create_motor_state_msg(db, on_off, node_addr, dest_addr=None, priority=None):
    if dest_addr is None:
        dest_addr = 0xFF

    if priority is None:
        priority = 6

    msg = db.get_message_by_name("MOTOR_STATE")
    signals = {"RELAY_STATE": encode_on_off(on_off)}

    return can.Message(
        arbitration_id=pgn_to_can_id(msg.frame_id, priority, node_addr, dest_addr),
        data=msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def parse_motor_state_msg(message, db, node_addr=None, assert_src_addr=None):
    msg = db.get_message_by_name("MOTOR_STATE")

    pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(message.arbitration_id)

    if pgn == msg.frame_id \
            and (node_addr is None or msg_dest_addr == 0xFF or msg_dest_addr == node_addr) \
            and (assert_src_addr is None or msg_src_addr == assert_src_addr):
        return msg.decode(message.data)
    else:
        return None


def create_heat_plate_cmd_msg(db, on, node_addr, dest_addr=None, priority=None):
    if dest_addr is None:
        dest_addr = 0xFF

    if priority is None:
        priority = 6

    msg = db.get_message_by_name("HEAT_PLATE_CMD")

    if on:
        signals = {"RELAY_STATE": 0x01}
    else:
        signals = {"RELAY_STATE": 0x00}

    return can.Message(
        arbitration_id=pgn_to_can_id(msg.frame_id, priority, node_addr, dest_addr),
        data=msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def create_heat_plate_state_msg(db, on_off, node_addr, dest_addr=None, priority=None):
    if dest_addr is None:
        dest_addr = 0xFF

    if priority is None:
        priority = 6

    msg = db.get_message_by_name("HEAT_PLATE_STATE")
    signals = {"RELAY_STATE": encode_on_off(on_off)}

    return can.Message(
        arbitration_id=pgn_to_can_id(msg.frame_id, priority, node_addr, dest_addr),
        data=msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def parse_heat_plate_state_msg(message, db, node_addr=None, assert_src_addr=None):
    msg = db.get_message_by_name("HEAT_PLATE_STATE")

    pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(message.arbitration_id)

    if pgn == msg.frame_id \
            and (node_addr is None or msg_dest_addr == 0xFF or msg_dest_addr == node_addr) \
            and (assert_src_addr is None or msg_src_addr == assert_src_addr):
        return msg.decode(message.data)
    else:
        return None


def create_temp_state_msg(db, temp_c, temp_v, node_addr, dest_addr=None, priority=None):
    if dest_addr is None:
        dest_addr = 0xFF

    if priority is None:
        priority = 6

    msg = db.get_message_by_name("TEMP_STATE")

    signals = {"TEMP_C": temp_c, "TEMP_V": temp_v}

    return can.Message(
        arbitration_id=pgn_to_can_id(msg.frame_id, priority, node_addr, dest_addr),
        data=msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def parse_temp_state_msg(message, db, msg_name, node_addr=None, assert_src_addr=None):
    msg = db.get_message_by_name(msg_name)

    pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(message.arbitration_id)

    if pgn == msg.frame_id \
            and (node_addr is None or msg_dest_addr == 0xFF or msg_dest_addr == node_addr) \
            and (assert_src_addr is None or msg_src_addr == assert_src_addr):
        return msg.decode(message.data)
    else:
        return None
