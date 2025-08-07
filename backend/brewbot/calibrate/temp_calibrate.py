from dataclasses import dataclass
from typing import Optional, Tuple
import asyncio
import tkinter as tk
from brewbot.calibrate.cam import Cam
from brewbot.calibrate.box_config_app import BoxConfigApp, capture_digits
from brewbot.can.can_env import CanEnv
from brewbot.config import load_config, CanEnvConfig
import time
import os
import json
import datetime


@dataclass
class AppState:
    active_components: set[str]
    finished: bool
    digit_boxes: list[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]]
    preview_image_dims: Tuple[int, int]
    digit_image_dims: Tuple[int, int]
    digit_segment_boxes: list[Tuple[Tuple[float, float, float, float], int]]
    tk_root: Optional[tk.Tk]
    box_config_app: Optional[BoxConfigApp]
    cam: Optional[Cam]
    show_capture_digits_debug_windows: bool
    parsed_digit: Optional[int]
    # can_temp_node_names: list[str]
    # can_temp_readers: dict[str, CanTempReader]
    can_conf: Optional[CanEnvConfig]
    can_env: Optional[CanEnv]
    can_temp_vs: list[Tuple[float, float]]
    temp_v_aggregate_time: float
    recording_file: str


async def update_input_image_task(app_state: AppState):
    while not app_state.finished:
        if "update_input_image" in app_state.active_components and app_state.tk_root is not None:
            app_state.box_config_app.update_input_image(app_state.cam.image)

        await asyncio.sleep(0.1)


async def capture_digits_task(app_state: AppState):
    while not app_state.finished:
        if "capture_digits" in app_state.active_components:
            num = capture_digits(
                app_state.cam.image,
                app_state.digit_boxes,
                app_state.digit_image_dims,
                app_state.digit_segment_boxes,
                app_state.show_capture_digits_debug_windows
            )
            app_state.parsed_digit = num

        await asyncio.sleep(0.5)


"""async def update_can_task(app_state: AppState):
    for node_name in app_state.can_temp_node_names:
        if node_name not in app_state.can_temp_readers:
            app_state.can_temp_readers[node_name] = CanTempReader(node_name)

    while not app_state.finished:
        if "update_can" in app_state.active_components:
            for node_name, temp_reader in app_state.can_temp_readers.items():
                temp_msg = temp_reader.recv()
                if temp_msg is not None:
                    can_temp_vs = app_state.can_temp_vs
                    can_temp_vs.append((time.time(), temp_msg['TEMP_V']))
                    can_temp_vs = [(t, v) for t, v in can_temp_vs if (time.time() - t) < app_state.temp_v_aggregate_time]
                    app_state.can_temp_vs = can_temp_vs

                    print(node_name, temp_msg['TEMP_C'])

        await asyncio.sleep(0.01)"""


async def tk_mainloop_task(app_state: AppState):
    def init():
        app_state.tk_root = tk.Tk()
        app_state.box_config_app = BoxConfigApp(
            app_state.preview_image_dims,
            app_state.digit_image_dims,
            app_state.digit_segment_boxes
        )
        app_state.box_config_app.create_widgets(app_state.tk_root, app_state.digit_boxes)

    def update():
        app_state.tk_root.update()
        app_state.digit_boxes = [dv.get() for dv in app_state.box_config_app.digit_box_vars]

    def destroy():
        app_state.tk_root = None
        app_state.bbox_config_app = None
        app_state.active_components.discard("tk_mainloop")
        app_state.active_components.discard("update_input_image")
        app_state.active_components.add("capture_digits")
        app_state.active_components.add("output")
        app_state.active_components.add("update_can")

    while not app_state.finished:
        if "tk_mainloop" in app_state.active_components:
            if app_state.tk_root is None:
                init()
            try:
                update()
                if not app_state.tk_root.winfo_exists():
                    destroy()
            except tk.TclError:
                destroy()

        await asyncio.sleep(0.01)


async def update_cam_task(app_state: AppState):
    while not app_state.finished:
        if "read_cam" in app_state.active_components:
            app_state.cam.update()
        await asyncio.sleep(0.1)

    app_state.cam.release()


async def output_task(app_state: AppState):
    with open(app_state.recording_file, "w") as f:
        while not app_state.finished:
            if "output" in app_state.active_components:
                real_temp_c = app_state.parsed_digit

                if "thermometer_1" in app_state.can_env.node_states and \
                        "temp_state" in app_state.can_env.node_states['thermometer_1'].rx_message_state and \
                        app_state.can_env.node_states['thermometer_1'].rx_message_state['temp_state'] is not None:
                    can_temp_v = app_state.can_env.node_states['thermometer_1'].rx_message_state['temp_state'].get("temp_v")
                else:
                    can_temp_v = None

                d = {
                    "time": datetime.datetime.now(datetime.UTC).isoformat(),
                    "real_temp_c": real_temp_c,
                    "can_temp_v": can_temp_v
                }
                print(d)

                f.write(f"{json.dumps(d)}\n")
                f.flush()

            await asyncio.sleep(1.0)


async def main():
    time_str = time.strftime("%Y-%m-%dT%H-%M-%S", time.localtime())

    app_state = AppState(
        active_components={# "tk_mainloop",
                           # "read_cam",
                           # "update_can",
                           "output",
                           "capture_digits",
                           # "update_input_image"
                           },
        finished=False,
        digit_boxes = [
            ((273, 83), (342, 83), (332, 195), (264, 196)),
            ((344, 84), (411, 83), (400, 195), (335, 195))
        ],
        preview_image_dims=(512, 512),
        digit_image_dims=(256, 128),
        digit_segment_boxes=[
            (( 0.25, 0.00, 0.50, 0.20), 1),
            (( 0.00, 0.15, 0.40, 0.30), 0),
            (( 0.60, 0.15, 0.40, 0.30), 0),
            (( 0.25, 0.40, 0.50, 0.22), 1),
            (( 0.00, 0.56, 0.40, 0.30), 0),
            (( 0.60, 0.56, 0.40, 0.30), 0),
            (( 0.25, 0.80, 0.50, 0.20), 1)
        ],
        tk_root = None,
        box_config_app = None,
        cam = Cam(0), # Cam(0),
        show_capture_digits_debug_windows = False,
        parsed_digit=70,
        # can_temp_readers = {},
        # can_temp_node_names = ["temp_1", "temp_2"],
        can_conf = load_config(),
        can_env=None,
        can_temp_vs = [],
        temp_v_aggregate_time = 1.0,
        recording_file=os.path.join("recordings", f"rec_{time_str}.txt")
    )

    app_state.can_env = CanEnv(app_state.can_conf)
    app_state.can_env.run()

    tasks = [
        # asyncio.create_task(tk_mainloop_task(app_state)),
        # asyncio.create_task(update_cam_task(app_state)),
        # asyncio.create_task(update_input_image_task(app_state)),
        # asyncio.create_task(capture_digits_task(app_state)),
        # asyncio.create_task(update_can_task(app_state)),
        asyncio.create_task(output_task(app_state))
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
