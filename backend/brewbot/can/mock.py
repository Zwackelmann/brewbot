import asyncio
from brewbot.can.messages import create_temp_state_msg
from brewbot.config import load_config
import time


class MockBus:
    def __init__(self, db):
        self.db = db
        self.msg_queue = []
        self.config = load_config()

        self.temp_min_val = 50
        self.temp_max_val = 300
        self.temp_step = 1
        self.temp_curr_val = (self.temp_min_val + self.temp_max_val) / 2

    def recv(self, timeout):
        if len(self.msg_queue) != 0:
            return self.msg_queue.pop(0)
        else:
            time.sleep(timeout)
            return None

    def apply_temp_step(self):
        self.temp_curr_val += self.temp_step
        if self.temp_curr_val > self.temp_max_val:
            self.temp_curr_val = self.temp_max_val
            self.temp_step = -self.temp_step
        elif self.temp_curr_val < self.temp_min_val:
            self.temp_curr_val = self.temp_min_val
            self.temp_step = -self.temp_step

    async def queue_temp_messages(self):
        while True:
            msg = create_temp_state_msg(self.db, self.temp_curr_val, 0.0, self.config["data"]["temp"]["src_addr"])
            self.msg_queue.append(msg)
            self.apply_temp_step()
            await asyncio.sleep(0.1)

    async def queue_messages(self):
        await self.queue_temp_messages()

    @classmethod
    def send(cls, message):
        print(f"sending message {message}")
