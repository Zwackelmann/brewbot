import numpy as np


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
