from typing import Optional

import numpy as np
import pandas as pd
import time

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt


def generate_test_series(t1, t2, y1, y2, num_points, sigma):
    # Create linear spaces series for time and measurements
    ts = np.linspace(t1, t2, num_points)
    ys = np.linspace(y1, y2, num_points)

    # add noise to measurements
    noise = np.random.normal(0, sigma, num_points)
    ys_noisy = ys + noise

    return pd.DataFrame(data={"t": ts, "y": ys_noisy}).set_index("t")


def calculate_pd_error(setpoint, df, current_time, time_window):
    """
    Calculates the proportional (P) and derivative (D) error components for a PID controller.

    Parameters:
    - setpoint: The desired reference value (r).
    - df: A pandas DataFrame containing time-indexed measurements of the system.
    - current_time: The current time (t) for which the P and D errors are being calculated.
    - time_window: The time window (dt) to filter the measurements from current_time - time_window to current_time.

    Returns:
    - p_error: Proportional error (P component).
    - d_error: Derivative error (D component).
    """

    filtered_data = df.loc[(current_time - time_window):current_time]

    if len(filtered_data) == 0:
        return float("nan"), float("nan")

    if len(filtered_data) == 1:
        # If only one data point exists, assume no change in slope (D = 0.0)
        return setpoint - filtered_data.iloc[0]["y"], 0.0

    # Fit a linear polynomial (1st-degree) to the filtered data to approximate slope
    poly = np.polyfit(filtered_data.index.to_numpy(), filtered_data['y'].to_numpy(), 1)

    p_error = setpoint - np.polyval(poly, current_time)
    d_error = -poly[0]  # D-Error = negative of the slope from the polynomial fit

    return p_error, d_error


def duty_cycle(cs, max_cs=2.5, low_jump_thres=0.1, high_jump_thres=0.9):
    # Calculate the duty cycle as a fraction of the max control signal
    pw = min(cs / max_cs, 1.0)

    if pw < low_jump_thres / 2:
        return 0.0  # Force relay completely off for very low control signals
    elif low_jump_thres / 2 <= pw < low_jump_thres:
        return low_jump_thres  # Jump to minimum duty cycle
    elif high_jump_thres <= pw < ((high_jump_thres + 1.0) / 2):
        return high_jump_thres  # Jump to maximum duty cycle
    elif pw > high_jump_thres:
        return 1.0  # Force full-on signal
    else:
        return pw  # Return the calculated duty cycle if no jumps are triggered


def main():
    time_series_t0 = 0.0
    time_series_t1 = 60.0
    time_series_y0 = 30.0
    time_series_y1 = 35.0
    time_series_sigma = 0.3
    time_series_num_points = int(time_series_t1 - time_series_t0) * 10

    df = generate_test_series(
        time_series_t0,
        time_series_t1,
        time_series_y0,
        time_series_y1,
        time_series_num_points,
        time_series_sigma
    )

    r = 39.7
    t = 60.0
    dt = 10.0

    p, d, poly = calculate_pd_error(r, df, t, dt)
    cs = p_gain * p + d_gain * d
    pw = duty_cycle(cs, max_cs=2.5, low_jump_thres=0.1, high_jump_thres=0.9)

    df["y_poly"] = np.polyval(poly, df.index.to_numpy())
    df["r"] = np.ones((time_series_num_points, )) * r

    df_points = pd.DataFrame(data={"t": [t-dt, t], "y_poly": np.polyval(poly, [t-dt, t])}).set_index("t")

    plt.plot(df.index.to_numpy(), df['y'].to_numpy())
    plt.plot(df.index.to_numpy(), df['y_poly'].to_numpy())
    plt.plot(df.index.to_numpy(), df['r'].to_numpy())
    plt.scatter(df_points.index.to_numpy(), df_points["y_poly"].to_numpy(), color='red')

    plt.show()


if __name__ == "__main__":
    main()
