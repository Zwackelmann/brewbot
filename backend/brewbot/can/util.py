from typing import Tuple

def pdu_format(pgn: int) -> int:
    return (pgn >> 8) & 0xFF


def is_pdu_format_1(pgn: int) -> bool:
    return pdu_format(pgn) < 0xF0


def is_pdu_format_2(pgn: int) -> bool:
    return pdu_format(pgn) >= 0xF0


def pgn_to_can_id(pgn: int, priority: int, src_addr: int, dest_addr: int) -> int:
    pgn_encoded = pgn
    if is_pdu_format_1(pgn):
        pgn_encoded &= 0xFF00  # clear dest_addr part
        pgn_encoded |= (dest_addr & 0xFF)

    dp = (pgn_encoded >> 16) & 0x1
    pf = (pgn_encoded >> 8) & 0xFF
    ps = pgn_encoded & 0xFF

    can_id = 0
    can_id |= (priority & 0x7) << 26
    can_id |= (dp & 0x1) << 24
    can_id |= (pf & 0xFF) << 16
    can_id |= (ps & 0xFF) << 8
    can_id |= src_addr & 0xFF

    return can_id


def can_id_to_pgn(can_id: int) -> Tuple[int, int, int, int]:
    src_addr = can_id & 0xFF
    ps = (can_id >> 8) & 0xFF
    pf = (can_id >> 16) & 0xFF
    dp = (can_id >> 24) & 0x1
    priority = (can_id >> 26) & 0x7

    pgn = ps
    pgn |= (pf << 8)
    pgn |= (dp << 16)

    if is_pdu_format_1(pgn):
        dest_addr = (pgn & 0xFF)
        pgn = (pgn & 0x1FF00)
    else:
        dest_addr = 0xFF

    return pgn, priority, src_addr, dest_addr
