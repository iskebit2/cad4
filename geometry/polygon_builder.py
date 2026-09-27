# geometry/polygon_builder.py
import numpy as np
from typing import Tuple
from domain.element import Polygon
import mapbox_earcut as earcut
import logging

logger = logging.getLogger(__name__)


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
        """
        Shaded render için: kenar + dolgu (triangulated).
        Returns: (vertices, colors, indices)
        vertices: [x,y,z, nx,ny,nz] per vertex (6 float)
        """
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) < 3:
            return np.array([]), np.array([]), np.array([])

        # Düzlem normali (ilk 3 noktadan)
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = normalize(np.cross(v1, v2))

        # 2D projeksiyon için eksenler
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

        # Ear-clipping triangulation
        rings = np.array([len(pts_2d)], dtype=np.uint32)
        tri = earcut.triangulate_float32(pts_2d, rings).tolist()

        # Vertex'ler: her köşe için pos + normal
        verts = []
        for p in points:
            verts.extend([p[0], p[1], p[2], normal[0], normal[1], normal[2]])

        # İndeksler
        idxs = list(tri)

        # Renkler
        color = np.array(
            [1.0, 0.5, 0.0] if polygon.is_selected else polygon.color,
            dtype=np.float32
        )
        colors = np.tile(color, (len(points), 1))

        return (
            np.array(verts, dtype=np.float32),
            colors,
            np.array(idxs, dtype=np.uint32)
        )

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

    def build_simple_lines(self, polygon: Polygon) -> np.ndarray:
        """
        Simple mod için — kapalı döngü (GL_LINES ile).
        Her kenar için 2 nokta (pos3+normal3).
        """
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) < 2:
            return np.array([], dtype=np.float32)

        # Normal
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

    def build_simple_points(self, polygon: Polygon) -> np.ndarray:
        """Simple mod için sadece köşe noktaları (6 float per nokta)."""
        points = np.array([[n.x, n.y, n.z] for n in polygon.nodes], dtype=np.float32)
        if len(points) == 0:
            return np.array([], dtype=np.float32)

        verts = []
        for p in points:
            verts.extend([p[0], p[1], p[2], 0.0, 0.0, 1.0])
        return np.array(verts, dtype=np.float32)