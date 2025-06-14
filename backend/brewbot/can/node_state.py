import pandas as pd
import asyncio
from brewbot.config import Config, NodeConfig, BoundMessage
from brewbot.data.df import WindowedDataFrame
from brewbot.util import format_on_off, load_object
import time
import numpy as np
from typing import Optional, Callable, Tuple


class NodeState:
    conf: Config
    node_conf: NodeConfig
    rx_message_state: dict[str, Optional[dict]]
    rx_message_handler: dict[str, list[Callable[[dict], None]]]

    def __init__(self, conf: Config, node_conf: NodeConfig):
        self.conf = conf
        self.node_conf = node_conf
        self.rx_message_state = {msg.key: None for msg in node_conf.messages if msg.direction == "rx"}
        self.rx_message_handler = {msg.key: [] for msg in node_conf.messages if msg.direction == "rx"}

    def update_rx_state(self, msg_def: BoundMessage | str, msg: dict) -> None:
        if isinstance(msg_def, BoundMessage):
            msg_key = msg_def.key
        else:
            msg_key = msg_def

        if msg_key not in self.rx_message_state:
            raise ValueError("Invalid message")

        self.rx_message_state[msg_key] = msg
        for handler in self.rx_message_handler[msg_key]:
            handler(msg)

    def register_rx_message_handler(self, msg_def: BoundMessage | str, handler: Callable[[dict], None]):
        if isinstance(msg_def, BoundMessage):
            msg_key = msg_def.key
        else:
            msg_key = msg_def

        if msg_key not in self.rx_message_handler:
            raise ValueError("Invalid message")

        self.rx_message_handler[msg_key].append(handler)

    def queue_tasks(self, send_queue: list[Tuple[NodeConfig, BoundMessage, dict]]):
        tasks = []
        for msg_def in [msg_def for msg_def in self.node_conf.messages if msg_def.direction == "tx" and msg_def.frequency is not None]:
            async def _task():
                while True:
                    try:
                        send_queue.append((self.node_conf, msg_def, self.tx_msg(msg_def)))
                        await asyncio.sleep(1.0 / msg_def.frequency)
                    except asyncio.CancelledError:
                        break
            tasks.append(_task)

        return tasks

    def tx_msg(self, msg_def: BoundMessage) -> dict:
        ...


class ThermometerNodeState(NodeState):
    conf: Config
    node_conf: NodeConfig
    window: float
    temp_c_frame: WindowedDataFrame
    temp_v_frame: WindowedDataFrame

    def __init__(self, conf: Config, node_conf: NodeConfig):
        super().__init__(conf, node_conf)
        self.window = conf.signals.temp.window
        self.temp_c_frame = WindowedDataFrame(self.window, columns=["t", "y"], index_column="t")
        self.temp_v_frame = WindowedDataFrame(self.window, columns=["t", "y"], index_column="t")
        self.register_rx_message_handler("temp_state", self.temp_msg_update)

    def temp_msg_update(self, msg: dict) -> None:
        self.temp_c_frame.append({"t": [time.time()], "y": [msg['temp_c']]})
        self.temp_v_frame.append({"t": [time.time()], "y": [msg['temp_v']]})

    def temp_state(self) -> dict:
        temp_c = ThermometerNodeState.interp(self.temp_c_frame.df, time.time(), self.window)
        temp_v = ThermometerNodeState.interp(self.temp_v_frame.df, time.time(), self.window)

        return {
            "temp_c": temp_c,
            "temp_v": temp_v
        }

    @classmethod
    def interp(cls, df: pd.DataFrame, current_time: float, window: float):
        if len(df) == 0:
            return float("nan")

        filtered_data = df.loc[(current_time - window):current_time]

        if len(filtered_data) == 0:
            return float("nan")
        elif len(filtered_data) == 1:
            return float(filtered_data.iloc[0]["y"])
        else:
            poly = np.polyfit(filtered_data.index.to_numpy(), filtered_data['y'].to_numpy(), 1)
            return float(np.polyval(poly, current_time))


class RelayNodeState(NodeState):
    conf: Config
    node_conf: NodeConfig
    cmd_state: bool

    def __init__(self, conf: Config, node_conf: NodeConfig):
        super().__init__(conf, node_conf)
        self.cmd_state = False

    def tx_msg(self, msg_def: BoundMessage) -> dict:
        if msg_def.key == "relay_cmd":
            return {'on': format_on_off(self.cmd_state)}
        else:
            raise ValueError("Invalid message")


class MasterNodeState(NodeState):
    conf: Config
    node_conf: NodeConfig
    heat_plate_setpoint: Optional[float]

    def __init__(self, conf: Config, node_conf: NodeConfig):
        super().__init__(conf, node_conf)
        self.heat_plate_setpoint = None


def gen_node_states(conf: Config) -> dict[str, NodeState]:
    node_states = {}
    for node in conf.nodes:
        if node.node_state_class is not None:
            node_state_class = load_object(node.node_state_class)
            node_states[node.key] = node_state_class(conf, node)

    return node_states
