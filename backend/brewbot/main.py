import cantools
from datetime import datetime
import can
from brewbot.can.messages import (create_heat_plate_cmd_msg, parse_heat_plate_state_msg, create_motor_cmd_msg,
                                  parse_motor_state_msg, parse_temp_state_msg)
from brewbot.can.util import load_can_database
import time
from brewbot.data.temp import TempState
from brewbot.config import load_config


# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0


def main():
    conf = load_config()

    db = load_can_database(conf["can"]["dbc_file"])
    can_bus = can.interface.Bus(conf["can"]["channel"], interface=conf["can"]["interface"])

    update_rate = 0.5
    last_update = None
    temp_state = TempState(temp_to_v_file=conf["signals"]["temp"]["measurements"])

    try:
        can_bus.send(create_heat_plate_cmd_msg(db, False, conf["can"]["node_addr"]))
        can_bus.send(create_motor_cmd_msg(db, False, conf["can"]["node_addr"]))

        while True:
            message = can_bus.recv()
            temp_msg = parse_temp_state_msg(message, db, conf["can"]["node_addr"], conf["signals"]["temp"]["node_addr"])

            if temp_msg is not None:
                temp_state.put(temp_msg['TEMP_V'])
                print("temp_c", temp_msg['TEMP_C'])
                print("temp_v", temp_msg['TEMP_V'])

                if last_update is None or last_update < (time.time() - update_rate):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    print(f"{timestamp}: temp c: {temp_state.curr_c}")
                    last_update = time.time()

            heat_plate_state_msg = parse_heat_plate_state_msg(message, db, conf["can"]["node_addr"], conf["signals"]["heat_plate"]["node_addr"])
            if heat_plate_state_msg is not None:
                print("heat_plate", heat_plate_state_msg)

            motor_state_msg = parse_motor_state_msg(message, db, conf["can"]["node_addr"], conf["signals"]["motor"]["node_addr"])
            if motor_state_msg is not None:
                print("motor", motor_state_msg)

            time.sleep(0.01)

    finally:
        can_bus.shutdown()


if __name__ == "__main__":
    main()
