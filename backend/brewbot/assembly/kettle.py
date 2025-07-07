from brewbot.can.node_state import NodeState, ThermometerNodeState, RelayNodeState
from brewbot.config import NodeConfig, AssemblyConfig, ControllerConfig, DataCollectConfig
from brewbot.assembly.assembly import Assembly
from brewbot.data.df import WindowedDataFrame
from brewbot.util import parse_on_off, async_infinite_loop, avg_dict
from brewbot.data.pid import calculate_pd_error, duty_cycle
from typing import Any, Coroutine
import asyncio
import time
import numpy as np
import logging
from cysystemd import journal


logger = logging.getLogger("brewbot.assembly.kettle")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():  # Prevent duplicate logs if already configured
    handler = journal.JournaldLogHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class KettleAssembly(Assembly):
    tpe_name: str
    key: str

    def __init__(self, key: str, thermometers: list[ThermometerNodeState], steering: RelayNodeState, heat_plate: RelayNodeState, volume: float, controller_conf: ControllerConfig, data_collect_conf: DataCollectConfig):
        self.tpe_name = "kettle"
        self.key = key
        self.thermometers = thermometers
        self.steering = steering
        self.heat_plate = heat_plate
        self.volume = volume
        self.controller_conf = controller_conf
        self.data_collect_conf = data_collect_conf

        self.heat_plate_setpoint = None
        self.temp_df = WindowedDataFrame(data_collect_conf.window, columns=["t", "y"], index_column="t")

    @property
    def temp_state(self) -> dict[str, float]:
        return avg_dict([t.temp_state() for t in self.thermometers])

    @property
    def heat_plate_state(self):
        return self.heat_plate.rx_message_state

    def set_heat_plate(self, on_off: Any):
        self.heat_plate.cmd_state = parse_on_off(on_off)

    @property
    def steering_state(self):
        return self.steering.rx_message_state

    def set_steering(self, on_off: Any):
        self.steering.cmd_state = parse_on_off(on_off)

    def set_heat_plate_setpoint(self, r: float):
        self.heat_plate_setpoint = r

    @async_infinite_loop
    async def collect_data(self):
        temp_c = self.temp_state.get("temp_c")
        if temp_c is not None:
            self.temp_df.append({"t": [time.time()], "y": [temp_c]})

        await asyncio.sleep(1.0 / self.data_collect_conf.collect_interval)

    @async_infinite_loop
    async def control_heat_plate(self):
        pwm_interval = self.controller_conf.pwm_interval
        interval_time = 1.0 / pwm_interval

        temp_setpoint = self.heat_plate_setpoint
        if temp_setpoint is None:
            dc = float("nan")
        else:
            dc = self.calc_duty_cycle(temp_setpoint)

        low_jump_thres = self.controller_conf.low_jump_thres
        high_jump_thres = self.controller_conf.high_jump_thres

        eps = 1e-6
        if np.isnan(dc):
            logger.info("nan dc -> don't control")
            await asyncio.sleep(interval_time)
        elif dc < (low_jump_thres - eps):
            logger.info("dc < low_jump_tres -> set heat plate off")
            self.set_heat_plate("off")
            await asyncio.sleep(interval_time)
        elif (low_jump_thres - eps) <= dc <= (high_jump_thres + eps):
            logger.info(f"dc in pwm range -> on: {interval_time * dc} - off: {interval_time * (1.0 - dc)}")
            self.set_heat_plate("on")
            await asyncio.sleep(interval_time * dc)
            self.set_heat_plate("off")
            await asyncio.sleep(interval_time * (1.0 - dc))
        elif dc > (high_jump_thres + eps):
            logger.info("dc > high_jump_thres -> set heat plate on")
            self.set_heat_plate("on")
            await asyncio.sleep(interval_time)
        else:
            raise ValueError("invalid value for duty cycle")

    def calc_duty_cycle(self, temp_setpoint: float) -> float:
        window = self.data_collect_conf.window
        p, d = calculate_pd_error(temp_setpoint, self.temp_df.df, time.time(), window)
        p_gain = self.controller_conf.p_gain
        d_gain = self.controller_conf.d_gain
        cs = p * p_gain + d * d_gain

        logger.info(f"temp: {self.temp_state.get("temp_c"):4.2f}")
        logger.info(f"p-comp: {p * p_gain: 4.2f}  ==  d-comp: {d * d_gain: 4.2f}  ==  cs: {cs: 4.2f}")

        max_cs = self.controller_conf.max_cs
        low_jump_thres = self.controller_conf.low_jump_thres
        high_jump_thres = self.controller_conf.high_jump_thres

        return duty_cycle(cs, max_cs, low_jump_thres, high_jump_thres)

    def coros(self) -> list[Coroutine]:
        return [self.collect_data(), self.control_heat_plate()]

    @classmethod
    def from_config(cls, conf: AssemblyConfig, node_states: dict[str, NodeState]):
        thermometers = []
        for temp_node in conf.nodes["thermometer"]:
            if isinstance(temp_node, NodeConfig):
                thermometers.append(node_states[temp_node.key])
            else:
                raise ValueError(f"Unexpected type: {type(temp_node)}")

        motor_node = conf.nodes["motor"]
        if isinstance(motor_node, NodeConfig):
            motor = node_states[motor_node.key]
            if not isinstance(motor, RelayNodeState):
                raise ValueError(f"Unexpected type: {type(motor)}")
        else:
            raise ValueError(f"Unexpected type: {type(motor_node)}")

        heat_plate_node = conf.nodes["heat_plate"]
        if isinstance(heat_plate_node, NodeConfig):
            heat_plate = node_states[heat_plate_node.key]
            if not isinstance(heat_plate, RelayNodeState):
                raise ValueError(f"Unexpected type: {type(heat_plate)}")
        else:
            raise ValueError(f"Unexpected type: {type(heat_plate_node)}")

        volume = conf.parsed_param['volume']
        if not isinstance(volume, float):
            raise ValueError("kettle volume must be a float")

        controller_conf = conf.parsed_param['controller']
        if not isinstance(controller_conf, ControllerConfig):
            raise ValueError("kettle control config must be a `ControllerConfig`")

        data_collect_conf = conf.parsed_param['data_collect']
        if not isinstance(data_collect_conf, DataCollectConfig):
            raise ValueError("kettle data collect config must be a `DataCollectConfig`")

        return KettleAssembly(conf.key, thermometers, motor, heat_plate, volume, controller_conf, data_collect_conf)
