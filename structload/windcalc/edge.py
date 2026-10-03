#windcalc/edge.py

from dataclasses import dataclass, field
import numpy as np
from typing import List, Dict, Tuple, Optional, Union, Any

@dataclass
class Edge:
    """
    Saf geometrik kenar verisi. Rüzgar analizi EdgeAnalyzer tarafından yapılır.
    """
    index: int
    p1: np.ndarray
    p2: np.ndarray
    p1_2d: np.ndarray
    p2_2d: np.ndarray

    vector: np.ndarray
    length: float
    direction: Optional[np.ndarray]

    vector_2d: np.ndarray
    length_2d: float
    direction_2d: Optional[np.ndarray]

    # EdgeAnalyzer tarafından doldurulur
    pos_front: Optional[float] = None
    pos_back: Optional[float] = None

    angle: Optional[float] = None
    exposed: bool = False
    leading: bool = False
    vertical: bool = False
    _global: bool = False

    shared: List[Dict[str, Any]] = field(default_factory=list)
    same_axis: List[Dict[str, Any]] = field(default_factory=list)

    wind_to_2d: Optional[np.ndarray] = None
    pos_front_pt: Optional[np.ndarray] = None
    log: str = ""
    @property
    def is_shared(self) -> bool:
        """Kenarın başka bir yüzeyle tam olarak çakışıp çakışmadığını döndürür."""
        return any(entry.get("same_edge", False) for entry in self.shared)

    @classmethod
    def from_points(cls, i: int, plane) -> "Edge":
        p1 = plane.pts_3d[i]
        p2 = plane.pts_3d[(i + 1) % plane.n_pts]

        p1_2d = plane.pts_2d[i]
        p2_2d = plane.pts_2d[(i + 1) % plane.n_pts]

        vector = p2 - p1
        length = float(np.linalg.norm(vector))
        direction = vector / length if length >= 1e-12 else None

        vector_2d = p2_2d - p1_2d
        length_2d = float(np.linalg.norm(vector_2d))
        direction_2d = vector_2d / length_2d if length_2d >= 1e-12 else None

        return cls(
            index=i,
            p1=p1, p2=p2,
            p1_2d=p1_2d, p2_2d=p2_2d,
            vector=vector,
            length=length,
            direction=direction,
            vector_2d=vector_2d,
            length_2d=length_2d,
            direction_2d=direction_2d,
        )

    # ------------------------------------------------------------------
    # Geometrik karşılaştırma (rüzgardan bağımsız)
    # ------------------------------------------------------------------

    def same_axis_2d(
        self,
        other: "Edge",
        angle_tol: float = 2.0,
        distance_tol: float = 1e-6,
    ) -> bool:
        d1, d2 = self.direction_2d, other.direction_2d
        if d1 is None or d2 is None:
            return False

        # Vektör doğrultusu karşılaştırması
        dot = float(np.clip(abs(np.dot(d1, d2)), -1.0, 1.0))
        if np.degrees(np.arccos(dot)) > angle_tol:
            return False

        # Dik uzaklık hesabı
        normal = np.array([-d1[1], d1[0]])
        distance = abs(float(np.dot(other.p1_2d - self.p1_2d, normal)))
        return distance <= distance_tol

    def is_same_edge(self, other: "Edge", tol: float = 1e-6) -> bool:
        """3D düzlemde veya 2D düzlemde kenarların birebir aynı olup olmadığını kontrol eder."""
        same_orient = np.allclose(self.p1, other.p1, atol=tol) and np.allclose(self.p2, other.p2, atol=tol)
        opposite_orient = np.allclose(self.p1, other.p2, atol=tol) and np.allclose(self.p2, other.p1, atol=tol)
        return same_orient or opposite_orient

    def reset_analysis(self) -> None:
        """Rüzgar analizine bağlı alanları sıfırla."""
        self.pos_front = None
        self.pos_back = None
        self.angle = None
        self.exposed = False
        self.leading = False
        self.vertical = (self.direction_2d is None)
        self.shared = []
        self.same_axis = []
        self.log = ""
        self.wind_to_2d = None
        self.pos_front_pt = None
