# core/camera.py
import numpy as np
import glm
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, Union
from logging_config import CadLogger
from logging_config import CadLogger

logger = CadLogger.get(__name__)

@dataclass
class Camera:
    """
    Dinamik Kamera Sınıfı - Model boyutuna göre otomatik ayarlanır
    - Unitless çalışır (mm, cm, m fark etmez)
    - Model bounds'a göre zoom limitleri ve hassasiyet ayarlanır
    """
    
    # ===== TEMEL PARAMETRELER =====
    target: glm.vec3 = field(default_factory=lambda: glm.vec3(0.0, 0.0, 0.0))
    distance: float = 50.0  # Kameranın target'a uzaklığı
    pitch: float = 30.0     # Yukarı/aşağı açı (derece)
    yaw: float = -45.0      # Sağ/sol açı (derece)
    
    # ===== PROJEKSİYON =====
    view_mode: str = "PERSPECTIVE"  # "PERSPECTIVE" veya "ORTHO"
    fov: float = 45.0        # Görüş açısı (derece)
    near_ratio: float = 0.001  # near = model_size * near_ratio
    far_ratio: float = 10.0    # far = model_size * far_ratio
    aspect_ratio: float = 1.0
    
    # ===== MODEL BOUNDS (dinamik) =====
    model_center: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0]))
    model_size: float = 1000.0
    model_updated: bool = False
    
    # ===== HASSASİYET (model_size'a göre otomatik) =====
    base_orbit_sensitivity: float = 0.005
    base_pan_sensitivity: float = 0.0005
    base_zoom_sensitivity: float = 1
    
    # ===== SINIRLAR (dinamik) =====
    min_distance_ratio: float = 0.1   # model_size * min_distance_ratio
    max_distance_ratio: float = 50.0  # model_size * max_distance_ratio
    min_pitch: float = -89.0
    max_pitch: float = 89.0
    
    # ===== CACHE =====
    _position: Optional[glm.vec3] = None
    _view_matrix: Optional[glm.mat4] = None
    _projection_matrix: Optional[glm.mat4] = None

    # ===== PLAN & VIEW FILTER =====
    active_plane: Optional[str] = None      # None / "XY" / "XZ" / "YZ"
    plane_offset: float = 0.0               # Düzlemin konumu (o eksende)
    plane_direction: str = "positive"       # "positive" / "negative" — hangi taraf görünsün
    
    view_preset: Optional[str] = None       # None / "front" / "back" / "top" / "bottom" / "left" / "right" / "iso"
    
    def __post_init__(self):
        """İlk pozisyonu hesapla"""
        self._update_position()
    
    # ----------------------------------------------------------------------
    # MODEL BOUNDS GÜNCELLEME
    # ----------------------------------------------------------------------
    
    def update_bounds(self, center: np.ndarray, size: float):
        """
        Model bounds'larını güncelle - her model yüklendiğinde çağrılır
        """
        self.model_center = center
        self.model_size = max(size, 1.0)  # Minimum 1 birim
        self.model_updated = True
        
        # Hedefi model merkezine ayarla
        self.target = glm.vec3(center[0], center[1], center[2])
        
        # Mesafeyi model boyutuna göre ayarla
        self.distance = self.model_size * 2.0
        
        logger.debug(f"Model bounds güncellendi:")
        logger.debug(f"  Center: ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})")
        logger.debug(f"  Size: {size:.2f}")
        logger.debug(f"  Distance: {self.distance:.2f}")
        
        self._update_position()
    
    # ----------------------------------------------------------------------
    # DİNAMİK HASSASİYET
    # ----------------------------------------------------------------------
    
    @property
    def orbit_sensitivity(self) -> float:
        """Model boyutuna göre orbit hassasiyeti"""
        return self.base_orbit_sensitivity * (self.model_size / 50000)
    
    @property
    def pan_sensitivity(self) -> float:
        """Model boyutuna göre pan hassasiyeti"""
        return self.base_pan_sensitivity * self.distance
    
    @property
    def zoom_sensitivity(self) -> float:
        """Model boyutuna göre zoom hassasiyeti"""
        return self.base_zoom_sensitivity * (self.model_size / 100)
    
    @property
    def min_distance(self) -> float:
        """Minimum kamera mesafesi"""
        return self.model_size * self.min_distance_ratio
    
    @property
    def max_distance(self) -> float:
        """Maksimum kamera mesafesi"""
        return self.model_size * self.max_distance_ratio
    
    @property
    def near(self) -> float:
        """Near plane - model boyutuna göre"""
        return max(self.model_size * self.near_ratio, 0.01)
    
    @property
    def far(self) -> float:
        """Far plane - model boyutuna göre"""
        return self.model_size * self.far_ratio
    
    # ----------------------------------------------------------------------
    # POZİSYON HESAPLAMA
    # ----------------------------------------------------------------------
    
    @property
    def position(self) -> glm.vec3:
        """Kamera pozisyonu"""
        if self._position is None:
            self._update_position()
        return self._position
    
    def _update_position(self):
        """Kamera pozisyonunu güncelle"""
        # Euler açılarını radyana çevir
        p = math.radians(self.pitch)
        y = math.radians(self.yaw)
        
        # Küresel koordinatlardan kartezyen
        self._position = glm.vec3(
            self.target.x + self.distance * math.cos(p) * math.cos(y),
            self.target.y + self.distance * math.cos(p) * math.sin(y),
            self.target.z + self.distance * math.sin(p)
        )
        
        # Cache'leri temizle
        self._view_matrix = None
        self._projection_matrix = None
    
    # ----------------------------------------------------------------------
    # MATRIX HESAPLAMALARI
    # ----------------------------------------------------------------------
    
    def get_view_matrix(self) -> glm.mat4:
        """View matrisini hesapla"""
        if self._view_matrix is None:
            self._view_matrix = glm.lookAt(
                self.position,
                self.target,
                glm.vec3(0.0, 0.0, 1.0)  # Z-up
            )
        return self._view_matrix
    
    def get_projection_matrix(self) -> glm.mat4:
        """Projeksiyon matrisini hesapla"""
        if self._projection_matrix is None:
            if self.view_mode == "PERSPECTIVE":
                self._projection_matrix = glm.perspective(
                    glm.radians(self.fov),
                    self.aspect_ratio,
                    self.near,
                    self.far
                )
            else:
                # Orthographic - model boyutuna göre
                ortho_size = self.distance * 0.5
                self._projection_matrix = glm.ortho(
                    -ortho_size * self.aspect_ratio,
                    ortho_size * self.aspect_ratio,
                    -ortho_size,
                    ortho_size,
                    self.near,
                    self.far
                )
        return self._projection_matrix
    
    def get_mvp_matrix(self, model_matrix: Optional[glm.mat4] = None) -> glm.mat4:
        """Model-View-Projection matrisi"""
        if model_matrix is None:
            model_matrix = glm.mat4(1.0)
        return self.get_projection_matrix() * self.get_view_matrix() * model_matrix
    
    # ----------------------------------------------------------------------
    # KAMERA KONTROLLERİ
    # ----------------------------------------------------------------------
    
    def orbit(self, dx: float, dy: float):
        """Target etrafında döndür"""
        self.yaw -= dx * self.orbit_sensitivity * 100
        self.pitch += dy * self.orbit_sensitivity * 100
        self.pitch = np.clip(self.pitch, self.min_pitch, self.max_pitch)
        self._update_position()
    
    def pan(self, dx: float, dy: float):
        """Target noktasını kaydır (kamera kaydırma)"""
        # Kamera yön vektörleri
        forward = glm.normalize(self.target - self.position)
        right = glm.normalize(glm.cross(forward, glm.vec3(0, 0, 1)))
        up = glm.normalize(glm.cross(right, forward))
        
        # Hareket miktarı
        speed = self.pan_sensitivity
        self.target += -right * dx * speed
        self.target += up * dy * speed
        
        self._update_position()
    
    def zoom(self, delta: float):
        """Zoom yap (mesafe değiştir)"""
        self.distance -= delta * self.zoom_sensitivity * 10
        self.distance = np.clip(self.distance, self.min_distance, self.max_distance)
        self._update_position()
    
    def focus_on_model(self):
        """Model'e odaklan"""
        self.distance = self.model_size * 2.0
        self._update_position()
        logger.debug(f"Focus: distance={self.distance:.2f}")
    
    def reset(self):
        """Kamerayı varsayılan konuma getir"""
        self.target = glm.vec3(self.model_center[0], self.model_center[1], self.model_center[2])
        self.distance = self.model_size * 2.0
        self.pitch = 30.0
        self.yaw = -45.0
        self.view_mode = "PERSPECTIVE"
        self._update_position()
        logger.debug("Reset")
    
    # ----------------------------------------------------------------------
    # PROJEKSİYON MODU
    # ----------------------------------------------------------------------
    
    def toggle_projection(self):
        """Perspektif/Ortho arasında geçiş yap"""
        self.view_mode = "ORTHO" if self.view_mode == "PERSPECTIVE" else "PERSPECTIVE"
        self._projection_matrix = None
        logger.debug(f"Mode: {self.view_mode}")
    
    def set_aspect(self, width: int, height: int):
        """En-boy oranını güncelle"""
        self.aspect_ratio = width / height if height > 0 else 1.0
        self._projection_matrix = None
    
    # ----------------------------------------------------------------------
    # DEBUG
    # ----------------------------------------------------------------------
    
    def print_info(self):
        """Kamera bilgilerini yazdır"""
        logger.debug(f"\n=== CAMERA INFO ===")
        logger.debug(f"Target: ({self.target.x:.2f}, {self.target.y:.2f}, {self.target.z:.2f})")
        logger.debug(f"Position: ({self.position.x:.2f}, {self.position.y:.2f}, {self.position.z:.2f})")
        logger.debug(f"Distance: {self.distance:.2f}")
        logger.debug(f"Pitch: {self.pitch:.1f}°, Yaw: {self.yaw:.1f}°")
        logger.debug(f"Mode: {self.view_mode}")
        logger.debug(f"Model size: {self.model_size:.2f}")
        logger.debug(f"Sensitivities - Orbit: {self.orbit_sensitivity:.4f}, Pan: {self.pan_sensitivity:.4f}, Zoom: {self.zoom_sensitivity:.4f}")
        logger.debug(f"Clipping - Near: {self.near:.2f}, Far: {self.far:.2f}")

    # ----------------------------------------------------------------------
    # PLAN & VIEW FILTER
    # ----------------------------------------------------------------------

    def set_plane_filter(self, plane, offset=0.0, direction="positive"):
        self.active_plane = plane
        self.plane_offset = offset
        self.plane_direction = direction

    def clear_plane_filter(self):
        self.active_plane = None
        self.plane_offset = 0.0

    def is_element_visible_by_plane(self, coords):
        if self.active_plane is None:
            return True
        x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
        if self.active_plane == "XY":
            axis_val = z
        elif self.active_plane == "XZ":
            axis_val = y
        elif self.active_plane == "YZ":
            axis_val = x
        else:
            return True
        if self.plane_direction == "positive":
            return axis_val >= self.plane_offset
        else:
            return axis_val <= self.plane_offset

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
        self._update_position()

    def clear_view_preset(self):
        self.view_preset = None
        self.view_mode = "PERSPECTIVE"
        self._projection_matrix = None