import pandas as pd

from brewbot.config import Config, Node, BoundMessage
from brewbot.data.df import WindowedDataFrame
import time
import numpy as np
from typing import Protocol


class NodeState(Protocol):
    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        ...

    def state(self) -> dict:
        ...


class ThermometerNodeState(NodeState):
    conf: Config
    node: Node
    window: float
    temp_c_frame: WindowedDataFrame
    temp_v_frame: WindowedDataFrame

    def __init__(self, conf: Config, node: Node):
        self.conf = conf
        self.node = node
        self.window = conf.signals.temp.window
        self.temp_c_frame = WindowedDataFrame(self.window, columns=["t", "y"], index_column=["t"])
        self.temp_v_frame = WindowedDataFrame(self.window, columns=["t", "y"], index_column=["t"])

    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        if msg_def.key == "temp_state":
            self.temp_c_frame.append({"t": [time.time()], "y": [msg['temp_c']]})
            self.temp_v_frame.append({"t": [time.time()], "y": [msg['temp_v']]})
        else:
            raise ValueError("Invalid message")

    def state(self) -> dict:
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
    node: Node
    relay_state: dict

    def __init__(self, conf: Config, node: Node):
        self.conf = conf
        self.node = node
        self.relay_state = {}

    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        if msg_def.key == 'relay_state':
            self.relay_state = msg
        else:
            raise ValueError("Invalid message")

    def state(self) -> dict:
        return self.relay_state
