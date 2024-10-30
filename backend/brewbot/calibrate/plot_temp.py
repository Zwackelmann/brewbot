import json
from dataclasses import dataclass

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.ndimage import gaussian_filter1d


@dataclass
class RecSequence:
    file_path: str
    slc: slice
    temp_spline_divider: int
    voltage_filter_sigma: float


@dataclass
class RecGroup:
    name: str
    file_paths: list[str]
    slices: list[slice]


def time_plot(recs, dfs, ax1):

    for df in dfs:
        # Plot real_temp_c on the left y-axis
        ax1.plot(df.index, df['real_temp_c_smoothed'], color='blue', label='Real Temp (C)')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Real Temp (C)', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')

        # Create a second y-axis for can_temp_v
        ax2 = ax1.twinx()
        ax2.plot(df.index, df['can_temp_v_smoothed'], color='red', label='CAN Temp (V)')
        ax2.set_ylabel('CAN Temp (V)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

    plt.xticks(rotation=45)


def temp_to_v_means_plot(recs, dfs, ax1):
    for df in dfs:
        grouped = df.groupby('real_temp_c_smoothed')['can_temp_v_smoothed']
        box_plot_data = [grouped.get_group(temp) for temp in grouped.groups]
        means = grouped.mean()

        # Generate the boxplot
        ax1.boxplot(box_plot_data,
            positions=grouped.groups.keys(),
            showmeans=False,
            whis=[5, 95],
            showfliers=False
        )

        temps = list(means.index)
        vs = list(means.values)
        poly_temp2v = np.polyfit(temps, vs, deg=2)
        poly_v2temp = np.polyfit(vs, temps, deg=2)
        p_vs = list(np.polyval(poly_temp2v, temps))
        p_temps = list(np.polyval(poly_v2temp, p_vs))

        mean_error = np.mean(np.abs(np.subtract(temps, p_temps)))

        # log_temps = [-5.0, 0.0, 100.0, 140.0]
        log_temps = [-50.0, 0.0, 100.0, 200.0]
        log_vs = list(np.polyval(poly_temp2v, log_temps))
        log_str = ", ".join([f"v {t}: {v:1.3f}" for t, v in zip(log_temps, log_vs)])

        print(poly_temp2v)
        print(f"mean error: {mean_error:1.4f}, {log_str}, v diff: {log_vs[-1]-log_vs[0]:1.3f}")

        ax1.plot(temps, p_vs)

        # temp, v = calc_temp_to_v(2400)
        # ax1.plot(temp, v)

        plt.xticks(rotation=90)

        # ax1.plot(df['real_temp_c_smoothed'], df['can_temp_v_smoothed'], color='blue')
        # ax1.set_xlabel('Real Temp (C)')
        # ax1.set_ylabel('CAN Temp (V)')
        # ax1.tick_params(axis='y', labelcolor='red')


def smoothed_plot(recs, dfs, ax1):
    time_list = []
    time_smooth_list = []
    temps_list = []
    temps_smooth_list = []
    temps_bin_list = []
    voltages_list = []
    voltages_smooth_list = []
    voltages_bin_list = []

    for rec, df in zip(recs, dfs):
        time_start = df.index[0]
        df['time_sec'] = (df.index - time_start).total_seconds()

        time = df['time_sec'].values
        temps = df['real_temp_c_interpolated'].values
        voltage = df['can_temp_v_smoothed'].values

        time_smooth = np.linspace(time.min(), time.max(),  len(time))
        temp_spline = UnivariateSpline(time, temps, s=len(time)//rec.temp_spline_divider)

        temps_smooth = temp_spline(time_smooth)
        voltages_smooth = gaussian_filter1d(voltage, sigma=rec.voltage_filter_sigma)

        volt_to_temp_df = pd.DataFrame({'voltage': voltages_smooth, 'temp': temps_smooth})
        bin_width = 0.1
        temp_bins = np.arange(volt_to_temp_df['temp'].min(), volt_to_temp_df['temp'].max() + bin_width, bin_width)
        volt_to_temp_df['temp_bin'] = pd.cut(volt_to_temp_df['temp'], temp_bins)
        volt_to_temp_binned_groups = volt_to_temp_df.groupby('temp_bin', observed=True).agg({'temp': 'median', 'voltage': 'median'}).dropna()

        time_list.append(time)
        time_smooth_list.append(time_smooth)
        temps_list.append(temps)
        temps_smooth_list.append(temps_smooth)
        temps_bin_list.append(volt_to_temp_binned_groups['temp'])
        voltages_list.append(voltage)
        voltages_smooth_list.append(voltages_smooth)
        voltages_bin_list.append(volt_to_temp_binned_groups['voltage'])

    times = np.hstack(time_list)
    times_smooth = np.hstack(time_smooth_list)
    temps = np.hstack(temps_list)
    temps_smooth = np.hstack(temps_smooth_list)
    temps_bins = np.hstack(temps_bin_list)
    voltages = np.hstack(voltages_list)
    voltages_smooth = np.hstack(voltages_smooth_list)
    voltages_bins = np.hstack(voltages_bin_list)

    poly = np.polyfit(voltages_bins, temps_bins, deg=2)
    print(poly)

    # vs = np.linspace(np.min(voltages_bins), np.max(voltages_bins))
    # ts = np.polyval(poly, vs)

    # ax1.scatter(voltages_bins, temps_bins, color="blue")
    # ax1.plot(vs, ts, color="red")

    ax1.plot(times, temps, color='skyblue')
    ax1.plot(times_smooth, temps_smooth, color="blue")
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Real Temp (C)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.plot(times, voltages, color='pink')
    ax2.plot(times_smooth, voltages_smooth, color='red')
    ax2.set_ylabel('CAN Temp (V)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.xticks(rotation=45)


def main():
    group_name = "3k OP Amp"
    recs = [
        RecSequence(
            file_path="recordings/rec_2024-10-28T15-51-55.txt",
            slc=slice(100, 42000),
            temp_spline_divider=10,
            voltage_filter_sigma=20
        ),
        RecSequence(
            file_path="recordings/rec_2024-10-29T09-13-42.txt",
            slc=slice(4000, None),
            temp_spline_divider=10,
            voltage_filter_sigma=750.0
        )
    ]

    # show_plot = "temp_to_v"
    # show_plot = "time"
    show_plot = "smoothed"

    v_factor = 5.033 / 5.0  # real voltage measured at can module / max voltage assumed in can message
    rolling_window = 5

    dfs = []
    for rec in recs:
        with open(rec.file_path) as f:
            df = pd.DataFrame([json.loads(line) for line in f][rec.slc])
            df['time'] = pd.to_datetime(df['time'], errors='coerce')
            df = df.astype({"real_temp_c": "float64", "can_temp_v": "float64"})
            df = df.set_index("time")
            df.loc[(df['real_temp_c'] < 1), 'real_temp_c'] = df['real_temp_c'] + 100
            df['can_temp_v'] = df['can_temp_v'] * v_factor
            df['real_temp_c_smoothed'] = df['real_temp_c'].rolling(window=rolling_window, center=True).median()
            df['real_temp_c_interpolated'] = df['real_temp_c_smoothed'].interpolate(method='linear')
            df['can_temp_v_smoothed'] = df['can_temp_v'].rolling(window=rolling_window, center=True).median()
            df = df.iloc[(rolling_window//2):-(rolling_window//2)]

            dfs.append(df)

    fig, ax1 = plt.subplots(figsize=(10, 6))

    if show_plot == "time":
        plt.title('Temperature Data Over Time')
        time_plot(recs, dfs, ax1)
    elif show_plot == "temp_to_v":
        plt.title(f"Temperature To Voltage {group_name}")
        temp_to_v_means_plot(recs, dfs, ax1)
    elif show_plot == "smoothed":
        plt.title(f"Temperature To Voltage Smoothed {group_name}")
        smoothed_plot(recs, dfs, ax1)

    plt.tight_layout()
    plt.savefig('temp_plot.png')


def main2():
    v_in = 5  # Input voltage in volts
    r_sensor_0_deg = 1000  # Sensor resistance at 0 degrees in ohms
    r_sensor_100_deg = 1385  # Sensor resistance at 100 degrees in ohms

    for r_fixed in [1000, 1200, 1500, 2000, 3000]:
        # Voltage divider formula: V_out = V_in * (R_sensor / (R_sensor + R_fixed))
        v_out_0_deg = v_in * (r_sensor_0_deg / (r_sensor_0_deg + r_fixed))
        v_out_100_deg = v_in * (r_sensor_100_deg / (r_sensor_100_deg + r_fixed))

        print(f"r_fixed: {r_fixed}, v0: {v_out_0_deg:2.3f}, v100: {v_out_100_deg:2.3f}, vdiff: {v_out_100_deg-v_out_0_deg:2.3f}")


def calc_temp_to_v(r_fixed):
    v_in = 4.9  # Input voltage in volts
    r_sensor_0_deg = 1000  # Sensor resistance at 0 degrees in ohms
    r_sensor_100_deg = 1385  # Sensor resistance at 100 degrees in ohms

    r = np.linspace(r_sensor_100_deg, r_sensor_0_deg, 100)
    v = v_in * (r / (r + r_fixed))
    temp = np.linspace(100, 0, 100)

    return temp, v


def main3():
    v_in = 4.5  # Input voltage in volts
    r_sensor_0_deg = 1000  # Sensor resistance at 0 degrees in ohms
    r_sensor_100_deg = 1385  # Sensor resistance at 100 degrees in ohms
    r_fixed = 2400

    r = np.linspace(r_sensor_100_deg, r_sensor_0_deg, 100)
    v = v_in * (r / (r + r_fixed))
    temp = np.linspace(100, 0, 100)
    print(temp)

    plt.plot(temp, v)
    plt.savefig('temp_v.png')

    print(v)


if __name__ == "__main__":
    main()
