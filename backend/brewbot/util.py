

def parse_on_off(on_off):
    if on_off == "on":
        return True
    elif on_off == "off":
        return False
    else:
        raise ValueError("value must be either 'on' or 'off'")


def format_on_off(on):
    return "on" if on else "off"

