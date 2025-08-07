import can
import asyncio
import logging

from brewbot.config import CanPortConfig
from brewbot.util import  suppress_stderr
from cysystemd import journal
from typing import Callable


logger = logging.getLogger("brewbot.can.can_port")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():  # Prevent duplicate logs if already configured
    handler = journal.JournaldLogHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class CanPort:
    conf: CanPortConfig
    bus: can.Bus
    event_handlers: list[Callable[[str], None]]

    def __init__(self, conf: CanPortConfig):
        self.bus = None
        self.conf = conf
        self.event_handlers = []

        self.shutdown()

    def shutdown(self) -> None:
        if self.bus is not None:
            self.bus.shutdown()

        self.bus = None
        self.notify('shutdown')

    def add_event_handler(self, event_handler: Callable[[str], None]) -> None:
        self.event_handlers.append(event_handler)

    def notify(self, evt: str) -> None:
        for event_handler in self.event_handlers:
            event_handler(evt)

    def connect_can_device(self) -> None:
        if self.bus is not None:
            # can device already connected
            return

        if self.conf.bus is None:
            raise ValueError("Cannot connect to can device: Can bus config is empty")

        try:
            with suppress_stderr():
                self.bus = can.interface.Bus(
                    self.conf.bus.channel,
                    interface=self.conf.bus.interface
                )
                self.notify('connected')
                print("Connection established to can device")
        except OSError as e:
            if "[Errno 19]" in str(e):  # no such device error -> can device is not plugged in -> default error case
                pass
            else:
                raise e
        except can.exceptions.CanOperationError:
            print("can error")
            pass

    def recv(self, *args, **kwargs):
        if self.bus is None:
            return None

        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.conf.bus.receive_timeout

        try:
            return self.bus.recv(*args, **kwargs)
        except OSError as e:
            if "[Errno 19]" in str(e):
                # no such device error -> can device was plugged out -> shutdown
                print("Connection to can device lost -> shutdown")
                self.shutdown()
                return None
            else:
                raise e
        except can.exceptions.CanOperationError:
            # no such device error -> can device was plugged out -> shutdown
            print("Connection to can device lost -> shutdown")
            self.shutdown()
            return None

    def send(self, *args, **kwargs):
        if self.bus is None:
            return

        try:
            self.bus.send(*args, **kwargs)
        except OSError as e:
            if "[Errno 19]" in str(e):
                # no such device error -> can device was plugged out -> shutdown
                logger.warning("Connection to can device lost -> shutdown")
                self.shutdown()
            else:
                raise e
        except can.exceptions.CanOperationError:
            # no such device error -> can device was plugged out -> shutdown
            logger.warning("Connection to can device lost -> shutdown")
            self.shutdown()

    async def connect_can_coro(self):
        try:
            while True:
                self.connect_can_device()
                await asyncio.sleep(self.conf.device_connect_interval)
        except asyncio.CancelledError:
            self.shutdown()
