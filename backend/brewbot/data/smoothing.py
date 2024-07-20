import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass, field
import time


@dataclass
class Series:
    window: float = 1.0
    values: List[Tuple[float, float]] = field(default_factory=list)

    def put(self, v_temp):
        self.values.append((time.time(), v_temp))
        self.values = [(_t, _temp) for _t, _temp in self.values if _t > time.time() - self.window]

    @property
    def curr(self):
        if len(self.values) == 0:
            return None
        else:
            return np.median([_temp for _t, _temp in self.values])
