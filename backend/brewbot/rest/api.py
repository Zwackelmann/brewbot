import asyncio
import can
import time
from fastapi import FastAPI, Query
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from asyncio.tasks import Task
from brewbot.data.pid import calculate_pd_error, duty_cycle
from brewbot.util import parse_on_off, async_infinite_loop, load_object, avg_dict
from brewbot.config import load_config, Config, Node, BoundMessage
from brewbot.can.msg_registry import MsgRegistry
from brewbot.can.mock import MockState, MockNode

# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0
# uvicorn brewbot.rest.api:app --reload


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await read_config(_app)
    await create_background_tasks(_app)
    yield
    await cancel_background_tasks(_app)


app = FastAPI(lifespan=lifespan)
app.state = app.state  # for IDE, since accessing `app.state` yielded warnings


@async_infinite_loop
async def can_recv_loop():
    conf: Config = app.state.conf

    if app.state.can_bus is None and conf.can.bus is not None:
        app.state.can_bus = can.interface.Bus(
            conf.can.bus.channel,
            interface=conf.can.bus.interface
        )

    if app.state.can_bus is not None:
        can_message = app.state.can_bus.recv(timeout=conf.can.bus.receive_timeout)

        if can_message is not None:
            decoded_message = app.state.msg_reg.decode(can_message)
            if decoded_message is not None:
                handle_message(*decoded_message)

    if len(app.state.mock_msg_queue) != 0:
        handle_message(*app.state.mock_msg_queue.pop(0))

    await asyncio.sleep(conf.can.process_interval)


def calc_duty_cycle(temp_setpoint):
    df = app.state.signal_values["temp"]["temp_c"].df
    window = app.state.conf["signals"]["temp"]["window"]
    p, d = calculate_pd_error(temp_setpoint, df, time.time(), window)
    p_gain = app.state.conf["control"]["temp"]["p_gain"]
    d_gain = app.state.conf["control"]["temp"]["d_gain"]
    cs = p * p_gain + d * d_gain

    print(f"p-comp: {p * p_gain: 4.2f}  ==  d-comp: {d * d_gain: 4.2f}  ==  cs: {cs: 4.2f}")

    max_cs = app.state.conf["control"]["temp"]["max_cs"]
    low_jump_thres = app.state.conf["control"]["temp"]["low_jump_thres"]
    high_jump_thres = app.state.conf["control"]["temp"]["high_jump_thres"]

    return duty_cycle(cs, max_cs, low_jump_thres, high_jump_thres)


@async_infinite_loop
async def control_heat_plate():
    pwm_interval = app.state.conf["control"]["temp"]["pwm_interval"]
    temp_setpoint = app.state.setpoint["temp"]

    if temp_setpoint is None:
        dc = 0.0
    else:
        dc = calc_duty_cycle(temp_setpoint)

    low_jump_thres = app.state.conf["control"]["temp"]["low_jump_thres"]
    high_jump_thres = app.state.conf["control"]["temp"]["high_jump_thres"]

    eps = 1e-6
    if dc < (low_jump_thres - eps):
        set_heat_plate("off")
        await asyncio.sleep(pwm_interval)
    elif (low_jump_thres - eps) <= dc <= (high_jump_thres + eps):
        set_heat_plate("on")
        await asyncio.sleep(pwm_interval * dc)
        set_heat_plate("off")
        await asyncio.sleep(pwm_interval * (1.0 - dc))
    elif dc > (high_jump_thres + eps):
        set_heat_plate("on")
        await asyncio.sleep(pwm_interval)
    else:
        raise ValueError("invalid value for duty cycle")


def send_message(node_key: str, msg_key: str, msg: dict):
    conf: Config = app.state.conf
    node = conf.node(node_key)
    msg_def = node.message(msg_key)

    if node.debug.get('mock', False):
        node_mock: MockNode = app.state.mock_nodes[node_key]
        node_mock.handle_message(msg_def, msg)
    elif app.state.bus is not None:
        bus: can.interface.Bus = app.state.bus
        msg_reg: MsgRegistry = app.state.msg_reg
        encoded_message = msg_reg.encode(node_key, msg_key, msg)
        bus.send(encoded_message)
    else:
        print(f"target node is not defined as mock and no can bus is defined: {node_key} {msg_key}")


def handle_message(node: Node, msg_def: BoundMessage, msg: dict):
    node_state = app.state.node_states.get(node.key)

    if node_state is not None:
        node_state.handle_message(msg_def, msg)


async def read_config(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    conf = load_config()
    _app.state.conf = conf
    _app.state.msg_reg = MsgRegistry(_app.state.conf.nodes)
    _app.state.can_bus = None
    _app.state.mock_msg_queue = []
    _app.state.send_queue = []
    _app.state.tasks = {"can_recv": None, "mock_sources": {}}

    _app.state.node_states = gen_node_states(conf)
    _app.state.mock_state = MockState(conf, _app.state.node_states)
    _app.state.mock_nodes = gen_mock_nodes(conf, _app.state.mock_msg_queue, _app.state.mock_state)


def gen_node_states(conf: Config):
    node_states = {}
    for node in conf.nodes:
        if node.node_state_class is not None:
            node_state_class = load_object(node.node_state_class)
            node_states[node.key] = node_state_class(conf, node)

    return node_states


def gen_mock_nodes(conf: Config, msg_queue: list[(Node, BoundMessage, dict)], mock_state: MockState) -> dict[str, MockNode]:
    mock_nodes = {}
    for node in conf.nodes:
        if node.debug.get('mock', False):
            mock_class = load_object(node.mock_class)
            mock_nodes[node.key] = mock_class(conf, node, msg_queue, mock_state)

    return mock_nodes


async def create_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    for node_key, node_mock in  _app.state.mock_nodes.items():
        mock_source_task = asyncio.create_task(node_mock.queue_messages())
        _app.state.tasks["mock_sources"][node_key] = mock_source_task

    _app.state.tasks["can_recv"] = asyncio.create_task(can_recv_loop())
    _app.state.tasks["simulate_mock_state"] = asyncio.create_task(_app.state.mock_state.simulation_task())
    # _app.state.tasks["control_heat_plate"] = asyncio.create_task(control_heat_plate())
    # _app.state.tasks["print_temp"] = asyncio.create_task(print_temp())


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
        print(f"invalid type in type dict: {type(obj)}")

    return tasks


async def cancel_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    for task in collect_tasks(app.state.tasks):
        task.cancel()
        await task


@app.get("/temp")
async def get_temp():
    nodes = app.state.msg_reg.nodes_by_type("thermometer")
    states = [app.state.node_states[node.key].state() for node in nodes]

    return {
        "action": "get_temp",
        "status": "success",
        "data": avg_dict(states)
    }


def set_motor(on_off):
    send_message('motor_1', 'relay_cmd', {'on': on_off})


@app.get("/motor/{on_off}")
async def set_motor_route(on_off):
    try:
        set_motor(parse_on_off(on_off))
    except ValueError as ex:
        return JSONResponse(status_code=400, content={
            "action": "set_motor",
            "success": False,
            "error": {"code": 400, "msg": str(ex)},
            "data": {"relay_state": on_off}
        })

    return {
        "action": "set_motor",
        "status": "success",
        "data": {"relay_state": on_off}
    }


@app.get("/motor")
async def get_motor_state():
    node_state = app.state.node_states['motor_1']
    return {
        "action": "get_motor",
        "status": "success",
        "data": node_state.state()
    }


def set_heat_plate(on_off):
    send_message('heat_plate_1', 'relay_cmd', {'on': on_off})


@app.get("/heat_plate/{on_off}")
async def set_heat_plate_route(on_off):
    try:
        set_heat_plate(parse_on_off(on_off))
    except ValueError as ex:
        return JSONResponse(status_code=400, content={
            "action": "set_heat_plate",
            "status": "error",
            "error": {"code": 400, "msg": str(ex)},
            "data": {"relay_state": on_off}
        })

    return {
        "action": "heat_plate",
        "status": "success",
        "data": {"relay_state": on_off}
    }


@app.get("/heat_plate")
async def get_heat_plate_state():
    node_state = app.state.node_states['heat_plate_1']

    return {
        "action": "get_heat_plate",
        "status": "success",
        "data": node_state.state()
    }


@app.get("/temp/set")
async def set_temp_setpoint(r: float = Query(None, description="Desired temperature in Celsius")):
    app.state.setpoint["temp"] = r

    return {
        "action": "set_temp_setpoint",
        "status": "success",
        "data": {"temp": r}
    }
