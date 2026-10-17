# domain/plane.py
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np


class Plane:
    """
    3D düzlem. Tek doğruluk kaynağı.
    Normal + bir nokta ile tanımlanır.

    Kullanım:
        plane = Plane.from_polygon(poly)          # poly'nin düzlemi
        plane = Plane.from_3_points(p1, p2, p3)
        plane = Plane.from_point_normal(p0, n)

        d = plane.distance(pt)                    # işaretli mesafe
        d = plane.distance_abs(pt)                # mutlak mesafe
        proj = plane.project(pt)                  # düzleme izdüşüm
        u, v = plane.axes()                       # düzlem içi 2D eksenler
        uv = plane.to_2d(pt)                      # lokal 2D koordinat
        pt3 = plane.to_3d(uv)                     # geri 3D
        inside = plane.contains_2d(pt, poly.nodes) # poly içinde mi
    """

    __slots__ = ("origin", "normal", "u", "v")

    def __init__(self, origin: np.ndarray, normal: np.ndarray,
                 u: Optional[np.ndarray] = None):
        origin = np.asarray(origin, dtype=float)
        normal = np.asarray(normal, dtype=float)
        n_len = np.linalg.norm(normal)
        if n_len < 1e-12:
            raise ValueError("Plane normal sıfır olamaz")
        self.origin = origin
        self.normal = normal / n_len

        if u is None:
            # Normal'e dik rastgele bir u üret (deterministik)
            # Normal'in en küçük bileşeninden başla
            abs_n = np.abs(self.normal)
            min_axis = int(np.argmin(abs_n))
            seed = np.zeros(3)
            seed[min_axis] = 1.0
            u = np.cross(self.normal, seed)
            u_len = np.linalg.norm(u)
            if u_len < 1e-12:
                # Çok nadir: normal seed'e paralel
                seed = np.array([0.0, 1.0, 0.0])
                u = np.cross(self.normal, seed)
                u_len = np.linalg.norm(u)
            u = u / u_len

        self.u = u / np.linalg.norm(u)
        self.v = np.cross(self.normal, self.u)
        self.v = self.v / np.linalg.norm(self.v)

    # ---------------- CONSTRUCTORS ----------------

    @classmethod
    def from_point_normal(cls, p0, normal) -> "Plane":
        return cls(np.asarray(p0, dtype=float), np.asarray(normal, dtype=float))

    @classmethod
    def from_3_points(cls, p0, p1, p2) -> "Plane":
        p0 = np.asarray(p0, dtype=float)
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)
        n = np.cross(p1 - p0, p2 - p0)
        if np.linalg.norm(n) < 1e-12:
            raise ValueError("3 nokta collinear, düzlem tanımsız")
        return cls(p0, n)

    @classmethod
    def from_polygon(cls, poly) -> "Plane":
        """
        Poly'nin node'larından Newell metodu ile düzlem üretir.
        Node sırası CW/CCW önemli değil — normal yönü işaret dışında aynı.
        """
        nodes = poly.nodes
        if len(nodes) < 3:
            raise ValueError("Poly en az 3 node olmalı")

        # Newell metodu
        n = np.zeros(3)
        m = len(nodes)
        for i in range(m):
            a = nodes[i]
            b = nodes[(i + 1) % m]
            n[0] += (a.y - b.y) * (a.z + b.z)
            n[1] += (a.z - b.z) * (a.x + b.x)
            n[2] += (a.x - b.x) * (a.y + b.y)

        if np.linalg.norm(n) < 1e-12:
            raise ValueError("Poly dejenere, normal hesaplanamadı")

        origin = np.array([nodes[0].x, nodes[0].y, nodes[0].z])
        # u ekseni: ilk kenar yönü
        v0 = np.array([nodes[1].x - nodes[0].x,
                       nodes[1].y - nodes[0].y,
                       nodes[1].z - nodes[0].z])
        u_len = np.linalg.norm(v0)
        if u_len < 1e-12:
            u = None
        else:
            u = v0 / u_len
        return cls(origin, n, u)

    # ---------------- MESAFE / İZDÜŞÜM ----------------

    def distance(self, pt) -> float:
        """İşaretli mesafe: pozitif = normal yönünde, negatif = tersi."""
        return float(np.dot(self.normal, np.asarray(pt, dtype=float) - self.origin))

    def distance_abs(self, pt) -> float:
        """Mutlak mesafe."""
        return abs(self.distance(pt))

    def project(self, pt) -> np.ndarray:
        """Noktayı düzleme dik izdüşür."""
        pt = np.asarray(pt, dtype=float)
        return pt - self.normal * self.distance(pt)

    # ---------------- LOKAL 2D ----------------

    def to_2d(self, pt) -> Tuple[float, float]:
        """Dünya noktası → düzlem lokal 2D (u, v)."""
        rel = np.asarray(pt, dtype=float) - self.origin
        return float(np.dot(rel, self.u)), float(np.dot(rel, self.v))

    def to_3d(self, uv: Tuple[float, float]) -> np.ndarray:
        """Lokal 2D → dünya 3D."""
        return self.origin + uv[0] * self.u + uv[1] * self.v

    def polygon_to_2d(self, poly) -> List[Tuple[float, float]]:
        """Poly'nin node'larını lokal 2D'ye çevir."""
        return [self.to_2d((nd.x, nd.y, nd.z)) for nd in poly.nodes]

    # ---------------- POLY İÇİNDE Mİ ----------------

    def contains_2d(self, pt, poly_2d: List[Tuple[float, float]]) -> bool:
        """
        Nokta (dünya 3D) poly'nin 2D izdüşümü içinde mi?
        Ray-casting.
        """
        u, v = self.to_2d(pt)
        return self._point_in_polygon_2d(u, v, poly_2d)

    @staticmethod
    def _point_in_polygon_2d(x: float, y: float,
                              poly_2d: List[Tuple[float, float]]) -> bool:
        inside = False
        n = len(poly_2d)
        j = n - 1
        for i in range(n):
            xi, yi = poly_2d[i]
            xj, yj = poly_2d[j]
            if ((yi > y) != (yj > y)) and \
               (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    # ---------------- DEBUG ----------------

    def __repr__(self):
        return (f"Plane(origin=({self.origin[0]:.2f},{self.origin[1]:.2f},{self.origin[2]:.2f}), "
                f"normal=({self.normal[0]:.4f},{self.normal[1]:.4f},{self.normal[2]:.4f}))")