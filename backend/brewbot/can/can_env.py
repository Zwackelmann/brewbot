from typing import Tuple, Coroutine, Optional
import asyncio
import logging
from asyncio.tasks import Task
from brewbot.can.mock import MockNode, MockState, gen_mock_nodes
from brewbot.can.node_state import NodeState, gen_node_states
from brewbot.config import CanEnvConfig, NodeConfig, BoundMessage
from brewbot.assembly.assembly import Assembly, gen_assemblies
from brewbot.util import async_infinite_loop, log_exceptions, collect_tasks
from brewbot.can.can_port import CanPort
from cysystemd import journal
from brewbot.can.msg_registry import MsgRegistry


logger = logging.getLogger("brewbot.can.can_env")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():  # Prevent duplicate logs if already configured
    handler = journal.JournaldLogHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CanEnv:
    conf: CanEnvConfig
    can_port: CanPort
    send_queue: list[Tuple[NodeConfig, BoundMessage, dict]]

    msg_reg: MsgRegistry
    node_states: dict[str, NodeState]
    assemblies: dict[str, Assembly]

    mock_nodes: dict[str, MockNode]
    mock_state: MockState
    mock_msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]]

    main_queue: list[Coroutine]
    main_task: Optional[Task]
    connect_can_task: Optional[Task]
    tasks: dict

    def __init__(self, conf: CanEnvConfig):
        self.conf = conf

        self.msg_reg = MsgRegistry(conf.nodes)
        self.can_port = CanPort(conf.port)
        self.can_port.event_handlers.append(self.can_port_event_handler)

        self.main_queue = []
        self.main_task = None
        self.connect_can_task = None

        self.reset_state()

    def reset_state(self):
        self.assemblies = {}
        self.send_queue = []
        self.node_states = {}
        self.mock_msg_queue = []

        self.tasks = {
            "mock_sources": {},
            "queue_tasks": {},
            "assemblies": {},
            "connect_can": None,
            "handle_node_messages": None,
            "process_send_queue": None
        }

    def setup_nodes(self):
        self.send_queue = []
        self.node_states = gen_node_states(self.conf)

    def setup_mock_state(self):
        self.mock_msg_queue = []
        self.mock_state = MockState(self.conf, self.node_states)
        self.mock_nodes = gen_mock_nodes(self.conf, self.mock_msg_queue, self.mock_state)

    def setup_assemblies(self):
        self.assemblies = gen_assemblies(self.conf.assemblies, self.node_states)

    async def cancel_tasks(self):
        task_list = collect_tasks(self.tasks)

        for task in task_list:
            task.cancel()

        for task in task_list:
            await task

        if all([task.done() for task in self.tasks.get('mock_sources', {}).values()]):
            self.tasks['mock_sources'] = {}
        else:
            raise ValueError("Error during task reset: awaited task not done")

        if all([all([task.done() for task in tasks]) for tasks in self.tasks.get('queue_tasks', {}).values()]):
            self.tasks['queue_tasks'] = {}
        else:
            raise ValueError("Error during task reset: awaited task not done")

        if all([all([task.done() for task in tasks]) for tasks in self.tasks.get('assemblies', {}).values()]):
            self.tasks['assemblies'] = {}
        else:
            raise ValueError("Error during task reset: awaited task not done")

        for key in ["connect_can", "handle_node_messages", "process_send_queue"]:
            if key not in self.tasks or self.tasks[key] is None:
                pass
            elif self.tasks[key].done():
                self.tasks[key] = None
            else:
                raise ValueError("Error during task reset: awaited task not done")

    async def startup_coro(self):
        self.setup_nodes()
        self.setup_mock_state()
        self.setup_assemblies()
        self.create_background_tasks()

    async def shutdown_coro(self):
        await self.cancel_tasks()
        self.reset_state()

    def can_port_event_handler(self, evt: str):
        # evt is either 'connected' when a new can bus connection was established and 'shutdown' when the connection was shut down

        if evt == 'connected':
            self.main_queue.append(self.startup_coro())
        elif evt == 'shutdown':
            self.main_queue.append(self.shutdown_coro())

    def receive_node_message(self):
        msg = self.can_port.recv()
        if msg is None:
            return None

        return self.msg_reg.decode(msg)

    def handle_message(self, node: NodeConfig, msg_def: BoundMessage, msg: dict) -> None:
        node_state = self.node_states.get(node.key)

        if node_state is not None:
            node_state.update_rx_state(msg_def, msg)

    def send_message(self, node: NodeConfig, msg_def: BoundMessage, msg: dict) -> None:
        msg_def = node.message(msg_def.key)

        if node.debug.get('mock', False):
            self.mock_nodes[node.key].handle_message(msg_def, msg)
        else:
            encoded_message = self.msg_reg.encode(node.key, msg_def.key, msg)
            self.can_port.send(encoded_message)

    @async_infinite_loop
    async def handle_node_messages_coro(self):
        node_msg = self.receive_node_message()

        if node_msg  is not None:
            self.handle_message(*node_msg)
        elif len(self.mock_msg_queue) != 0:
            self.handle_message(*self.mock_msg_queue.pop(0))

        await asyncio.sleep(self.conf.port.process_interval)

    @async_infinite_loop
    async def process_send_queue_coro(self):
        if len(self.send_queue) != 0:
            self.send_message(*self.send_queue.pop(0))

        await asyncio.sleep(self.conf.port.process_interval)

    async def process_main_queue_coro(self):
        async def process_main_queue():
            while len(self.main_queue) != 0:
                await self.main_queue.pop(0)

        try:
            while True:
                await process_main_queue()
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            await process_main_queue()
            await self.cancel_tasks()
            self.reset_state()


    def create_background_tasks(self):
        for node_key, node_mock in  self.mock_nodes.items():
            self.tasks["mock_sources"][node_key] = log_exceptions(asyncio.create_task(node_mock.queue_messages_coro()), f"mock_sources.{node_key}")

        for node_key, node_state in self.node_states.items():
            self.tasks["queue_tasks"][node_key] = [log_exceptions(asyncio.create_task(coro()), f"queue_tasks.node_key[{i}]") for i, coro in enumerate(node_state.queue_coros(self.send_queue))]

        self.tasks["handle_node_messages"] = log_exceptions(asyncio.create_task(self.handle_node_messages_coro()), "handle_node_messages")
        self.tasks["process_send_queue"] = log_exceptions(asyncio.create_task(self.process_send_queue_coro()), "process_send_queue")
        # app_state.tasks["simulate_mock_state"] = log_exceptions(asyncio.create_task(app_state.can_port.mock_state.simulation_task()), "simulate_mock_state")
        self.tasks["assemblies"] = {key: [log_exceptions(asyncio.create_task(coro), f"assemblies.{key}[{i}]") for i, coro in enumerate(assembly.coros())] for key, assembly in self.assemblies.items()}

    def run(self):
        if self.main_task is None:
            self.main_task = log_exceptions(asyncio.create_task(self.process_main_queue_coro()))

        if self.connect_can_task is None:
            self.connect_can_task = log_exceptions(asyncio.create_task(self.can_port.connect_can_coro()))

    async def stop(self):
        if self.connect_can_task is not None:
            self.connect_can_task.cancel()
            await self.connect_can_task
            self.connect_can_task = None

        if self.main_task is not None:
            self.main_task.cancel()
            await self.main_task
            self.main_task = None