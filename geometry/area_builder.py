# geometry/area_builder.py
import numpy as np
from typing import Tuple, List
from domain.element import Area
import mapbox_earcut as earcut

from logging_config import CadLogger
logger = CadLogger.get(__name__)

def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0,0,1])
    return v / n

class AreaBuilder:
    def build(self, area: Area) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        points = np.array([[n.x, n.y, n.z] for n in area.nodes], dtype=np.float32)
        if len(points) < 3: return np.array([]), np.array([]), np.array([])
        
        # Düzlem normali
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            normal = np.array([0,0,1])
        else:
            normal = normal / norm
        
        # Kalınlık
        thick = area.thickness / 2
        up = points + normal * thick
        down = points - normal * thick
        N = len(points)
        
        # 2D projeksiyon için eksenler
        if abs(normal[2]) > 0.9:
            u, v = np.array([1,0,0]), np.array([0,1,0])
        elif abs(normal[1]) > 0.9:
            u, v = np.array([1,0,0]), np.array([0,0,1])
        elif abs(normal[0]) > 0.9:
            u, v = np.array([0,1,0]), np.array([0,0,1])
        else:
            world_up = np.array([0,0,1])
            u = normalize(np.cross(normal, world_up))
            v = normalize(np.cross(normal, u))
        
        # 2D projeksiyon
        center = points.mean(0)
        pts_2d = np.array([[(p-center)@u, (p-center)@v] for p in points])
        
        # Üçgenle
        rings = np.array([len(pts_2d)], dtype=np.uint32)
        tri = earcut.triangulate_float32(pts_2d, rings).tolist()
        
        verts, idxs = [], []
        
        # ===== YAN YÜZLER (her yüz için DOĞRU normal) =====
        for i in range(N):
            i_next = (i + 1) % N
            
            v0 = up[i]      # üst i
            v1 = up[i_next] # üst i_next
            v2 = down[i_next] # alt i_next
            v3 = down[i]    # alt i
            
            # Yüzey normali (dışa bakan)
            face_normal = normalize(np.cross(v1 - v0, v2 - v0))
            
            base = len(verts) // 6
            for p in [v0, v1, v2, v3]:
                verts.extend([p[0], p[1], p[2], face_normal[0], face_normal[1], face_normal[2]])
            
            # İki üçgen
            idxs.extend([base, base+1, base+2, base, base+2, base+3])
        
        # ===== ÜST KAPAK =====
        base = len(verts) // 6
        for p in up:
            verts.extend([p[0], p[1], p[2], normal[0], normal[1], normal[2]])
        for i in range(0, len(tri), 3):
            idxs.extend([base + tri[i], base + tri[i+2], base + tri[i+1]])
        
        # ===== ALT KAPAK =====
        base = len(verts) // 6
        for p in down:
            verts.extend([p[0], p[1], p[2], -normal[0], -normal[1], -normal[2]])
        for i in range(0, len(tri), 3):
            idxs.extend([base + tri[i], base + tri[i+1], base + tri[i+2]])
        
        # Renkler
        color = np.array(
            [1,1,0] if area.is_selected else [0.5,0.8,1.0],
            dtype=np.float32
        )
        vc = len(verts) // 6
        colors = np.tile(color, (vc, 1)).astype(np.float32)

        # logger.debug(f"AreaBuilder: {vc} vertices, {len(idxs)} indices")

        return (
            np.array(verts, dtype=np.float32),
            colors.astype(np.float32),
            np.array(idxs, dtype=np.uint32),
        )
    
    def _plane_axes(self, points):
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        if norm < 1e-10: normal = np.array([0,0,1])
        else: normal /= norm
        
        if abs(normal[2]) > 0.9:
            return np.array([1,0,0]), np.array([0,1,0]), normal
        elif abs(normal[1]) > 0.9:
            return np.array([1,0,0]), np.array([0,0,1]), normal
        elif abs(normal[0]) > 0.9:
            return np.array([0,1,0]), np.array([0,0,1]), normal
        else:
            world_up = np.array([0,0,1])
            u = np.cross(normal, world_up)
            u /= np.linalg.norm(u)
            v = np.cross(normal, u)
            return u, v, normal

    def build_simple_lines(self, area: Area) -> np.ndarray:
        """
        Area'nın çevresini oluşturan basit çizgi döngüsü.
        Her kenar için 2 nokta (çift yönlü olmasın diye döngü kapanışını da ekle)
        Returns: vertices array [x,y,z, nx,ny,nz]
        """
        points = np.array([[n.x, n.y, n.z] for n in area.nodes], dtype=np.float32)
        if len(points) < 2:
            return np.array([], dtype=np.float32)
        
        N = len(points)
        
        # Normal hesapla (tüm kenarlar aynı normali paylaşsın)
        v1 = points[1] - points[0]
        v2 = points[2] - points[0] if N >= 3 else np.array([0,0,1], dtype=np.float32)
        normal = np.cross(v1, v2)
        n = np.linalg.norm(normal)
        normal = normal / n if n > 1e-10 else np.array([0,0,1], dtype=np.float32)
        
        verts = []
        for i in range(N):
            j = (i + 1) % N
            p0 = points[i]
            p1 = points[j]
            verts.extend([p0[0], p0[1], p0[2], normal[0], normal[1], normal[2]])
            verts.extend([p1[0], p1[1], p1[2], normal[0], normal[1], normal[2]])
        
        return np.array(verts, dtype=np.float32)