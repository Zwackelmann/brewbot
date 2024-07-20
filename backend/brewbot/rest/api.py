import cantools
import asyncio
import can
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from brewbot.data.smoothing import Series
from brewbot.can.messages import (create_heat_plate_cmd_msg, parse_heat_plate_state_msg, create_motor_cmd_msg,
                                  parse_motor_state_msg, parse_temp_state_msg)
from brewbot.util import parse_on_off, format_on_off
from brewbot.config import load_config
from brewbot.can.mock import MockBus

# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0
# uvicorn brewbot.rest.api:app --reload

app = FastAPI()


def handle_message(message):
    temp_msg = parse_temp_state_msg(message, app.state.dbc, app.state.conf["can"]["node_addr"], app.state.conf["data"]["temp"]["node_addr"])
    if temp_msg is not None:
        app.state.temp["temp_c"].put(temp_msg['TEMP_C'])
        app.state.temp["temp_v"].put(temp_msg['TEMP_V'])

    motor_state_msg = parse_motor_state_msg(message, app.state.dbc, app.state.conf["can"]["node_addr"], app.state.conf["data"]["motor"]["node_addr"])
    if motor_state_msg is not None:
        app.state.motor = {"relay_state": format_on_off(motor_state_msg["RELAY_STATE"])}

    heat_plate_state_msg = parse_heat_plate_state_msg(message, app.state.dbc, app.state.conf["can"]["node_addr"], app.state.conf["data"]["heat_plate"]["node_addr"])
    if heat_plate_state_msg is not None:
        app.state.heat_plate = {"relay_state": format_on_off(heat_plate_state_msg["RELAY_STATE"])}


async def can_recv_loop():
    while True:
        try:
            message = app.state.can_bus.recv(timeout=app.state.conf["can"]["receive_timeout"])
            if message is not None:
                handle_message(message)

            await asyncio.sleep(app.state.conf["can"]["process_interval"])
        except asyncio.CancelledError:
            # Handle task cancellation
            break
        except Exception as e:
            print(f"Error in CAN loop: {e}")


@app.on_event("startup")
async def read_config():
    app.state.conf = load_config()
    app.state.dbc = cantools.database.load_file(app.state.conf["can"]["dbc_file"])
    app.state.temp = {
        "temp_c": Series(),
        "temp_v": Series()
    }
    app.state.motor = {"relay_state": None}
    app.state.heat_plate = {"relay_state": None}

    if not app.state.conf["debug"]["mock"]["can_bus"]:
        app.state.can_bus = can.interface.Bus(
            app.state.conf["can"]["channel"],
            interface=app.state.conf["can"]["interface"]
        )
    else:
        app.state.can_bus = MockBus(app.state.dbc)


@app.on_event("startup")
async def start_can_loop():
    if app.state.conf["debug"]["mock"]["can_bus"]:
        app.state.mock_queue_temp_task = asyncio.create_task(app.state.can_bus.queue_temp_messages())

    app.state.can_recv_task = asyncio.create_task(can_recv_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if app.state.can_recv_task is not None:
        app.state.can_recv_task.cancel()
        await app.state.can_recv_task


@app.get("/temp")
async def get_temp():
    return {
        "action": "get_temp",
        "status": "success",
        "data": {"temp_c": app.state.temp["temp_c"].curr, "temp_v": app.state.temp["temp_v"].curr}
    }


def set_motor(on):
    msg = create_motor_cmd_msg(app.state.dbc, on, app.state.conf["can"]["node_addr"])
    app.state.can_bus.send(msg)


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
        "data": app.state.motor
    }


def set_heat_plate(on):
    msg = create_heat_plate_cmd_msg(app.state.dbc, on, app.state.conf["can"]["node_addr"])
    app.state.can_bus.send(msg)


@app.get("/heat_plate/{on_off}")
async def set_heat_plate_route(on_off):
    try:
        set_heat_plate(parse_on_off(on_off))
    except ValueError as ex:
        return JSONResponse(status_code=400, content={
            "action": "set_heat_plate",
            "status": "error",
            "error": {"code": 400, "msg": str(ex)},
            "data": {"state": on_off}
        })

    return {
        "action": "heat_plate",
        "status": "success",
        "data": {"state": on_off}
    }


@app.get("/heat_plate")
async def get_heat_plate_state():
    return {
        "action": "get_heat_plate",
        "status": "success",
        "data": app.state.heat_plate
    }