# geometry/link_builder.py
import numpy as np
from typing import Tuple
from domain.element import Link
import math

def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0, 0, 1])
    return v / n

class LinkBuilder:
    
    def build(self, link: Link) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Basit link - sadece pos ve norm (6 float)"""
        start = np.array([link.node_i.x, link.node_i.y, link.node_i.z], dtype=np.float32)
        end = np.array([link.node_j.x, link.node_j.y, link.node_j.z], dtype=np.float32)
        
        axis = end - start
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return np.array([]), np.array([]), np.array([])
        
        # Sadece bir kalın çizgi (basit quad)
        dir = axis / length
        
        # Dik vektörler bul
        up = np.array([0, 0, 1])
        if abs(np.dot(dir, up)) > 0.99:
            right = np.array([1, 0, 0])
        else:
            right = np.cross(up, dir)
            right = right / np.linalg.norm(right)
        up = np.cross(dir, right)
        up = up / np.linalg.norm(up)
        
        thickness = 15.0  # Daha kalın
        
        # 4 köşe noktası
        p1 = start + right * thickness + up * thickness
        p2 = start - right * thickness + up * thickness
        p3 = end - right * thickness - up * thickness
        p4 = end + right * thickness - up * thickness
        
        # Vertex'ler: pos3 + norm3 (norm = dir)
        verts = []
        for p in [p1, p2, p3, p4]:
            verts.extend([p[0], p[1], p[2], dir[0], dir[1], dir[2]])
        
        # İndeksler (2 üçgen)
        idxs = [0, 1, 2, 0, 2, 3]
        
        # Renkler
        color = np.array([1, 0, 0] if link.is_selected else [0, 1, 0], dtype=np.float32)
        colors = np.tile(color, (4, 1))
        
        return np.array(verts, dtype=np.float32), colors, np.array(idxs, dtype=np.uint32)

    def build_simple_lines(self, link: Link) -> np.ndarray:
        """Link'in sadece merkez çizgisi."""
        start = np.array([link.node_i.x, link.node_i.y, link.node_i.z], dtype=np.float32)
        end = np.array([link.node_j.x, link.node_j.y, link.node_j.z], dtype=np.float32)
        
        axis = end - start
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return np.array([], dtype=np.float32)
        
        d = axis / length
        verts = np.array([
            start[0], start[1], start[2], d[0], d[1], d[2],
            end[0],   end[1],   end[2],   d[0], d[1], d[2]
        ], dtype=np.float32)
        return verts