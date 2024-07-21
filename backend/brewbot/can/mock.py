import asyncio
from brewbot.can.messages import create_temp_state_msg, create_motor_state_msg, create_heat_plate_state_msg
from brewbot.config import load_config
from brewbot.util import format_on_off
import time
import random


class MockBus:
    def __init__(self, sources):
        self.sources = sources

    def recv(self, timeout):
        for source in self.sources:
            if len(source.msg_queue) != 0:
                return source.msg_queue.pop(0)

        time.sleep(timeout)
        return None

    @classmethod
    def send(cls, message):
        print(f"sending message {message}")


class MockSourceTemp:
    def __init__(self, db):
        self.db = db
        self.msg_queue = []
        self.config = load_config()
        self.msg_interval = 0.1

        self.min_temp = 20.0
        self.max_temp = 100.0
        self.curr_temp = self.min_temp
        self.approach_factor = 0.001
        self.heating = False

        self.error_mu = 0.0
        self.error_sigma = 0.2

        self.v_to_temp_m = 23.69448038
        self.v_to_temp_b = -4.59983094

    def apply_temp_step(self):
        if self.heating:
            diff = self.max_temp - self.curr_temp
        else:
            diff = self.min_temp - self.curr_temp

        step = diff * self.approach_factor
        self.curr_temp += step

    def measure_error(self):
        return random.gauss(self.error_mu, self.error_sigma)

    async def queue_messages(self):
        while True:
            try:
                temp_c = self.curr_temp + self.measure_error()
                temp_v = (temp_c - self.v_to_temp_b) / self.v_to_temp_m
                msg = create_temp_state_msg(self.db, temp_c, temp_v, self.config["signals"]["temp"]["node_addr"])
                self.msg_queue.append(msg)
                self.apply_temp_step()
                await asyncio.sleep(self.msg_interval)
            except asyncio.CancelledError:
                break


class MockSourceMotor:
    def __init__(self, db):
        self.db = db
        self.msg_queue = []
        self.config = load_config()
        self.msg_interval = 0.1

        self.relay_state = format_on_off(False)

    def set_relay(self, on_off):
        self.relay_state = format_on_off(on_off)

    async def queue_messages(self):
        while True:
            try:
                msg = create_motor_state_msg(
                    self.db,
                    self.relay_state,
                    self.config["signals"]["motor"]["node_addr"]
                )
                self.msg_queue.append(msg)
                await asyncio.sleep(self.msg_interval)
            except asyncio.CancelledError:
                break


class MockSourceHeatPlate:
    def __init__(self, db):
        self.db = db
        self.msg_queue = []
        self.config = load_config()
        self.msg_interval = 0.1

        self.relay_state = format_on_off(False)

    def set_relay(self, on_off):
        self.relay_state = format_on_off(on_off)

    async def queue_messages(self):
        while True:
            try:
                msg = create_heat_plate_state_msg(
                    self.db,
                    self.relay_state,
                    self.config["signals"]["heat_plate"]["node_addr"]
                )
                self.msg_queue.append(msg)
                await asyncio.sleep(self.msg_interval)
            except asyncio.CancelledError:
                break
