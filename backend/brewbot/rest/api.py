import asyncio
import can
from fastapi import FastAPI, Query
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from asyncio.tasks import Task
from brewbot.assembly.kettle import KettleAssembly
from brewbot.util import async_infinite_loop, log_exceptions
from brewbot.config import load_config, Config, NodeConfig, BoundMessage
from brewbot.can.msg_registry import MsgRegistry
from brewbot.assembly.assembly import Assembly, gen_assemblies
from brewbot.can.mock import MockState, MockNode, gen_mock_nodes
from brewbot.can.node_state import NodeState, gen_node_states
from typing import Optional, Tuple
from dataclasses import dataclass, field
import logging


# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0
# uvicorn brewbot.rest.api:app --reload


logger = logging.getLogger("brewbot.rest.api")
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_app_state(_app)
    await create_background_tasks(_app)
    yield
    await cancel_background_tasks(_app)


@dataclass
class AppState:
    conf: Optional[Config] = None
    msg_reg: Optional[MsgRegistry] = None
    can_bus: Optional[can.interface.Bus] = None
    mock_msg_queue: list[Tuple[NodeConfig, BoundMessage, dict]] = field(default_factory=lambda: [])
    send_queue: list[Tuple[NodeConfig, BoundMessage, dict]] = field(default_factory=lambda: [])
    tasks: dict = field(default_factory=lambda: {})
    node_states: dict[str, NodeState] = field(default_factory=lambda: {})
    assemblies: dict[str, Assembly] = field(default_factory=lambda: {})
    mock_state: Optional[MockState] = None
    mock_nodes: dict[str, MockNode] = field(default_factory=lambda: {})


app = FastAPI(lifespan=lifespan)
app.state = AppState()


def can_recv_loop_task(app_state: AppState):
    @async_infinite_loop
    async def _task():
        conf: Config = app_state.conf

        if app_state.can_bus is None and conf.can.bus is not None:
            app_state.can_bus = can.interface.Bus(
                conf.can.bus.channel,
                interface=conf.can.bus.interface
            )

        if app_state.can_bus is not None:
            can_message = app_state.can_bus.recv(timeout=conf.can.bus.receive_timeout)

            if can_message is not None:
                decoded_message = app_state.msg_reg.decode(can_message)
                if decoded_message is not None:
                    handle_message(*decoded_message)

        if len(app_state.mock_msg_queue) != 0:
            handle_message(*app_state.mock_msg_queue.pop(0))

        await asyncio.sleep(conf.can.process_interval)

    return _task

def process_send_queue_task(send_queue: list[Tuple[NodeConfig, BoundMessage, dict]], interval: float):
    @async_infinite_loop
    async def _task():
        if len(send_queue) != 0:
            send_message(*send_queue.pop(0))

        await asyncio.sleep(interval)

    return _task

def send_message(node: NodeConfig, msg_def: BoundMessage, msg: dict) -> None:
    conf: Config = app.state.conf
    node = conf.node(node.key)
    msg_def = node.message(msg_def.key)

    if node.debug.get('mock', False):
        node_mock: MockNode = app.state.mock_nodes[node.key]
        node_mock.handle_message(msg_def, msg)
    elif app.state.can_bus is not None:
        bus: can.interface.Bus = app.state.can_bus
        msg_reg: MsgRegistry = app.state.msg_reg
        encoded_message = msg_reg.encode(node.key, msg_def.key, msg)
        bus.send(encoded_message)
    else:
        logger.error(f"target node is not defined as mock and no can bus is defined: {node.key} {msg_def.key}")


def handle_message(node: NodeConfig, msg_def: BoundMessage, msg: dict) -> None:
    node_state = app.state.node_states.get(node.key)

    if node_state is not None:
        node_state.update_rx_state(msg_def, msg)


async def init_app_state(_app: FastAPI):
    app_state = AppState()

    app_state.conf = load_config()
    app_state.msg_reg = MsgRegistry(app_state.conf.nodes)

    app_state.node_states = gen_node_states(app_state.conf)
    app_state.mock_state = MockState(app_state.conf, app_state.node_states)
    app_state.mock_nodes = gen_mock_nodes(app_state.conf, app_state.mock_msg_queue, app_state.mock_state)
    app_state.assemblies = gen_assemblies(app_state.conf, app_state.node_states)

    _app.state = app_state


async def create_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings
    app_state: AppState = _app.state

    app_state.tasks["mock_sources"] = {}
    for node_key, node_mock in  app_state.mock_nodes.items():
        app_state.tasks["mock_sources"][node_key] = log_exceptions(asyncio.create_task(node_mock.queue_messages_task()), f"mock_sources.{node_key}")

    app_state.tasks["queue_tasks"] = {}
    for node_key, node_state in app_state.node_states.items():
        app_state.tasks["queue_tasks"][node_key] = [log_exceptions(asyncio.create_task(task()), f"queue_tasks.node_key[{i}]") for i, task in enumerate(node_state.queue_tasks(app_state.send_queue))]

    app_state.tasks["can_recv"] = log_exceptions(asyncio.create_task(can_recv_loop_task(app_state)()), "can_recv")
    app_state.tasks["simulate_mock_state"] = log_exceptions(asyncio.create_task(app_state.mock_state.simulation_task()), "simulate_mock_state")
    app_state.tasks["process_send_queue"] = log_exceptions(asyncio.create_task(process_send_queue_task(app_state.send_queue, app_state.conf.can.process_interval)()), "process_send_queue")
    app_state.tasks["assemblies"] = {key: [log_exceptions(asyncio.create_task(coro), f"assemblies.{key}[{i}]") for i, coro in enumerate(assembly.background_tasks())] for key, assembly in app_state.assemblies.items()}


def collect_tasks(obj) -> list[Task]:
    tasks = []
    if isinstance(obj, Task):
        tasks.append(obj)
    elif isinstance(obj, dict):
        for item in [_item for _, _item in obj.items()]:
            tasks.extend(collect_tasks(item))
    elif isinstance(obj, list):
        for item in obj:
            tasks.extend(collect_tasks(item))
    else:
        logger.error(f"invalid type in type dict: {type(obj)}")

    return tasks


async def cancel_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings
    app_state: AppState = _app.state

    for task in collect_tasks(app_state.tasks):
        task.cancel()
        await task


@app.get("/kettle/{kettle_name}/temp")
async def get_temp_state_route(kettle_name):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)
    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "get_temp_state",
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "get_temp_state",
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"}
        })
    else:
        return JSONResponse(status_code=200, content={
            "action": "get_temp_state",
            "status": "success",
            "data": kettle.temp_state
        })


@app.get("/kettle/{kettle_name}/heat_plate/{on_off}")
async def set_heat_plate_route(kettle_name, on_off):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)

    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "set_heat_plate",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"},
            "data": {"relay_state": on_off}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "set_heat_plate",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"},
            "data": {"relay_state": on_off}
        })
    else:
        kettle.set_heat_plate(on_off)
        return JSONResponse(status_code=200, content={
            "action": "set_heat_plate",
            "kettle_name": kettle_name,
            "status": "success",
            "data": {"relay_state": on_off}
        })


@app.get("/kettle/{kettle_name}/steering/{on_off}")
async def set_steering_state_route(kettle_name, on_off):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)

    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "set_steering_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"},
            "data": {"relay_state": on_off}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "set_steering_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"},
            "data": {"relay_state": on_off}
        })
    else:
        kettle.set_steering(on_off)
        return JSONResponse(status_code=200, content={
            "action": "set_steering_state",
            "kettle_name": kettle_name,
            "status": "success",
            "data": {"relay_state": on_off}
        })


@app.get("/kettle/{kettle_name}/heat_plate")
async def get_heat_plate_state_route(kettle_name):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)

    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "get_heat_plate_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "get_heat_plate_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"}
        })
    else:
        return JSONResponse(status_code=200, content={
            "action": "get_heat_plate_state",
            "kettle_name": kettle_name,
            "status": "success",
            "data": {kettle.heat_plate_state}
        })


@app.get("/kettle/{kettle_name}/steering")
async def get_steering_state_route(kettle_name):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)

    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "get_steering_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "get_steering_state",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"}
        })
    else:
        return JSONResponse(status_code=200, content={
            "action": "get_steering_state",
            "kettle_name": kettle_name,
            "status": "success",
            "data": kettle.steering_state
        })


@app.get("/kettle/{kettle_name}/temp/set")
async def set_temp_setpoint_route(kettle_name, r: float = Query(None, description="Desired temperature in Celsius")):
    app_state: AppState = app.state
    kettle = app_state.assemblies.get(kettle_name)

    if kettle is None:
        return JSONResponse(status_code=400, content={
            "action": "set_temp_setpoint",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly does not exist: {kettle}"}
        })
    elif not isinstance(kettle, KettleAssembly):
        return JSONResponse(status_code=400, content={
            "action": "set_temp_setpoint",
            "kettle_name": kettle_name,
            "status": "error",
            "error": {"code": 400, "msg": f"assembly is not a kettle: {kettle}"}
        })
    else:
        kettle.set_heat_plate_setpoint(r)

        return JSONResponse(status_code=200, content={
            "action": "set_temp_setpoint",
            "kettle_name": kettle_name,
            "status": "success",
            "data": {"temp": kettle.heat_plate_setpoint}
        })
