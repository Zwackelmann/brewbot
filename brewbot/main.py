from vispy import app
import time
import numpy as np
from vispy.plot import Fig
from brewbot.ard import ArduinoRemote, PIN_INPUT, PIN_ANALOG, PIN_OUTPUT, PIN_DIGITAL, HIGH, LOW
from matplotlib import pyplot as plt
from scipy import interpolate
from threading import Thread


class LivePlot:
    def __init__(self, series_names, update_handle, time_span=60.0, y_axis=(0.0, 1024.0), nan_value=0.0,
                 fig_size=(2000, 600), min_pan=0.05):
        self.series_names = series_names
        self.update_handle = update_handle
        self.time_span = time_span
        self.nan_value = nan_value
        self.min_pan = min_pan

        self.start_time = None

        self.fig = Fig(size=fig_size)
        self.plotwidget = self.fig[0, 0]

        self.sample_times = np.vstack([0.0, 0.0])
        self.series_values = {s: np.vstack([self.nan_value, self.nan_value]) for s in series_names}
        self.series_lines = {s: self.plotwidget.plot(np.hstack([self.sample_times, sv]))
                             for s, sv in self.series_values.items()}

        self.plotwidget.camera.set_range((0.0, self.time_span), y_axis)

    def update(self, _):
        t = time.time()

        if self.start_time is None:
            self.start_time = t

        self.sample_times = np.concatenate([self.sample_times, np.vstack([time.time() - self.start_time])], axis=0)

        for s in self.series_names:
            update_dict = self.update_handle()
            val = update_dict.get(s)
            if val is None:
                val = self.nan_value

            self.series_values[s] = np.concatenate([self.series_values[s], np.vstack([val])], axis=0)

        last_sample_time = self.sample_times[-1]
        mask = self.sample_times > last_sample_time - self.time_span
        self.sample_times = self.sample_times[mask].reshape(-1, 1)
        for s in self.series_names:
            self.series_values[s] = self.series_values[s][mask].reshape(-1, 1)
            arr = np.hstack([
                self.sample_times,
                self.series_values[s]
            ])

            self.series_lines[s].set_data(arr)

        sample_time_center = np.mean([self.sample_times[0], self.sample_times[-1]])
        center_diff = sample_time_center - self.plotwidget.camera.center[0]

        if center_diff > self.min_pan:
            self.plotwidget.camera.pan([center_diff, 0])


def main2():
    # poly = curr_temp_poly_from_log('temp_002.log', temp_times_002)
    # poly = np.array([1.0, 0.0])
    poly = determine_poly(temp_curr_001)

    with ArduinoRemote(pin_config={"A0": (PIN_INPUT, PIN_ANALOG), 7: (PIN_OUTPUT, PIN_DIGITAL)}).cm() as ard, open('temp.log', 'w') as f:
        last_write = None
        start_time = time.time()

        def update_handle():
            nonlocal last_write

            temp_val = ard.pin_values.get('A0', 0)
            temp = np.polyval(poly, temp_val)

            t = time.time()-start_time
            f.write(f"{t}, {temp_val}, {temp}\n")

            if last_write is None or last_write + 1.0 < time.time():
                print(f"{t}, {temp_val}, {temp}")
                last_write = time.time()

            return {"A0": temp}

        lplot = LivePlot(['A0'], update_handle, time_span=60.0, y_axis=(20, 100))
        plot_timer = app.Timer()
        plot_timer.connect(lplot.update)
        plot_timer.start(1/60)

        def relay_loop():
            while True:
                print('HIGH')
                ard.set_pin(7, HIGH)
                time.sleep(3)
                print('LOW')
                ard.set_pin(7, LOW)
                time.sleep(3)

        t = Thread(target=relay_loop(), daemon=True)
        t.start()

        app.run()


def main():
    with ArduinoRemote(pin_config={8: (PIN_OUTPUT, PIN_DIGITAL)}).cm() as ard:
        while True:
            print('HIGH')
            ard.set_pin(8, HIGH)
            time.sleep(1)
            print('LOW')
            ard.set_pin(8, LOW)
            time.sleep(1)


def determine_poly(measurements):
    buckets = {}
    for x, y in measurements:
        bucket = int(y + 0.5)
        if bucket not in buckets:
            buckets[bucket] = []

        buckets[bucket].append(x)

    cleaned_measurements = sorted([(np.mean(xs), y) for y, xs in buckets.items()], key=lambda _x: _x[0])
    xs, ys = zip(*cleaned_measurements)
    return np.polyfit(xs, ys, deg=1)


temp_times_001 = [(30, 21), (33, 35), (36, 47), (39, 60), (42, 68), (45, 78), (48, 88), (51, 99), (54, 108),
                  (57, 119), (60, 130), (63, 139), (66, 150), (69, 162), (71, 168), (74, 177), (77, 187),
                  (80, 199), (83, 208), (86, 218), (89, 228), (92, 237), (95, 248), (98, 253), (100, 260)]


temp_curr_001 = [(308, 28), (335, 31), (383, 35), (424, 39), (458, 42), (491, 46), (527, 50), (564, 54), (599, 58),
                 (630, 62), (660, 66), (695, 70), (726, 74), (756, 78), (785, 81), (806, 84), (828, 87), (857, 91),
                 (881, 94), (903, 97), (922, 100)]


def curr_temp_poly_from_log(logfile, temp_times, buffer_time=1.0):
    temp_times = sorted(temp_times, key=lambda x: x[0])
    temps, times = zip(*temp_times)
    temps = np.array(temps)
    times = np.array(times)

    time_temp_interp = interpolate.interp1d(times, temps, kind='slinear')

    lines = [line.split(',') for line in open(logfile)]
    time_curr_data = [(float(li[0].strip()), int(li[1].strip()), float(li[2].strip()))
                      for li in lines if len(li) >= 3]

    time_curr_data = [(d[0], d[1]) for d in time_curr_data if temp_times[0][1] <= d[0] <= temp_times[-1][1]]
    time_curr_data = sorted(time_curr_data, key=lambda x: x[0])

    xs, ys = zip(*time_curr_data)
    plt.scatter(xs, ys)
    plt.show()

    curr_temp = []
    for t, cur_med in time_curr_median:
        temp = time_temp_interp(t)
        curr_temp.append((cur_med, temp))

    xs, ys = zip(*curr_temp)
    return np.polyfit(xs, ys, deg=1)


if __name__ == "__main__":
    # curr_temp_poly_from_log("temp_003.log", temp_times_003)
    main()
































