import asyncio
import can
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from brewbot.data.smoothing import Series
from brewbot.can.messages import (create_heat_plate_cmd_msg, parse_heat_plate_state_msg, create_motor_cmd_msg,
                                  parse_motor_state_msg, parse_temp_state_msg)
from brewbot.can.util import load_can_database
from brewbot.util import parse_on_off, format_on_off
from brewbot.config import load_config
from brewbot.can.mock import MockSourceTemp, MockSourceMotor, MockSourceHeatPlate, MockBus

# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0
# uvicorn brewbot.rest.api:app --reload

app = FastAPI()
# for IDE, since accessing `app.state` yielded warnings
app.state = app.state

mock_source_class = {
    "temp": MockSourceTemp,
    "motor": MockSourceMotor,
    "heat_plate": MockSourceHeatPlate
}


async def can_recv_loop():
    while True:
        try:
            can_recv_step()
            await asyncio.sleep(app.state.conf["can"]["process_interval"])
        except asyncio.CancelledError:
            break


def can_recv_step():
    for bus in app.state.busses.values():
        message = bus.recv(timeout=app.state.conf["can"]["receive_timeout"])

        if message is not None:
            handle_message(message)


def handle_message(message):
    temp_msg = parse_temp_state_msg(
        message,
        app.state.dbc,
        app.state.conf["can"]["node_addr"],
        app.state.conf["signals"]["temp"]["node_addr"]
    )
    if temp_msg is not None:
        app.state.signal_values["temp"]["temp_c"].put(temp_msg['TEMP_C'])
        app.state.signal_values["temp"]["temp_v"].put(temp_msg['TEMP_V'])

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


@app.on_event("startup")
async def read_config():
    app.state.conf = load_config()
    app.state.dbc = load_can_database(app.state.conf["can"]["dbc_file"])
    app.state.busses = {}
    app.state.tasks = {"can_recv": None, "mock_sources": {}}

    app.state.signal_names = ["temp", "motor", "heat_plate"]

    app.state.signal_values = {
        "temp": {"temp_c": Series(), "temp_v": Series()},
        "motor": {"relay_state": None},
        "heat_plate": {"relay_state": None}
    }

    app.state.debug = {"mock_sources": {}}

    for signal_name in app.state.signal_names:
        if app.state.conf["debug"]["mock"][signal_name]:
            app.state.debug["mock_sources"][signal_name] = mock_source_class[signal_name](app.state.dbc)

    # initiate real can bus, if one signal is not being mocked
    if any(signal_name not in app.state.debug["mock_sources"] for signal_name in app.state.signal_names):
        app.state.busses["can"] = can.interface.Bus(
            app.state.conf["can"]["channel"],
            interface=app.state.conf["can"]["interface"]
        )

    mock_sources = [mock_source for mock_source in app.state.debug["mock_sources"].values()]
    app.state.busses["mock"] = MockBus(mock_sources)


@app.on_event("startup")
async def create_background_tasks():
    for signal_name, mock_source in app.state.debug["mock_sources"].items():
        app.state.tasks["mock_sources"][signal_name] = asyncio.create_task(mock_source.queue_messages())

    app.state.tasks["can_recv"] = asyncio.create_task(can_recv_loop())


@app.on_event("shutdown")
async def cancel_background_tasks():
    if app.state.tasks["can_recv"] is not None:
        app.state.tasks["can_recv"].cancel()
        await app.state.tasks["can_recv"]

    for mock_source_task in app.state.tasks["mock_sources"].values():
        mock_source_task.cancel()
        await mock_source_task


@app.get("/temp")
async def get_temp():
    return {
        "action": "get_temp",
        "status": "success",
        "data": {
            "temp_c": app.state.signal_values["temp"]["temp_c"].curr,
            "temp_v": app.state.signal_values["temp"]["temp_v"].curr
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
    if not app.state.conf["debug"]["mock"]["heat_plate"]:
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
