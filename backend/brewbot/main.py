from brewbot.config import load_config
from brewbot.can.messages import MsgRegistry
import can
import time

def main():
    config = load_config()
    msg_reg = MsgRegistry(config.nodes)

    bus = can.interface.Bus(config.can.channel, interface=config.can.interface)

    while True:
        msg = bus.recv(timeout=config.can.receive_timeout)

        if msg is not None:
            parsed_msg = msg_reg.decode(msg)
            print(parsed_msg)

        bus.send(msg_reg.encode('heat_plate_1', 'relay_cmd', {'on': False}))

        time.sleep(0.1)


if __name__ == "__main__":
    main()
