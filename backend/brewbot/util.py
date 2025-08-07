import asyncio
import importlib
from contextlib import contextmanager

import numpy as np
from typing import Any, Callable, Optional
import functools
import inspect
import sys
import os
from asyncio.tasks import Task


def async_infinite_loop(fun):
    sig = inspect.signature(fun)
    params = list(sig.parameters.values())
    is_method = params and params[0].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)

    if is_method:
        @functools.wraps(fun)
        async def _coroutine(self, *args, **kwargs):
            while True:
                try:
                    await fun(self, *args, **kwargs)
                except asyncio.CancelledError:
                    break
        return _coroutine
    else:
        @functools.wraps(fun)
        async def _coroutine(*args, **kwargs):
            while True:
                try:
                    await fun(*args, **kwargs)
                except asyncio.CancelledError:
                    break
        return _coroutine


def collect_tasks(obj) -> list[Task]:
    tasks = []
    if isinstance(obj, Task):
        tasks.append(obj)
    elif isinstance(obj, dict):
        for item in [_item for _, _item in obj.items()]:
            tasks.extend(collect_tasks(item))
    elif isinstance(obj, list):
        for item in obj:
            tasks.extend(collect_tasks(item))
    elif obj is None:
        # task dicts can contain `None` tasks as placeholder
        pass
    else:
        print(f"invalid type in type dict: {type(obj)}")

    return tasks

def map_tasks(map_fun: Callable[[Optional[Task]], Any], obj) -> Any:
    if obj is None or isinstance(obj, Task):
        return map_fun(obj)
    elif isinstance(obj, dict):
        return {k: map_tasks(map_fun, v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [map_tasks(map_fun, v) for v in obj]
    else:
        raise ValueError(f"Unable to map tasks: Invalid type `{type(obj)}`")

def log_exceptions(task: asyncio.Task, name: str = ""):
    def callback(t):
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[ERROR] Task {name} crashed: {e}")
    task.add_done_callback(callback)
    return task

@contextmanager
def suppress_stderr():
    old_stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr

def parse_on_off(on_off: Any) -> bool:
    if on_off is None:
        raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, bool):
        return on_off
    elif isinstance(on_off, int):
        if on_off == 0x00:
            return False
        elif on_off == 0x01:
            return True
        else:
            raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, str):
        if on_off == "on":
            return True
        elif on_off == "off":
            return False
        else:
            raise ValueError("value must be either 'on' or 'off'")
    else:
        raise ValueError(f"unsupported type: {type(on_off)}")


def format_on_off(on_off: Any) -> str:
    if on_off is None:
        raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, bool):
        return "on" if on_off else "off"
    elif isinstance(on_off, int):
        if on_off == 0x00:
            return "off"
        elif on_off == 0x01:
            return "on"
        else:
            raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, str):
        if on_off == "off":
            return "off"
        elif on_off == "on":
            return "on"
        else:
            raise ValueError(f"unsupported value: {on_off}")
    else:
        raise ValueError(f"unsupported type: {type(on_off)}")


def encode_on_off(on_off: Any) -> int:
    if on_off is None:
        raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, bool):
        return 0x01 if on_off else 0x00
    elif isinstance(on_off, int):
        if on_off == 0x00:
            return 0x00
        elif on_off == 0x01:
            return 0x01
        else:
            raise ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, str):
        if on_off == "off":
            return 0x00
        elif on_off == "on":
            return 0x01
        else:
            raise ValueError(f"unsupported value: {on_off}")
    else:
        raise ValueError(f"unsupported type: {type(on_off)}")


def load_object(path: str) -> Any:
    module_path, sep, class_name = path.partition(':')
    if not sep:
        raise ValueError("Invalid path format. Expected 'module.submodule:ClassName'.")

    module = importlib.import_module(module_path)
    obj = getattr(module, class_name)
    return obj


def avg_dict(dict_list: list[dict[str, float]]) -> dict[str, float]:
    res = {}
    for d in dict_list:
        for key, val in d.items():
            res.setdefault(key, []).append(val)

    res = {k: [v for v in vs if v is not None and not np.isnan(v)] for k, vs in res.items()}
    return {k: float(np.mean(vs)) if len(vs) != 0 else None for k, vs in res.items()}


def int_range(bits: int, signed: bool):
    if bits < 1:
        raise ValueError("Bit size must be >= 1")

    if signed:
        min_val = -(1 << (bits - 1))
        max_val = (1 << (bits - 1)) - 1
    else:
        min_val = 0
        max_val = (1 << bits) - 1

    return min_val, max_val
