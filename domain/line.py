# domain/line.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.id_manager import IDManager
from domain.vertex import Vertex


@dataclass
class Line:
    v1: Vertex = field(default_factory=Vertex)
    v2: Vertex = field(default_factory=Vertex)
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    width: float = 1.0
    style: str = "solid"
    label: str = ""
    visible: bool = True
    is_column: bool = False
    is_selected: bool = False
    unique_id: int = field(default_factory=IDManager.generate_id)
    pick_id: int = 0

    @property
    def vertices(self) -> tuple[Vertex, Vertex]:
        return (self.v1, self.v2)

    @property
    def length(self) -> float:
        return self.v1.distance_to(self.v2)

    def midpoint(self) -> tuple[float, float, float]:
        return (
            (self.v1.x + self.v2.x) * 0.5,
            (self.v1.y + self.v2.y) * 0.5,
            (self.v1.z + self.v2.z) * 0.5,
        )

    def direction(self) -> tuple[float, float, float]:
        dx = self.v2.x - self.v1.x
        dy = self.v2.y - self.v1.y
        dz = self.v2.z - self.v1.z
        L = math.hypot(dx, dy, dz)
        if L < 1e-9:
            return (1.0, 0.0, 0.0)
        return (dx / L, dy / L, dz / L)

    def endpoints(self):
        return (self.v1.coords, self.v2.coords)

    def copy(self) -> "Line":
        return Line(
            v1=self.v1.copy(), v2=self.v2.copy(),
            color=self.color, width=self.width, style=self.style,
            label=self.label, visible=self.visible, is_column=self.is_column,
        )