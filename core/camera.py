# core/camera.py
import glm
import numpy as np

glm.silence(2)
import math
from dataclasses import dataclass, field

from logging_config import CadLogger

logger = CadLogger.get(__name__)


@dataclass
class Camera:
    """
    Milimetre/Metre uyumlu, yapısal aks sistemleri için optimize edilmiş CAD Kamerası.
    """

    # --- Hedef ve konum ---
    target: glm.vec3 = field(default_factory=lambda: glm.vec3(0.0, 0.0, 0.0))
    distance: float = 15000.0
    pitch: float = 30.0
    yaw: float = -45.0

    # --- Model bounds (kullanıcı biriminde, ham - örn. mm) ---
    model_center: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0]))
    model_size: float = 10000.0  # Varsayılan aks aralığına uygun başlangıç

    # --- Projeksiyon ---
    view_mode: str = "PERSPECTIVE"
    fov: float = 45.0
    near_ratio: float = 0.00001
    far_ratio: float = 50.0
    aspect_ratio: float = 1.0

    # --- Hassasiyetler (Model boyutuna orantılı dinamik) ---
    ORBIT_SENSITIVITY: float = 0.3        # derece / piksel
    PAN_RATIO: float = 0.0008             # distance oranlı pan hızı
    ZOOM_RATIO: float = 0.12              # logaritmik zoom hassasiyeti

    # --- Mesafe sınırları ---
    min_distance_ratio: float = 0.001
    max_distance_ratio: float = 500.0

    # --- Açı sınırları ---
    min_pitch: float = -89.0
    max_pitch: float = 89.0

    # --- Cache ---
    _position: glm.vec3 | None = None
    _view_matrix: glm.mat4 | None = None
    _projection_matrix: glm.mat4 | None = None

    # --- View / Plan filter ---
    active_plane: str | None = None
    plane_offset: float = 0.0
    plane_direction: str = "positive"
    view_preset: str | None = None

    section_active: bool = False
    section_normal: tuple = (0.0, 0.0, 1.0)
    section_origin: tuple = (0.0, 0.0, 0.0)
    section_min: float = -1e30
    section_max: float = 1e30

    up: glm.vec3 = field(default_factory=lambda: glm.vec3(0.0, 0.0, 1.0))

    def __post_init__(self):
        self._update_position()

    # ==================================================================
    # Ölçek ve Kırpma Düzlemleri
    # ==================================================================
    @property
    def min_distance(self) -> float:
        return max(self.model_size * self.min_distance_ratio, 1.0)

    @property
    def max_distance(self) -> float:
        return self.model_size * self.max_distance_ratio

    @property
    def near(self) -> float:
        # Büyük mm modellerde near kırpmasını önlemek için mesafeye bağlı dinamik alt sınır
        return max(self.distance * self.near_ratio, 0.1)

    @property
    def far(self) -> float:
        return max(self.distance * self.far_ratio, self.model_size * self.far_ratio)

    # ==================================================================
    # Model bounds & Odaklanma
    # ==================================================================
    def update_bounds(self, center, size):
        self.model_center = np.asarray(center, dtype=float)
        self.model_size = max(float(size), 1.0)
        self.target = glm.vec3(*self.model_center)
        # Kamerayı tüm modeli kapsayacak güvenli mesafeye konumlandır
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
        self.view_mode = "PERSPECTIVE"
        self._invalidate()

    # ==================================================================
    # Kontroller
    # ==================================================================
    def orbit(self, dx, dy):
        self.yaw -= dx * self.ORBIT_SENSITIVITY
        self.pitch += dy * self.ORBIT_SENSITIVITY
        self.pitch = float(np.clip(self.pitch, self.min_pitch, self.max_pitch))
        self._invalidate()

    def pan(self, dx, dy):
        forward = glm.normalize(self.target - self.position)
        
        # Kamera up'ı ile doğru right hesapla (gimbal-safe)
        up_ref = self.up
        # forward ile up_ref neredeyse paralel olmasın
        if abs(glm.dot(forward, up_ref)) > 0.999:
            up_ref = glm.vec3(0.0, 1.0, 0.0)   # yedek
        
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

    # ==================================================================
    # Konum ve Matrisler
    # ==================================================================
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
        self._view_matrix = None

    def _invalidate(self):
        self._update_position()
        self._projection_matrix = None
        self._view_matrix = None

    def get_view_matrix(self):
        if self._view_matrix is None:
            self._view_matrix = glm.lookAt(
                self.position, self.target, self.up
            )
        return self._view_matrix

    def get_projection_matrix(self):
        if self._projection_matrix is None:
            if self.view_mode == "PERSPECTIVE":
                self._projection_matrix = glm.perspective(
                    glm.radians(self.fov), self.aspect_ratio, self.near, self.far
                )
            else:
                # Ortografik görünüm için boyutu doğrudan model boyutuna ve mesafeye endeksle
                ortho_size = (self.model_size * 0.75) * (self.distance / (self.model_size * 1.5))
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
            "front":  {"pitch": 0,   "yaw": -90,  "view_mode": "ORTHO"},
            "back":   {"pitch": 0,   "yaw": 90,   "view_mode": "ORTHO"},
            "top":    {"pitch": 89,  "yaw": -90,  "view_mode": "ORTHO"},
            "bottom": {"pitch": -89, "yaw": -90,  "view_mode": "ORTHO"},
            "left":   {"pitch": 0,   "yaw": 180,  "view_mode": "ORTHO"},
            "right":  {"pitch": 0,   "yaw": 0,    "view_mode": "ORTHO"},
            "iso":    {"pitch": 30,  "yaw": -45,  "view_mode": "PERSPECTIVE"},
        }
        if preset not in presets:
            return
        p = presets[preset]
        self.pitch = p["pitch"]
        self.yaw = p["yaw"]
        self.view_mode = p["view_mode"]
        self.view_preset = preset
        self._invalidate()

    def clear_view_preset(self):
        self.view_preset = None

        # ==================================================================
    # Section filter
    # ==================================================================
    def set_section_filter(self, normal, origin, min_s, max_s):
        """Aktif UCS'ye göre alt/üst aralık filtresi."""
        self.section_normal = (float(normal[0]), float(normal[1]), float(normal[2]))
        self.section_origin = (float(origin[0]), float(origin[1]), float(origin[2]))
        self.section_min = float(min_s)
        self.section_max = float(max_s)
        self.section_active = True

    def clear_section_filter(self):
        self.section_active = False

    def is_element_visible_by_section(self, coords):
        if not self.section_active:
            return True
        nx, ny, nz = self.section_normal
        ox, oy, oz = self.section_origin
        s = nx * (coords[0] - ox) + ny * (coords[1] - oy) + nz * (coords[2] - oz)
        return self.section_min <= s <= self.section_max
    
    def look_at_plane(self, origin, u, v, n, fit_radius=None):
        origin = glm.vec3(*origin) if not isinstance(origin, glm.vec3) else origin
        n = glm.normalize(glm.vec3(*n) if not isinstance(n, glm.vec3) else n)
        v = glm.normalize(glm.vec3(*v) if not isinstance(v, glm.vec3) else v)

        d = fit_radius if fit_radius else max(self.model_size, 1000.0) * 1.2

        self.target = origin
        self.distance = d
        self.pitch = math.degrees(math.asin(max(-1.0, min(1.0, n.z))))
        self.yaw   = math.degrees(math.atan2(n.y, n.x))

        # KRİTİK: view matrix'in up'ı düzlemin V ekseni olmalı
        self.up = v

        self._invalidate()