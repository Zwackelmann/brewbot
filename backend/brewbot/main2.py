import cantools
from datetime import datetime
import can
from brewbot.can.messages import heat_plate_msg, motor_msg, parse_temp_msg
import time
from brewbot.data.temp import TempState


# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0


def main():
    db = cantools.database.load_file("conf/messages.dbc")

    can_bus = can.interface.Bus('can0', interface='socketcan')

    update_rate = 0.5
    last_update = None
    temp_state = TempState(temp_to_v_file="conf/measurements/temp_to_v")

    try:
        can_bus.send(heat_plate_msg(db, False))
        can_bus.send(motor_msg(db, False))

        while True:
            message = can_bus.recv()
            temp_msg = parse_temp_msg(message, db, 0x70)

            if temp_msg is not None:
                temp_state.put(temp_msg['TEMP_VOLTAGE'])

                if last_update is None or last_update < (time.time() - update_rate):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    print(f"{timestamp}: temp c: {temp_state.curr_c}")
                    # print(f"{timestamp}: voltage: {mean_tempv}")

                    last_update = time.time()
    finally:
        can_bus.shutdown()


if __name__ == "__main__":
    main()
