# render/orbit_camera.py
from __future__ import annotations
import math
import numpy as np
from pyglm import glm


class OrbitCamera:
    """Basit orbit kamera. Bir hedef noktası etrafında döner."""

    def __init__(self):
        self.target = np.zeros(3)
        self.distance = 1000.0
        self.yaw_deg = 45.0
        self.pitch_deg = 25.0
        self.fov = 45.0
        self.aspect = 1.0
        self.near = 1.0
        self.far = 100000.0
        self._view = glm.mat4(1.0)

    def set_target(self, p):
        self.target = np.asarray(p, dtype=float)

    def get_position(self) -> np.ndarray:
        cy = math.cos(math.radians(self.yaw_deg))
        sy = math.sin(math.radians(self.yaw_deg))
        cp = math.cos(math.radians(self.pitch_deg))
        sp = math.sin(math.radians(self.pitch_deg))
        offset = np.array([
            self.distance * cp * cy,
            self.distance * cp * sy,
            self.distance * sp,
        ])
        return self.target + offset

    def get_view_matrix(self):
        pos = self.get_position()
        up = np.array([0.0, 0.0, 1.0])
        f = self.target - pos
        f_n = np.linalg.norm(f)
        if f_n < 1e-9:
            f = np.array([0.0, 0.0, -1.0])
            f_n = 1.0
        f = f / f_n
        s = np.cross(f, up)
        s_n = np.linalg.norm(s)
        if s_n < 1e-9:
            s = np.array([1.0, 0.0, 0.0])
            s_n = 1.0
        s = s / s_n
        u = np.cross(s, f)

        m = np.eye(4, dtype=np.float32)
        m[0, :3] = s
        m[1, :3] = u
        m[2, :3] = -f
        m[0, 3] = -np.dot(s, pos)
        m[1, 3] = -np.dot(u, pos)
        m[2, 3] = np.dot(f, pos)
        # glm mat4 column-major
        return glm.mat4(
            float(m[0,0]), float(m[1,0]), float(m[2,0]), float(m[3,0]),
            float(m[0,1]), float(m[1,1]), float(m[2,1]), float(m[3,1]),
            float(m[0,2]), float(m[1,2]), float(m[2,2]), float(m[3,2]),
            float(m[0,3]), float(m[1,3]), float(m[2,3]), float(m[3,3]),
        )

    def get_projection_matrix(self):
        return glm.perspective(
            glm.radians(self.fov),
            max(self.aspect, 1e-3),
            self.near, self.far,
        )

    def render_info(self):
        """MathModelRenderer._render_shaded için (cpos, v, p)."""
        pos = self.get_position()
        return (
            glm.vec3(float(pos[0]), float(pos[1]), float(pos[2])),
            self.get_view_matrix(),
            self.get_projection_matrix(),
        )