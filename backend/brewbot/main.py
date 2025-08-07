from brewbot.config import load_config, CanEnvConfig
from brewbot.can.can_env import CanEnv
from brewbot.assembly.kettle import KettleAssembly
import asyncio
from brewbot.util import async_infinite_loop
from brewbot.can.util import pdu_format, pgn_to_can_id, is_pdu_format_1
from cantools.database import Database, load_string as load_dbc_string, Message


async def main():
    can_env = CanEnv(load_config())
    can_env.run()

    @async_infinite_loop
    async def debug_coro():
        kettle = can_env.assemblies.get('kettle_1')

        if isinstance(kettle, KettleAssembly):
            print(kettle.therm_state)

            is_on = None
            relay_state = kettle.heat_plate_state.get("relay_state")

            if relay_state is not None:
                is_on = relay_state.get("on")

            if is_on:
                kettle.set_heat_plate(False)
                kettle.set_steering(True)
            else:
                kettle.set_heat_plate(True)
                kettle.set_steering(False)

        await asyncio.sleep(2.5)

    asyncio.create_task(debug_coro())

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await can_env.stop()


if __name__ == "__main__":
    # asyncio.run(main())
    print(is_pdu_format_1(0x1031))
    print(pgn_to_can_id(0x1031, 6, 0x10, 0x80))
