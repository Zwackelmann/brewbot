
def parse_on_off(on_off):
    if on_off == "on":
        return True
    elif on_off == "off":
        return False
    else:
        raise ValueError("value must be either 'on' or 'off'")


def format_on_off(on):
    if isinstance(on, bool):
        return "on" if on else "off"
    elif isinstance(on, int):
        if on == 0x00:
            return "off"
        elif on == 0x01:
            return "on"
        else:
            return None
    else:
        return ValueError(f"unsupported type: {type(on)}")

