from dataclasses import dataclass

import numpy as np


@dataclass
class Bounds3D:
    min: np.ndarray
    max: np.ndarray

    @property
    def center(self):
        return 0.5 * (self.min + self.max)

    @property
    def size(self):
        return float(np.linalg.norm(self.max - self.min))

    @property
    def half_size(self):
        return 0.5 * (self.max - self.min)
