from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from pyglm import glm

glm.silence(2)


@dataclass
class Camera:
    target: glm.vec3 = field(default_factory=lambda: glm.vec3(0.0, 0.0, 0.0))
    distance: float = 15000.0
    pitch: float = 30.0
    yaw: float = -45.0

    model_center: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0]))
    model_size: float = 10000.0

    view_mode: str = "PERSPECTIVE"
    fov: float = 45.0
    near_ratio: float = 0.00001
    far_ratio: float = 50.0
    aspect_ratio: float = 1.0

    ORBIT_SENSITIVITY: float = 0.3
    PAN_RATIO: float = 0.0008
    ZOOM_RATIO: float = 0.12

    min_distance_ratio: float = 0.001
    max_distance_ratio: float = 500.0

    min_pitch: float = -89.0
    max_pitch: float = 89.0

    _position: glm.vec3 | None = None
    _view_matrix: glm.mat4 | None = None
    _projection_matrix: glm.mat4 | None = None
    _saved_3d_view: dict | None = None

    view_preset: str | None = None
    up: glm.vec3 = field(default_factory=lambda: glm.vec3(0.0, 0.0, 1.0))
    is_2d: bool = False

    def __post_init__(self):
        self._update_position()

    @property
    def min_distance(self) -> float:
        return max(self.model_size * self.min_distance_ratio, 1.0)

    @property
    def max_distance(self) -> float:
        return self.model_size * self.max_distance_ratio

    @property
    def near(self) -> float:
        return max(self.distance * self.near_ratio, 0.1)

    @property
    def far(self) -> float:
        return max(self.distance * self.far_ratio, self.model_size * self.far_ratio)

    def update_bounds(self, center, size):
        self.model_center = np.asarray(center, dtype=float)
        self.model_size = max(float(size), 1.0)
        self.target = glm.vec3(*self.model_center)
        self.distance = self.model_size * 1.1
        self._invalidate()

    def focus_on_model(self):
        self.distance = self.model_size * 1.1
        self._invalidate()

    def reset(self):
        self.target = glm.vec3(*self.model_center)
        self.distance = self.model_size * 1.1
        self.pitch = 30.0
        self.yaw = -45.0
        self.up = glm.vec3(0.0, 0.0, 1.0)
        self.view_mode = "PERSPECTIVE"
        self.view_preset = None
        self.is_2d = False
        self._invalidate()

    def set_top_view(self) -> None:
        self.pitch = 90.0
        self.yaw = -90.0
        self.up = glm.vec3(0.0, 1.0, 0.0)
        self.view_mode = "ORTHO"
        self.view_preset = "top"
        self.distance = max(self.model_size * 2.0, 2000.0)
        self._invalidate()

    def orbit(self, dx, dy):
        if self._is_2d_locked():
            return
        if self.view_preset == "top":
            self.pitch = 89.0
        self.view_preset = None
        self.yaw -= dx * self.ORBIT_SENSITIVITY
        self.pitch += dy * self.ORBIT_SENSITIVITY
        self.pitch = float(np.clip(self.pitch, self.min_pitch, self.max_pitch))
        self._invalidate()

    def _is_2d_locked(self) -> bool:
        return bool(self.is_2d or self.view_preset == "working_plane")

    def pan(self, dx, dy):
        forward = glm.normalize(self.target - self.position)
        up_ref = self.up
        if abs(glm.dot(forward, up_ref)) > 0.999:
            up_ref = glm.vec3(0.0, 1.0, 0.0)
        right = glm.normalize(glm.cross(forward, up_ref))
        up = glm.normalize(glm.cross(right, forward))
        speed = self.distance * self.PAN_RATIO
        self.target += -right * dx * speed
        self.target += up * dy * speed
        self._invalidate()

    def zoom(self, delta):
        factor = math.exp(-delta * self.ZOOM_RATIO)
        new_distance = self.distance * factor
        self.distance = float(np.clip(new_distance, self.min_distance, self.max_distance))
        self._invalidate()

    @property
    def position(self) -> glm.vec3:
        if self._position is None:
            self._update_position()
        return self._position

    def _update_position(self):
        p = math.radians(self.pitch)
        y = math.radians(self.yaw)
        self._position = glm.vec3(
            self.target.x + self.distance * math.cos(p) * math.cos(y),
            self.target.y + self.distance * math.cos(p) * math.sin(y),
            self.target.z + self.distance * math.sin(p),
        )

    def _invalidate(self):
        self._update_position()
        self._projection_matrix = None
        self._view_matrix = None

    def get_view_matrix(self):
        if self._view_matrix is None:
            self._view_matrix = glm.lookAt(self.position, self.target, self.up)
        return self._view_matrix

    def get_projection_matrix(self):
        if self._projection_matrix is None:
            if self.view_mode == "PERSPECTIVE":
                self._projection_matrix = glm.perspective(
                    glm.radians(self.fov), self.aspect_ratio, self.near, self.far
                )
            else:
                ortho_size = self.distance * 0.5
                self._projection_matrix = glm.ortho(
                    -ortho_size * self.aspect_ratio,
                    ortho_size * self.aspect_ratio,
                    -ortho_size, ortho_size,
                    self.near, self.far,
                )
        return self._projection_matrix

    def get_mvp_matrix(self, model_matrix=None):
        if model_matrix is None:
            model_matrix = glm.mat4(1.0)
        return self.get_projection_matrix() * self.get_view_matrix() * model_matrix

    def set_aspect(self, w, h):
        self.aspect_ratio = w / h if h > 0 else 1.0
        self._projection_matrix = None

    def toggle_projection(self):
        self.view_mode = "ORTHO" if self.view_mode == "PERSPECTIVE" else "PERSPECTIVE"
        self._projection_matrix = None

    def set_view_preset(self, preset):
        presets = {
            "front":  {"pitch": 0,   "yaw": -90,  "view_mode": "ORTHO", "up": (0, 0, 1)},
            "back":   {"pitch": 0,   "yaw": 90,   "view_mode": "ORTHO", "up": (0, 0, 1)},
            "top":    {"pitch": 90,  "yaw": -90,  "view_mode": "ORTHO", "up": (0, 1, 0)},
            "bottom": {"pitch": -90, "yaw": -90,  "view_mode": "ORTHO", "up": (0, 1, 0)},
            "left":   {"pitch": 0,   "yaw": 180,  "view_mode": "ORTHO", "up": (0, 0, 1)},
            "right":  {"pitch": 0,   "yaw": 0,    "view_mode": "ORTHO", "up": (0, 0, 1)},
            "iso":    {"pitch": 30,  "yaw": -45,  "view_mode": "PERSPECTIVE", "up": (0, 0, 1)},
            "iso_sw": {"pitch": 30,  "yaw": 45,   "view_mode": "PERSPECTIVE", "up": (0, 0, 1)},
            "iso_se": {"pitch": 30,  "yaw": 135,  "view_mode": "PERSPECTIVE", "up": (0, 0, 1)},
            "iso_ne": {"pitch": 30,  "yaw": -135, "view_mode": "PERSPECTIVE", "up": (0, 0, 1)},
            "iso_nw": {"pitch": 30,  "yaw": -45,  "view_mode": "PERSPECTIVE", "up": (0, 0, 1)},
        }
        if preset not in presets:
            return
        p = presets[preset]
        self.pitch = p["pitch"]
        self.yaw = p["yaw"]
        self.up = glm.vec3(*p["up"])
        self.view_mode = p["view_mode"]
        self.view_preset = preset
        self.is_2d = False
        self._invalidate()

    def clear_view_preset(self):
        self.view_preset = None

    def look_at_plane(self, origin, u, v, n, fit_radius=None):
        origin = glm.vec3(*origin) if not isinstance(origin, glm.vec3) else origin
        n = glm.normalize(glm.vec3(*n) if not isinstance(n, glm.vec3) else n)
        v = glm.normalize(glm.vec3(*v) if not isinstance(v, glm.vec3) else v)

        d = (
            float(fit_radius) * 2.0
            if fit_radius is not None
            else max(self.model_size, 1000.0) * 1.2
        )

        self.target = origin
        self.distance = d
        self.pitch = math.degrees(math.asin(max(-1.0, min(1.0, n.z))))
        self.yaw = math.degrees(math.atan2(n.y, n.x))
        self.up = v
        self.view_mode = "ORTHO"
        self.view_preset = "working_plane"
        self.is_2d = True
        self._invalidate()

    def look_at_plane_iso(self, origin, u, v, n, fit_radius=None):
        origin = glm.vec3(*origin) if not isinstance(origin, glm.vec3) else origin
        u = glm.normalize(glm.vec3(*u) if not isinstance(u, glm.vec3) else u)
        v = glm.normalize(glm.vec3(*v) if not isinstance(v, glm.vec3) else v)
        n = glm.normalize(glm.vec3(*n) if not isinstance(n, glm.vec3) else n)

        d = (
            float(fit_radius)
            if fit_radius is not None
            else max(self.model_size, 1000.0) * 1.4
        )

        az = math.radians(-45.0)
        el = math.radians(30.0)
        view_dir = glm.normalize(
            math.cos(el) * (math.cos(az) * u + math.sin(az) * v)
            + math.sin(el) * n
        )

        self.target = origin
        self.distance = d
        self.pitch = math.degrees(math.asin(max(-1.0, min(1.0, view_dir.z))))
        self.yaw = math.degrees(math.atan2(view_dir.y, view_dir.x))
        self.up = n
        self.view_mode = "PERSPECTIVE"
        self.view_preset = None
        self.is_2d = False
        self._invalidate()

    def save_view(self) -> None:
        self._saved_3d_view = {
            "target": (float(self.target.x), float(self.target.y), float(self.target.z)),
            "distance": float(self.distance),
            "pitch": float(self.pitch),
            "yaw": float(self.yaw),
            "up": (float(self.up.x), float(self.up.y), float(self.up.z)),
            "view_mode": self.view_mode,
            "view_preset": self.view_preset,
        }

    def restore_view(self) -> bool:
        s = self._saved_3d_view
        if s is None:
            return False
        self.target = glm.vec3(*s["target"])
        self.distance = s["distance"]
        self.pitch = s["pitch"]
        self.yaw = s["yaw"]
        self.up = glm.vec3(*s["up"])
        self.view_mode = s["view_mode"]
        self.view_preset = s["view_preset"]
        self.is_2d = False
        self._saved_3d_view = None
        self._invalidate()
        return True