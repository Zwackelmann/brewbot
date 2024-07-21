
def parse_on_off(on_off):
    if on_off == "on":
        return True
    elif on_off == "off":
        return False
    else:
        raise ValueError("value must be either 'on' or 'off'")


def format_on_off(on_off):
    if on_off is None:
        return ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, bool):
        return "on" if on_off else "off"
    elif isinstance(on_off, int):
        if on_off == 0x00:
            return "off"
        elif on_off == 0x01:
            return "on"
        else:
            return ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, str):
        if on_off == "off":
            return "off"
        elif on_off == "on":
            return "on"
        else:
            return ValueError(f"unsupported value: {on_off}")
    else:
        return ValueError(f"unsupported type: {type(on_off)}")


def encode_on_off(on_off):
    if on_off is None:
        return ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, bool):
        return 0x01 if on_off else 0x00
    elif isinstance(on_off, int):
        if on_off == 0x00:
            return 0x00
        elif on_off == 0x01:
            return 0x01
        else:
            return ValueError(f"unsupported value: {on_off}")
    elif isinstance(on_off, str):
        if on_off == "off":
            return 0x00
        elif on_off == "on":
            return 0x01
        else:
            return ValueError(f"unsupported value: {on_off}")
    else:
        return ValueError(f"unsupported type: {type(on_off)}")
