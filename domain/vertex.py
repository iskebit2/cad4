# domain/vertex.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.id_manager import IDManager


@dataclass
class Vertex:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    label: str = ""
    source_node_id: int | None = None
    unique_id: int = field(default_factory=IDManager.generate_id)

    @property
    def coords(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def distance_to(self, other: "Vertex") -> float:
        return math.dist(self.coords, other.coords)

    def copy(self) -> "Vertex":
        return Vertex(
            x=self.x, y=self.y, z=self.z,
            label=self.label, source_node_id=self.source_node_id,
        )