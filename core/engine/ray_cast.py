# core/engine/ray_cast.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pyglm import glm

if TYPE_CHECKING:
    from core.camera import Camera
    from plane.plane import Plane


def screen_ray(camera: "Camera", x: float, y: float,
               width: int, height: int) -> tuple[np.ndarray, np.ndarray] | None:
    if camera is None:
        return None
    v = camera.get_view_matrix()
    p = camera.get_projection_matrix()
    nx = 2.0 * x / width - 1.0
    ny = 1.0 - 2.0 * y / height
    inv = glm.inverse(p * v)
    near = inv * glm.vec4(nx, ny, -1.0, 1.0)
    far = inv * glm.vec4(nx, ny, 1.0, 1.0)
    if abs(near.w) < 1e-12 or abs(far.w) < 1e-12:
        return None
    near = glm.vec3(near) / near.w
    far = glm.vec3(far) / far.w
    direction = far - near
    if glm.length(direction) < 1e-12:
        return None
    return (
        np.asarray(near, dtype=float),
        np.asarray(glm.normalize(direction), dtype=float),
    )


def screen_to_world(camera: "Camera", x: float, y: float,
                    width: int, height: int,
                    working_plane: "Plane | None" = None):
    ray = screen_ray(camera, x, y, width, height)
    if ray is None:
        return None
    origin, direction = ray

    if working_plane is not None:
        n = np.asarray(working_plane.normal, dtype=float)
        o = np.asarray(working_plane.origin, dtype=float)
        denom = float(np.dot(n, direction))
        if abs(denom) < 1e-12:
            return None
        t = float(np.dot(n, o - origin)) / denom
        if t < 0:
            return None
        return glm.vec3(*(origin + t * direction))

    if abs(direction[2]) <= 1e-12:
        return None
    t = -origin[2] / direction[2]
    if t < 0:
        return None
    return glm.vec3(*(origin + t * direction))