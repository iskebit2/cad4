from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Light:
    direction: list[float]
    color: list[float]
    intensity: float
    name: str = ""
    enabled: bool = True


@dataclass
class LightingSettings:
    lights: list[Light] = field(default_factory=lambda: [
        Light(
            direction=[-0.45, -0.60, 1.00],
            color=[1.00, 0.97, 0.92],
            intensity=1.25,
            name="Key",
        ),
        Light(
            direction=[0.65, 0.35, 0.55],
            color=[0.82, 0.88, 1.00],
            intensity=0.35,
            name="Fill",
        ),
    ])
    ambient: float = 0.23
    diffuse: float = 1.00
    specular: float = 0.22
    shininess: float = 32.0
    brightness: float = 1.0

    @property
    def pos(self) -> list[list[float]]:
        return [light.direction for light in self.lights if light.enabled]

    @property
    def colors(self) -> list[list[float]]:
        return [light.color for light in self.lights if light.enabled]

    @property
    def intensities(self) -> list[float]:
        return [light.intensity for light in self.lights if light.enabled]

    def set_pos(self, index: int, x: float, y: float, z: float) -> None:
        light = self._enabled_light(index)
        if light is not None:
            light.direction = [x, y, z]

    def set_color(self, index: int, r: float, g: float, b: float) -> None:
        light = self._enabled_light(index)
        if light is not None:
            light.color = [r, g, b]

    def set_intensity(self, index: int, value: float) -> None:
        light = self._enabled_light(index)
        if light is not None:
            light.intensity = value

    def _enabled_light(self, index: int) -> Light | None:
        lights = [light for light in self.lights if light.enabled]
        return lights[index] if 0 <= index < len(lights) else None
