from fastapi import FastAPI, Query
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from brewbot.assembly.kettle import KettleAssembly
from brewbot.config import load_config, CanEnvConfig
from brewbot.can.can_env import CanEnv
from typing import Optional
from dataclasses import dataclass
import logging
from cysystemd import journal

# sudo ip link set can0 type can bitrate 125000
# sudo ip link set up can0
# uvicorn brewbot.rest.api:app --reload


logger = logging.getLogger("brewbot.rest.api")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():  # Prevent duplicate logs if already configured
    handler = journal.JournaldLogHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_app_state(_app)
    run_can_env(_app)
    yield
    await shutdown_can_env(_app)


@dataclass
class AppState:
    conf: Optional[CanEnvConfig] = None
    can_env: Optional[CanEnv] = None


app = FastAPI(lifespan=lifespan)


async def init_app_state(_app: FastAPI):
    app_state = AppState()

    conf = load_config()

    app_state.conf = conf
    app_state.can_env = CanEnv(conf)

    _app.state.app_state = app_state


def run_can_env(_app: FastAPI):
    app_state: AppState = _app.state.app_state
    app_state.can_env.run()


async def shutdown_can_env(_app: FastAPI):
    app_state: AppState = _app.state.app_state
    await app_state.can_env.stop()


@app.get("/kettle/{kettle_name}/temp")
async def get_temp_state_route(kettle_name):
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env

    kettle = can_env.assemblies.get(kettle_name)
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
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env
    kettle = can_env.assemblies.get(kettle_name)

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
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env
    kettle = can_env.assemblies.get(kettle_name)

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
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env
    kettle = can_env.assemblies.get(kettle_name)

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
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env
    kettle = can_env.assemblies.get(kettle_name)

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
    app_state: AppState = app.state.app_state
    can_env: CanEnv = app_state.can_env
    kettle = can_env.assemblies.get(kettle_name)

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
