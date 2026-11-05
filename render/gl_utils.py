from __future__ import annotations

import numpy as np
from pyglm import glm


def mat4_data(matrix: glm.mat4) -> np.ndarray:
    return np.fromiter(glm.value_ptr(matrix), dtype=np.float32, count=16)
