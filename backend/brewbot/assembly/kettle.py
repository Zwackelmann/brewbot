from brewbot.can.node_state import NodeState, ThermometerNodeState, RelayNodeState
from brewbot.config import NodeConfig, AssemblyConfig
from brewbot.assembly.assembly import Assembly
from brewbot.util import avg_dict, parse_on_off
from typing import Any


class KettleAssembly(Assembly):
    tpe_name: str
    key: str

    def __init__(self, key: str, thermometers: list[ThermometerNodeState], steering: RelayNodeState, heat_plate: RelayNodeState, volume: float):
        self.tpe_name = "kettle"
        self.key = key
        self.thermometers = thermometers
        self.steering = steering
        self.heat_plate = heat_plate
        self.volume = volume
        self.heat_plate_setpoint = None

    def temp_state(self) -> dict[str, float]:
        return avg_dict([t.temp_state() for t in self.thermometers])

    def heat_plate_state(self):
        return self.heat_plate.rx_message_state

    def set_heat_plate(self, on_off: Any):
        self.heat_plate.cmd_state = parse_on_off(on_off)

    def steering_state(self):
        return self.steering.rx_message_state

    def set_steering(self, on_off: Any):
        self.steering.cmd_state = parse_on_off(on_off)

    def set_heat_plate_setpoint(self, r: float):
        self.heat_plate_setpoint = r

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

        volume = conf.params['volume']
        return KettleAssembly(conf.key, thermometers, motor, heat_plate, volume)
