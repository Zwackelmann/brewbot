import asyncio
import importlib
import numpy as np
from typing import Any


def async_infinite_loop(fun):
    async def _coroutine():
        while True:
            try:
                await fun()
            except asyncio.CancelledError:
                break
    return _coroutine


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
    return {k: float(np.mean(vs)) for k, vs in res.items()}
