import asyncio
import time
from brewbot.config import Config
from brewbot.can.node_state import NodeState, MasterNodeState, RelayNodeState, ThermometerNodeState
from brewbot.util import async_infinite_loop, avg_dict
from brewbot.data.pid import calculate_pd_error, duty_cycle


class HeatPlateController:
    conf: Config
    node_states: dict[str, NodeState]

    def __init__(self, conf: Config, node_states: dict[str, NodeState]):
        self.conf = conf
        self.node_states = node_states

    @property
    def temp_setpoint(self):
        node_state = self.node_states['master']
        if isinstance(node_state, MasterNodeState):
            return node_state.heat_plate_setpoint
        else:
            raise ValueError("invalid master node state")

    def set_heat_plate(self, on_off):
        node_state: NodeState = self.node_states['heat_plate_1']
        if isinstance(node_state, RelayNodeState):
            node_state.cmd_state = on_off
        else:
            raise ValueError("heat plate is not a relay")

    def temp_state(self):
        states = [
            node_state
            for node_state in self.node_states.values()
            if node_state.node_conf.node_type == "thermometer" and isinstance(node_state, ThermometerNodeState)
        ]
        return avg_dict([state.temp_state() for state in states])

    @async_infinite_loop
    async def control_heat_plate(self):
        pwm_interval = self.conf.signals.temp.controller.pwm_interval

        temp_setpoint = self.temp_setpoint
        if temp_setpoint is None:
            dc = 0.0
        else:
            dc = self.calc_duty_cycle(temp_setpoint)

        low_jump_thres = self.conf.signals.temp.controller.low_jump_thres
        high_jump_thres = self.conf.signals.temp.controller.high_jump_thres

        eps = 1e-6
        if dc < (low_jump_thres - eps):
            self.set_heat_plate("off")
            await asyncio.sleep(pwm_interval)
        elif (low_jump_thres - eps) <= dc <= (high_jump_thres + eps):
            self.set_heat_plate("on")
            await asyncio.sleep(pwm_interval * dc)
            self.set_heat_plate("off")
            await asyncio.sleep(pwm_interval * (1.0 - dc))
        elif dc > (high_jump_thres + eps):
            self.set_heat_plate("on")
            await asyncio.sleep(pwm_interval)
        else:
            raise ValueError("invalid value for duty cycle")

    def calc_duty_cycle(self, temp_setpoint):
        df = self.temp_state()["temp_c"].df
        window = self.conf.signals.temp.window
        p, d = calculate_pd_error(temp_setpoint, df, time.time(), window)
        p_gain = self.conf.signals.temp.controller.p_gain
        d_gain = self.conf.signals.temp.controller.d_gain
        cs = p * p_gain + d * d_gain

        print(f"p-comp: {p * p_gain: 4.2f}  ==  d-comp: {d * d_gain: 4.2f}  ==  cs: {cs: 4.2f}")

        max_cs = self.conf.signals.temp.controller.max_cs
        low_jump_thres = self.conf.signals.temp.controller.low_jump_thres
        high_jump_thres = self.conf.signals.temp.controller.high_jump_thres

        return duty_cycle(cs, max_cs, low_jump_thres, high_jump_thres)
