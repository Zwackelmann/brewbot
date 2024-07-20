import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass, field
import time


def read_temps(file):
    measurements = []
    with open(file) as f:
        for line in f:
            parts = line.split()
            measurements.append((float(parts[0]), float(parts[1])))
    return measurements


@dataclass
class TempState:
    temp_to_v_file: Optional[str]
    temp_poly: Optional[np.ndarray] = None
    window: float = 1.0
    v_temps: List[Tuple[float, float]] = field(default_factory=list)

    @classmethod
    def poly_from_measurements(cls, vs, temps):
        return np.polyfit(vs, temps, 1)

    @classmethod
    def poly_from_measurement_file(cls, file):
        temp_to_v = read_temps(file)
        temps, vs = zip(*temp_to_v)
        return TempState.poly_from_measurements(vs, temps)

    def __post_init__(self):
        if self.temp_to_v_file is not None:
            self.temp_poly = TempState.poly_from_measurement_file(self.temp_to_v_file)

    def put(self, v_temp):
        self.v_temps.append((time.time(), v_temp))
        self.v_temps = [(_t, _temp) for _t, _temp in self.v_temps if _t > time.time() - self.window]

    @property
    def curr_v(self):
        return np.median([_temp for _t, _temp in self.v_temps])

    @property
    def curr_c(self):
        return np.polyval(self.temp_poly, self.curr_v)
