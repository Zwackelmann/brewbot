import can
from brewbot.can.util import pgn_to_can_id, can_id_to_pgn
from brewbot.config import Node, BoundMessage
from typing import Optional


class MsgRegistry:
    msg_by_pgn: dict[int, list[(Node, BoundMessage)]]
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

    def decode(self, msg: can.Message) -> Optional[(Node, BoundMessage, dict)]:
        if msg is None:
            return None

        pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(msg.arbitration_id)
        msg_def_candidates: Optional[list[Node, BoundMessage]] = self.msg_by_pgn.get(pgn)

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

    def nodes_by_type(self, type_name: str) -> list[Node]:
        return [node for node in self.nodes if node.node_type.key == type_name]
