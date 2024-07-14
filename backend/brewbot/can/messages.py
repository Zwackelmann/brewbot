import can
from brewbot.can.util import pgn_to_can_id, can_id_to_pgn


def heat_plate_msg(db, on, src_addr):
    relay_msg = db.get_message_by_name("HEAT_PLATE")

    if on:
        signals = {"RELAY_STATE": 0x01}
    else:
        signals = {"RELAY_STATE": 0x00}

    return can.Message(
        arbitration_id=pgn_to_can_id(relay_msg.frame_id, 6, src_addr, 0x00),
        data=relay_msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def motor_msg(db, on, src_addr):
    relay_msg = db.get_message_by_name("MOTOR")

    if on:
        signals = {"RELAY_STATE": 0x01}
    else:
        signals = {"RELAY_STATE": 0x00}

    return can.Message(
        arbitration_id=pgn_to_can_id(relay_msg.frame_id, 6, src_addr, 0x00),
        data=relay_msg.encode(signals),
        is_extended_id=True,
        dlc=8
    )


def parse_temp_msg(message, db, src_addr=None):
    temp_msg = db.get_message_by_name("TEMP")

    pgn, priority, msg_src_addr, msg_dest_addr = can_id_to_pgn(message.arbitration_id)
    if pgn == temp_msg.frame_id and src_addr is None or src_addr == msg_src_addr:
        return temp_msg.decode(message.data)
    else:
        return None
