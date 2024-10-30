import numpy as np


def parse_value(v_str):
    if v_str is None or len(v_str) == 0:
        return None
    try:
        return float(v_str)
    except ValueError:
        return None

def parse_line(line):
    parts = line.split(" ")
    if len(parts) == 1:
        [temp_str] = parts
        v_str = None
    elif len(parts) == 2:
        [temp_str, v_str] = parts
    else:
        temp_str = None
        v_str = None

    return parse_value(temp_str), parse_value(v_str)



def read_measurements(file):
    with open(file) as f:
        return [parse_line(line) for line in f]



def main():
    meas = read_measurements("conf/measurements/temp_to_v2")
    meas = [(t, v) for t, v in meas if t is not None and v is not None]

    temps, voltages = zip(*meas)
    [m, b] = np.polyfit(voltages, temps, deg=1)

    v_test = 1.226
    print(v_test * m + b)
    print(f"m: {m:1.8f}, b: {b:1.8f}")

if __name__ == "__main__":
    main()
