# render/lightingsystem.py

from dataclasses import dataclass, field
from typing import List


@dataclass
class LightingSystem:

    # ---------------------------------------------------------
    # LIGHTS
    # ---------------------------------------------------------

    # Ana ışık: üst-sol-ön
    pos: List[List[float]] = field(default_factory=lambda: [
        [-0.45, -0.60, 1.00],   # Key
        [ 0.65,  0.35, 0.55],   # Fill
    ])

    colors: List[List[float]] = field(default_factory=lambda: [
        [1.00, 0.97, 0.92],     # sıcak beyaz
        [0.82, 0.88, 1.00],     # hafif soğuk dolgu
    ])

    intensities: List[float] = field(default_factory=lambda: [
        1.25,
        0.35,
    ])

    # ---------------------------------------------------------
    # MATERIAL
    # ---------------------------------------------------------

    ambient = 0.28
    diffuse = 1.00

    # Daha mat / teknik görünüm
    specular = 0.12
    shininess = 24.0

    brightness = 1.0

    

    # ---------------------------------------------------------
    # PUBLIC
    # ---------------------------------------------------------

    def update_ubo(self, ubo, camera_pos):
        ubo.update(self, camera_pos)

    def set_pos(self, i, x, y, z):
        if 0 <= i < len(self.pos):
            self.pos[i] = [x, y, z]

    def set_color(self, i, r, g, b):
        if 0 <= i < len(self.colors):
            self.colors[i] = [r, g, b]

    def set_intensity(self, i, value):
        if 0 <= i < len(self.intensities):
            self.intensities[i] = value

    def cleanup(self):
        pass