# geometry/node_builder.py
import numpy as np
from typing import Tuple, Dict, Optional
from domain.element import Node, Restraint
import math

def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0, 0, 1])
    return v / n

class NodeBuilder:
    def __init__(self):
        # Birim şekiller (XY düzlemi, z=0, merkezde)
        self.size = 1.0  # Node boyutu
        self.segments = 16
        self.shapes: Dict[str, np.ndarray] = {}
        self._rebuild_shapes()

    def _rebuild_shapes(self):
        """self.size'a göre şekilleri yeniden üret"""
        radius = self.size / 2
        self.shapes = {
            "triangle": np.array([
                [0, radius, 0],
                [radius, -radius, 0],
                [-radius, -radius, 0]
            ], dtype=np.float32),

            "square": np.array([
                [-radius, radius, 0],
                [radius, radius, 0],
                [radius, -radius, 0],
                [-radius, -radius, 0]
            ], dtype=np.float32),

            "circle": self._create_circle(radius),
        }

    def set_size(self, size: float) -> bool:
        """
        Node sembol boyutunu ayarla.
        Returns: True -> gerçekten değişti, False -> zaten aynıydı
        """
        size = float(size)
        if size <= 0:
            return False
        if abs(self.size - size) < 1e-6:
            return False
        self.size = size
        self._rebuild_shapes()
        return True
    
    def _create_circle(self, radius):
        """Daire oluştur - merkezde, çevre noktaları"""
        circle = []
        # Merkez nokta (0,0,0)
        circle.append([0, 0, 0])
        # Çevre noktaları
        for i in range(self.segments):
            angle = 2 * math.pi * i / self.segments
            circle.append([radius * math.cos(angle), radius * math.sin(angle), 0])
        return np.array(circle, dtype=np.float32)
    
    def _local_matrix(self, x_deg=0, y_deg=0, z_deg=0):
        """Euler açılarından rotasyon matrisi"""
        theta_x = math.radians(x_deg)
        theta_y = math.radians(y_deg)
        theta_z = math.radians(z_deg)
        
        Rx = np.array([
            [1, 0, 0],
            [0, math.cos(theta_x), -math.sin(theta_x)],
            [0, math.sin(theta_x), math.cos(theta_x)]
        ], dtype=np.float32)
        
        Ry = np.array([
            [math.cos(theta_y), 0, math.sin(theta_y)],
            [0, 1, 0],
            [-math.sin(theta_y), 0, math.cos(theta_y)]
        ], dtype=np.float32)
        
        Rz = np.array([
            [math.cos(theta_z), -math.sin(theta_z), 0],
            [math.sin(theta_z), math.cos(theta_z), 0],
            [0, 0, 1]
        ], dtype=np.float32)
        
        return Rz @ Ry @ Rx
    
    def determine_support_symbols(self, restraint: Optional[Restraint]) -> Dict[str, Optional[str]]:
        """Restraint -> şekil belirleme"""
        symbols = {"x": None, "y": None, "z": None}
        
        if restraint is None or not restraint.uz:
            return symbols
        
        # X ekseni
        if not restraint.ux:
            symbols["x"] = "circle"
        else:
            symbols["x"] = "triangle" if not restraint.ry else "square"
        
        # Y ekseni
        if not restraint.uy:
            symbols["y"] = "circle"
        else:
            symbols["y"] = "triangle" if not restraint.rx else "square"
        
        # Z ekseni
        if restraint.uz:
            symbols["z"] = "square" if restraint.rz else "circle"
        
        return symbols
    
    def build(self, node: Node) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Node için 9'lu vertex yapısı: pos3 + norm3 + center3"""
        center = np.array([node.x, node.y, node.z], dtype=np.float32)
        
        
        verts = []
        idxs = []
        
        # Restraint yoksa veya free ise küçük küp
        if node.restraint is None or node.restraint.is_free():
            self._add_cube(center, verts, idxs)
        else:
            # Mesnet sembollerini ekle
            symbols = self.determine_support_symbols(node.restraint)
            
            # X ekseni sembolü
            if symbols["x"]:
                matrix = self._local_matrix(x_deg=90)  # X eksenine yatır
                self._add_symbol(symbols["x"], matrix, [0, 0, -self.size/2], center, verts, idxs)
            
            # Y ekseni sembolü
            if symbols["y"]:
                matrix = self._local_matrix(x_deg=90, z_deg=90)  # Y eksenine yatır
                self._add_symbol(symbols["y"], matrix, [0, 0, -self.size/2], center, verts, idxs)
            
            # Z ekseni sembolü
            if symbols["z"]:
                matrix = self._local_matrix()  # Düz (Z ekseni)
                self._add_symbol(symbols["z"], matrix, [0, 0, -self.size], center, verts, idxs)
        
        # Renkler
        vertex_count = len(verts) // 9
        color = np.array([1, 1, 0] if node.is_selected else [0.2, 0.2, 0.2], dtype=np.float32)
        colors = np.tile(color, (vertex_count, 1))
        
        return np.array(verts, dtype=np.float32), colors, np.array(idxs, dtype=np.uint32)
    
    def _add_symbol(self, shape_name, rotation_matrix, offset, center, verts, idxs):
        """Sembol ekle - yerel koordinatlarda, sonra center+offset eklenir"""
        shape = self.shapes[shape_name].copy()
        
        # Rotasyon uygula (yerel)
        rotated = shape @ rotation_matrix.T
        
        # Offset ekle (yerel) ve center ekle (global)
        for i, v in enumerate(rotated):
            # Yerel pozisyon = rotated + offset
            local_pos = v + np.array(offset)
            
            if shape_name == "circle" and i == 0:
                # Circle'ın merkez noktası
                self._add_to_verts(local_pos, [0, 0, 1], center, verts)
            elif shape_name == "circle":
                # Circle'ın çevre noktaları
                self._add_to_verts(local_pos, [0, 0, 1], center, verts)
            else:
                # Triangle/Square için tüm noktalar
                self._add_to_verts(local_pos, [0, 0, 1], center, verts)
        
        # İndeksleri oluştur
        n = len(rotated)
        base = len(verts) // 9 - n
        
        if shape_name == "triangle":
            # Triangle: tek üçgen
            idxs.extend([base, base+1, base+2])
        
        elif shape_name == "square":
            # Square: iki üçgen
            idxs.extend([base, base+1, base+2, base, base+2, base+3])
        
        elif shape_name == "circle":
            # Circle: merkez + çevre üçgenleri
            center_idx = base
            for i in range(1, n):
                next_i = i + 1 if i < n-1 else 1
                idxs.extend([center_idx, base + i, base + next_i])
    
    def _add_to_verts(self, p_local, normal, center, verts):
        """9'lu yapıya uygun veri ekler - p_local center'a göre OFFSET"""
        verts.extend([
            p_local[0], p_local[1], p_local[2],  # aPos (center'a göre offset)
            normal[0], normal[1], normal[2],     # aNormal
            center[0], center[1], center[2]      # aCenter (global pozisyon)
        ])
    
    def _add_cube(self, center, verts, idxs):
        """Küçük küp - free node için"""
        half = self.size * 0.4 / 2
        corners = np.array([
            [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
            [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1]
        ], dtype=np.float32) * half
        
        faces = [
            [0, 1, 2, 3], [4, 5, 6, 7], [0, 4, 7, 3],
            [1, 5, 6, 2], [0, 1, 5, 4], [3, 2, 6, 7]
        ]
        face_normals = [
            [0, 0, -1], [0, 0, 1], [-1, 0, 0],
            [1, 0, 0], [0, -1, 0], [0, 1, 0]
        ]
        
        for i, face in enumerate(faces):
            normal = face_normals[i]
            base = len(verts) // 9
            for idx in face:
                # corners[idx] zaten center'a göre offset
                self._add_to_verts(corners[idx], normal, center, verts)
            idxs.extend([base, base+1, base+2, base, base+2, base+3])

    def build_simple_points(self, node: Node) -> np.ndarray:
        """
        Node için sadece 1 nokta döner.
        format: pos3 + normal3 + center3 = 9 float (NodeBuilder ile uyumlu)
        """
        center = np.array([node.x, node.y, node.z], dtype=np.float32)
        return np.array([
            center[0], center[1], center[2],
            0.0, 0.0, 1.0,
            center[0], center[1], center[2]
        ], dtype=np.float32)