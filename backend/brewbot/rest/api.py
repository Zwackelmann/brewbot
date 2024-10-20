import asyncio
import can
import time
import numpy as np
from fastapi import FastAPI, Query
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from brewbot.data.df import WindowedDataFrame
from brewbot.data.pid import calculate_pd_error, duty_cycle
from brewbot.can.messages import (create_heat_plate_cmd_msg, parse_heat_plate_state_msg, create_motor_cmd_msg,
                                  parse_motor_state_msg, parse_temp_state_msg)
from brewbot.can.util import load_can_database
from brewbot.util import parse_on_off, format_on_off, async_infinite_loop
from brewbot.config import load_config
from brewbot.can.mock import MockSourceTemp, MockSourceMotor, MockSourceHeatPlate, MockBus

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


mock_source_class = {
    "temp": MockSourceTemp,
    "motor": MockSourceMotor,
    "heat_plate": MockSourceHeatPlate
}


@async_infinite_loop
async def can_recv_loop():
    can_recv_step()
    await asyncio.sleep(app.state.conf["can"]["process_interval"])


def can_recv_step():
    for bus in app.state.busses.values():
        message = bus.recv(timeout=app.state.conf["can"]["receive_timeout"])

        if message is not None:
            handle_message(message)


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


def curr_temp():
    df = app.state.signal_values["temp"]["temp_c"].df
    window = app.state.conf["signals"]["temp"]["window"]
    current_time = time.time()

    if len(df) == 0:
        return float("nan")

    filtered_data = df.loc[(current_time - window):current_time]

    if len(filtered_data) == 0:
        return float("nan")
    elif len(filtered_data) == 1:
        return filtered_data.iloc[0]["y"]
    else:
        poly = np.polyfit(filtered_data.index.to_numpy(), filtered_data['y'].to_numpy(), 1)
        return np.polyval(poly, current_time)


def curr_temp_v():
    df = app.state.signal_values["temp"]["temp_v"].df
    window = app.state.conf["signals"]["temp"]["window"]
    current_time = time.time()

    if len(df) == 0:
        return float("nan")

    filtered_data = df.loc[(current_time - window):current_time]

    if len(filtered_data) == 0:
        return float("nan")
    elif len(filtered_data) == 1:
        return filtered_data.iloc[0]["y"]
    else:
        poly = np.polyfit(filtered_data.index.to_numpy(), filtered_data['y'].to_numpy(), 1)
        return np.polyval(poly, current_time)


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


@async_infinite_loop
async def print_temp():
    print(f"temp {curr_temp_v():4.3f} V, {curr_temp():4.1f}°C")
    await asyncio.sleep(1.0)


def handle_message(message):
    temp_msg = parse_temp_state_msg(
        message,
        app.state.dbc,
        app.state.conf["can"]["node_addr"],
        app.state.conf["signals"]["temp"]["node_addr"]
    )
    if temp_msg is not None:
        app.state.signal_values["temp"]["temp_c"].append({"t": [time.time()], "y": [temp_msg['TEMP_C']]})
        app.state.signal_values["temp"]["temp_v"].append({"t": [time.time()], "y": [temp_msg['TEMP_V']]})

    motor_state_msg = parse_motor_state_msg(
        message,
        app.state.dbc,
        app.state.conf["can"]["node_addr"],
        app.state.conf["signals"]["motor"]["node_addr"]
    )
    if motor_state_msg is not None:
        app.state.signal_values["motor"] = {"relay_state": format_on_off(motor_state_msg["RELAY_STATE"])}

    heat_plate_state_msg = parse_heat_plate_state_msg(
        message,
        app.state.dbc,
        app.state.conf["can"]["node_addr"],
        app.state.conf["signals"]["heat_plate"]["node_addr"]
    )
    if heat_plate_state_msg is not None:
        app.state.signal_values["heat_plate"] = {"relay_state": format_on_off(heat_plate_state_msg["RELAY_STATE"])}

        if "temp" in app.state.debug["mock_sources"]:
            heating = app.state.signal_values["heat_plate"]["relay_state"] == "on"
            app.state.debug["mock_sources"]["temp"].heating = heating


async def read_config(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    _app.state.conf = load_config()
    _app.state.dbc = load_can_database(_app.state.conf["can"]["dbc_file"])
    _app.state.busses = {}
    _app.state.tasks = {"can_recv": None, "mock_sources": {}}

    _app.state.signal_names = ["temp", "motor", "heat_plate"]

    temp_window = _app.state.conf["signals"]["temp"]["window"]
    _app.state.signal_values = {
        "temp": {
            "temp_c": WindowedDataFrame(temp_window, columns=["t", "y"], index_column="t"),
            "temp_v": WindowedDataFrame(temp_window, columns=["t", "y"], index_column="t")
        },
        "motor": {"relay_state": None},
        "heat_plate": {"relay_state": None}
    }

    _app.state.setpoint = {
        "temp": None
    }

    _app.state.debug = {"mock_sources": {}}

    for signal_name in _app.state.signal_names:
        if _app.state.conf["debug"]["mock"][signal_name]:
            _app.state.debug["mock_sources"][signal_name] = mock_source_class[signal_name](_app.state.dbc)

    # initiate real can bus, if one signal is not being mocked
    if any(signal_name not in _app.state.debug["mock_sources"] for signal_name in _app.state.signal_names):
        _app.state.busses["can"] = can.interface.Bus(
            _app.state.conf["can"]["channel"],
            interface=_app.state.conf["can"]["interface"]
        )

    mock_sources = [mock_source for mock_source in _app.state.debug["mock_sources"].values()]
    _app.state.busses["mock"] = MockBus(mock_sources)


async def create_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    for signal_name, mock_source in _app.state.debug["mock_sources"].items():
        _app.state.tasks["mock_sources"][signal_name] = asyncio.create_task(mock_source.queue_messages())

    _app.state.tasks["can_recv"] = asyncio.create_task(can_recv_loop())
    _app.state.tasks["control_heat_plate"] = asyncio.create_task(control_heat_plate())
    _app.state.tasks["print_temp"] = asyncio.create_task(print_temp())


async def cancel_background_tasks(_app: FastAPI):
    _app.state = _app.state  # for IDE, since accessing `app.state` yielded warnings

    tasks = [_app.state.tasks.get("can_recv"),
             _app.state.tasks.get("control_heat_plate"),
             _app.state.tasks.get("print_temp")]

    tasks.extend(_app.state.tasks["mock_sources"].values())

    tasks = [_t for _t in tasks if _t is not None]

    for task in tasks:
        task.cancel()
        await task


@app.get("/temp")
async def get_temp():
    return {
        "action": "get_temp",
        "status": "success",
        "data": {
            "temp_c": float(app.state.signal_values["temp"]["temp_c"].df['y'].median()),
            "temp_v": float(app.state.signal_values["temp"]["temp_v"].df['y'].median())
        }
    }


def set_motor(on_off):
    if not app.state.conf["debug"]["mock"]["motor"]:
        msg = create_motor_cmd_msg(app.state.dbc, on_off, app.state.conf["can"]["node_addr"])
        app.state.busses["can"].send(msg)
    else:
        app.state.debug["mock_sources"]["motor"].set_relay(on_off)


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
    return {
        "action": "get_motor",
        "status": "success",
        "data": app.state.signal_values["motor"]
    }


def set_heat_plate(on_off):
    on_off = parse_on_off(on_off)

    if not app.state.conf["debug"]["mock"]["heat_plate"]:
        # print(f"heat plate: {format_on_off(on_off)}")
        msg = create_heat_plate_cmd_msg(app.state.dbc, on_off, app.state.conf["can"]["node_addr"])
        app.state.busses["can"].send(msg)
    else:
        app.state.debug["mock_sources"]["heat_plate"].set_relay(on_off)


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
    return {
        "action": "get_heat_plate",
        "status": "success",
        "data": app.state.signal_values["heat_plate"]
    }


@app.get("/temp/set")
async def set_temp_setpoint(r: float = Query(None, description="Desired temperature in Celsius")):
    app.state.setpoint["temp"] = r

    return {
        "action": "set_temp_setpoint",
        "status": "success",
        "data": {"temp": r}
    }
