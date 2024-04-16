import cantools
import can

# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0


def pdu_format(pgn):
    return (pgn >> 8) & 0xFF


def is_pdu_format_1(pgn):
    return pdu_format(pgn) < 0xF0


def is_pdu_format_2(pgn):
    return pdu_format(pgn) >= 0xF0


def pgn_to_can_id(pgn, priority, src_addr, dest_addr):
    pgn_encoded = pgn
    if is_pdu_format_1(pgn):
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


def can_id_to_pgn(can_id):
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
        dest_addr = 0x00

    return pgn, priority, src_addr, dest_addr


def main():
    db = cantools.database.load_file("messages.dbc")

    can_bus = can.interface.Bus('can0', bustype='socketcan')
    try:
        """relay_msg = db.get_message_by_name("HEAT_PLATE")
        signals = {"RELAY_STATE": 0x00}

        message = can.Message(
            arbitration_id=pgn_to_can_id(relay_msg.frame_id, 6, 0x80, 0x00),
            data=relay_msg.encode(signals),
            is_extended_id=True,
            dlc=8
        )

        can_bus.send(message)"""

        temp_msg = db.get_message_by_name("TEMP")

        while True:
            message = can_bus.recv()
            pgn, priority, src_addr, dest_addr = can_id_to_pgn(message.arbitration_id)
            if pgn == temp_msg.frame_id and src_addr == 0x70:
                print(temp_msg.decode(message.data))
    finally:
        can_bus.shutdown()

    print("hello")


if __name__ == "__main__":
    main()
