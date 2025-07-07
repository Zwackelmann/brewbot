import asyncio
from brewbot.util import load_object
from brewbot.config import CanEnvConfig, NodeConfig, BoundMessage
from brewbot.can.node_state import NodeState
import random
from typing import Protocol, Tuple


class MockNode(Protocol):
    async def queue_messages_coro(self) -> None:
        ...

    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        ...


class MockThermometer(MockNode):
    conf: CanEnvConfig
    node_conf: NodeConfig
    msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]]
    mock_state: "MockState"
    msg_interval: float

    error_mu: float
    error_sigma: float

    v_to_temp_m: float
    v_to_temp_b: float

    def __init__(self, conf: CanEnvConfig, node_conf: NodeConfig, msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]], mock_state: "MockState"):
        self.conf = conf
        self.node_conf = node_conf
        self.msg_queue = msg_queue
        self.mock_state = mock_state
        self.msg_interval = 0.1

        self.error_mu = 0.0
        self.error_sigma = 0.2

        self.v_to_temp_m = 23.69448038
        self.v_to_temp_b = -4.59983094

    def measure_error(self) -> float:
        return random.gauss(self.error_mu, self.error_sigma)

    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        raise ValueError("invalid message")

    async def queue_messages_coro(self):
        while True:
            try:
                temp_c = self.mock_state.temp + self.measure_error()
                temp_v = (temp_c - self.v_to_temp_b) / self.v_to_temp_m

                msg_def = self.node_conf.message('temp_state')
                msg = {'temp_v': temp_v, 'temp_c': temp_c}
                self.msg_queue.append((self.node_conf, msg_def, msg))

                await asyncio.sleep(self.msg_interval)
            except asyncio.CancelledError:
                break


class MockRelay(MockNode):
    conf: CanEnvConfig
    node_conf: NodeConfig
    msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]]
    mock_state: "MockState"
    msg_interval: float
    relay_state: dict

    def __init__(self, conf: CanEnvConfig, node_conf: NodeConfig, msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]], mock_state: "MockState"):
        self.conf = conf
        self.node_conf = node_conf
        self.msg_queue = msg_queue
        self.mock_state = mock_state
        self.msg_interval = 0.1

        self.relay_state = {'on': False}

    def handle_message(self, msg_def: BoundMessage, msg: dict) -> None:
        if msg_def.key == 'relay_cmd':
            self.relay_state = msg
        else:
            raise ValueError("invalid message")

    async def queue_messages_coro(self):
        while True:
            try:
                msg_def = self.node_conf.message('relay_state')
                self.msg_queue.append((self.node_conf, msg_def, self.relay_state))
                await asyncio.sleep(self.msg_interval)
            except asyncio.CancelledError:
                break


class MockState:
    def __init__(self, conf: CanEnvConfig, node_states: dict[str, NodeState]):
        self.temp = 20.0
        self.effective_power = 0.0
        self.p_on = 5000   # power heat plate is on (W)
        self.water_amount = 20.0  # amount of water (l)
        self.water_heat_capacity = 4186  # (constant) heat capacity of water (J/kg)
        self.tau = 2.0  # time constant for inertia (s)
        self.conf = conf
        self.node_states = node_states

        self.ambient = 20  # ambient temperature (C)
        self.k = self.p_on / (100 - self.ambient)  # heat loss coefficient (Watts per °C difference)

        self.simulation_interval = 0.1

    def simulate(self, dt: float) -> None:
        heat_plate_state = self.node_states['heat_plate_1']

        relay_state = heat_plate_state.rx_message_state.get('relay_state')
        heating = relay_state.get('on', False) if relay_state is not None else False
        target_power = self.p_on if heating else 0.0
        self.effective_power += (target_power - self.effective_power) * dt / self.tau

        temp_diff = (self.effective_power - self.k * (self.temp - self.ambient)) * dt / (self.water_amount * self.water_heat_capacity)

        self.temp += temp_diff

    async def simulation_coro(self):
        while True:
            try:
                self.simulate(self.simulation_interval)
                await asyncio.sleep(self.simulation_interval)
            except asyncio.CancelledError:
                break


def gen_mock_nodes(conf: CanEnvConfig, msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]], mock_state: MockState) -> dict[str, MockNode]:
    mock_nodes = {}
    for node in conf.nodes:
        if node.debug.get('mock', False):
            mock_class = load_object(node.mock_class)
            mock_nodes[node.key] = mock_class(conf, node, msg_queue, mock_state)

    return mock_nodes
