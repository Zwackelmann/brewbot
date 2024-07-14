import cantools
import json
import asyncio
import can
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from brewbot.data.temp import TempState
from brewbot.can.messages import parse_temp_msg, motor_msg, heat_plate_msg
from brewbot.util import parse_on_off, format_on_off

app = FastAPI()


def handle_message(message):
    temp_msg = parse_temp_msg(message, app.state.dbc, app.state.conf["data"]["temp"]["src_addr"])

    if temp_msg is not None:
        app.state.temp_state.put(temp_msg['TEMP_VOLTAGE'])


async def can_recv_loop():
    while True:
        try:
            message = app.state.can_bus.recv(timeout=0.001)
            if message is not None:
                handle_message(message)
            else:
                pass

            await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Handle task cancellation
            break
        except Exception as e:
            print(f"Error in CAN loop: {e}")


@app.on_event("startup")
async def read_config():
    with open('conf/config.json') as f:
        app.state.conf = json.load(f)

    app.state.can_bus = can.interface.Bus(app.state.conf["can"]["interface"], interface='socketcan')
    app.state.dbc = cantools.database.load_file(app.state.conf["can"]["dbc_file"])
    app.state.temp_state = TempState(app.state.conf["data"]["temp"]["measurements"])
    app.state.motor = {"curr_state": False}
    app.state.heat_plate = {"curr_state": False}


@app.on_event("startup")
async def start_can_loop():
    set_motor(app.state.motor["curr_state"])
    set_heat_plate(app.state.heat_plate["curr_state"])
    app.state.can_recv_task = asyncio.create_task(can_recv_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if app.state.can_recv_task is not None:
        app.state.can_recv_task.cancel()
        await app.state.can_recv_task


@app.get("/temp")
async def get_temp():
    return {"temp_c": app.state.temp_state.curr_c, "temp_v": app.state.temp_state.curr_v}


def set_motor(on):
    msg = motor_msg(app.state.dbc, on, app.state.conf["data"]["motor"]["src_addr"])
    app.state.can_bus.send(msg)
    app.state.motor["curr_state"] = on


@app.get("/motor/{on_off}")
async def set_motor_route(on_off):
    try:
        set_motor(parse_on_off(on_off))
    except ValueError as ex:
        return JSONResponse(status_code=400, content={
            "action": "set_motor",
            "success": False,
            "error": {"code": 400, "msg": str(ex)},
            "data": {"state": format_on_off(app.state.motor["curr_state"])}
        })

    return {
        "action": "set_motor",
        "success": True,
        "data": {"state": on_off}
    }


def set_heat_plate(on):
    msg = heat_plate_msg(app.state.dbc, on, app.state.conf["data"]["heat_plate"]["src_addr"])
    app.state.can_bus.send(msg)
    app.state.motor["curr_state"] = on


@app.get("/heat_plate/{on_off}")
async def set_heat_plate_route(on_off):
    try:
        set_heat_plate(parse_on_off(on_off))
    except ValueError as ex:
        return JSONResponse(status_code=400, content={
            "action": "set_heat_plate",
            "success": False,
            "error": {"code": 400, "msg": str(ex)},
            "data": {"state": format_on_off(app.state.motor["curr_state"])}
        })

    return {
        "action": "heat_plate",
        "success": True,
        "data": {"state": on_off}
    }


# @app.get("/user/{id}")
# async def read_user(id: int):
#     return {"user_id": id}
