# geometry/polygon_builder.py
import numpy as np
from typing import Tuple
from domain.element import Polygon
import mapbox_earcut as earcut
from logging_config import CadLogger

from logging_config import CadLogger

logger = CadLogger.get(__name__)


def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0, 0, 1], dtype=np.float32)
    return v / n


class PolygonBuilder:
    """
    Düz poligon — extrude YOK.
    Kapalı döngü, düzlem normaline göre 2D triangulate edilir.
    """

    def build(self, polygon: Polygon) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) < 3:
            return np.array([]), np.array([]), np.array([])

        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = normalize(np.cross(v1, v2))

        if abs(normal[2]) > 0.9:
            u, v = np.array([1, 0, 0]), np.array([0, 1, 0])
        elif abs(normal[1]) > 0.9:
            u, v = np.array([1, 0, 0]), np.array([0, 0, 1])
        elif abs(normal[0]) > 0.9:
            u, v = np.array([0, 1, 0]), np.array([0, 0, 1])
        else:
            world_up = np.array([0, 0, 1])
            u = normalize(np.cross(normal, world_up))
            v = normalize(np.cross(normal, u))

        center = points.mean(0)
        pts_2d = np.array(
            [[(p - center) @ u, (p - center) @ v] for p in points],
            dtype=np.float32
        )

        rings = np.array([len(pts_2d)], dtype=np.uint32)
        tri = earcut.triangulate_float32(pts_2d, rings).tolist()

        verts = []
        for p in points:
            verts.extend([p[0], p[1], p[2], normal[0], normal[1], normal[2]])

        # Çift yönlü yüzey için indisler... kaldırıldı
        idxs = list(tri)
        # for i in range(0, len(tri), 3):
        #     idxs.extend([tri[i], tri[i+2], tri[i+1]])

        # Dolgu Rengi
        base_color = polygon.color if hasattr(polygon, 'color') else [0.8, 0.3, 0.8]
        if polygon.is_selected:
            color = np.array([1.0, 0.5, 0.0], dtype=np.float32)
        else:
            # Buradaki [:3] dilimlemesi RGBA gelse bile sadece RGB kısmını alır
            color = np.array(base_color[:3], dtype=np.float32)

        colors = np.tile(color, (len(points), 1))

        return (
            np.array(verts, dtype=np.float32),
            colors,
            np.array(idxs, dtype=np.uint32)
        )

    def build_simple_lines(self, polygon: Polygon) -> np.ndarray:
        """Sınır çizgileri için (Beyaz renkli kenar telleri)"""
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) < 2:
            return np.array([], dtype=np.float32)

        v1 = points[1] - points[0]
        v2 = points[2] - points[0] if len(points) >= 3 else np.array([0, 0, 1], dtype=np.float32)
        normal = normalize(np.cross(v1, v2))

        N = len(points)
        verts = []
        for i in range(N):
            j = (i + 1) % N
            p0 = points[i]
            p1 = points[j]
            verts.extend([p0[0], p0[1], p0[2], normal[0], normal[1], normal[2]])
            verts.extend([p1[0], p1[1], p1[2], normal[0], normal[1], normal[2]])

        return np.array(verts, dtype=np.float32)

    def build_lines(self, polygon: Polygon) -> np.ndarray:
        """
        Wireframe mod için — sadece kenar çizgileri.
        Her kenar için 2 index (kenarın iki ucu).
        """
        N = len(polygon.nodes)
        if N < 3:
            return np.array([], dtype=np.uint32)

        line_indices = []
        for i in range(N):
            j = (i + 1) % N
            line_indices.extend([i, j])

        return np.array(line_indices, dtype=np.uint32)

    def build_simple_points(self, polygon: Polygon) -> np.ndarray:
        """Simple mod için sadece köşe noktaları (6 float per nokta)."""
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) == 0:
            return np.array([], dtype=np.float32)

        verts = []
        for p in points:
            verts.extend([p[0], p[1], p[2], 0.0, 0.0, 1.0])
        return np.array(verts, dtype=np.float32)
    
    def build_simple(self, polygon: Polygon) -> np.ndarray:
        """
        Simple modda transparan poligon dolgusu (GL_TRIANGLES) için vertex üretir.
        """
        verts, _, idxs = self.build(polygon)
        if len(verts) == 0 or len(idxs) == 0:
            return np.array([], dtype=np.float32)

        # Index listesinden sıralı üçgen vertex array'i oluştur (GL_TRIANGLES için)
        # verts verisi her vertex için 6 float [x,y,z, nx,ny,nz] içeriyor
        stride = 6
        tri_verts = []
        for idx in idxs:
            start_i = idx * stride
            tri_verts.extend(verts[start_i : start_i + stride])

        return np.array(tri_verts, dtype=np.float32)