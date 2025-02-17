from brewbot.can.util import load_can_database
from brewbot.can.messages import parse_temp_state_msg
from brewbot.config import load_config
import can


class CanTempReader:
    def __init__(self, node_name):
        self.conf = load_config()
        self.dbc = load_can_database(self.conf["can"]["dbc_file"])
        self.bus = can.interface.Bus(self.conf["can"]["channel"], interface=self.conf["can"]["interface"])

        self.receive_timeout = self.conf["can"]["receive_timeout"]
        self.master_node_addr = self.conf["can"]["node_addr"]
        self.node_addr = self.conf["signals"]["temp"]["nodes"][node_name]["node_addr"]
        self.msg_name = self.conf["signals"]["temp"]["nodes"][node_name]["msg_name"]

        self.dbc = load_can_database(self.conf["can"]["dbc_file"])

    def recv(self):
        message = self.bus.recv(timeout=self.receive_timeout)

        if message is not None:
            return parse_temp_state_msg(message, self.dbc, self.msg_name, self.master_node_addr, self.node_addr)
        else:
            return None
