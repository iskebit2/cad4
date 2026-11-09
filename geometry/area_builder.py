# geometry/area_builder.py

import time
import mapbox_earcut as earcut
import numpy as np

from domain.element import Area
from logging_config import CadLogger

logger = CadLogger.get(__name__)

def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0,0,1])
    return v / n

class AreaBuilder:
    def build(self, area: Area) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        t0 = time.perf_counter()
        points = np.array([[n.x, n.y, n.z] for n in area.nodes], dtype=np.float32)
        N = len(points)
        if N < 3: 
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32), np.array([], dtype=np.uint32)

        t1 = time.perf_counter()
        
        # Düzlem normali
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        normal = np.array([0, 0, 1], dtype=np.float32) if norm < 1e-10 else normal / norm
        
        # Kalınlık
        thick = area.thickness / 2.0
        up = points + normal * thick
        down = points - normal * thick
        
        # 2D projeksiyon ve earcut
        if abs(normal[2]) > 0.9:
            u, v = np.array([1, 0, 0], dtype=np.float32), np.array([0, 1, 0], dtype=np.float32)
        elif abs(normal[1]) > 0.9:
            u, v = np.array([1, 0, 0], dtype=np.float32), np.array([0, 0, 1], dtype=np.float32)
        elif abs(normal[0]) > 0.9:
            u, v = np.array([0, 1, 0], dtype=np.float32), np.array([0, 0, 1], dtype=np.float32)
        else:
            world_up = np.array([0, 0, 1], dtype=np.float32)
            u = normalize(np.cross(normal, world_up))
            v = normalize(np.cross(normal, u))
        
        center = points.mean(axis=0)
        pts_2d = np.column_stack([((points - center) @ u), ((points - center) @ v)])
        
        rings = np.array([N], dtype=np.uint32)
        tri = earcut.triangulate_float32(pts_2d, rings)
        t1 = time.perf_counter()
        num_tri = len(tri) // 3
        

        # Boyut hesapları:
        # Yan yüzler: N adet dörtgen -> 4 * N vertex, 6 * N index
        # Üst kapak: N vertex, num_tri * 3 index
        # Alt kapak: N vertex, num_tri * 3 index
        total_verts = 4 * N + 2 * N
        total_indices = 6 * N + 6 * num_tri

        verts = np.empty((total_verts, 6), dtype=np.float32)
        idxs = np.empty(total_indices, dtype=np.uint32)

        v_idx = 0
        i_idx = 0

        # ===== YAN YÜZLER =====
        for i in range(N):
            i_next = (i + 1) % N
            v0, v1_pt, v2_pt, v3 = up[i], up[i_next], down[i_next], down[i]
            
            face_normal = normalize(np.cross(v2_pt - v0, v1_pt - v0))
            
            base = v_idx // 1  # her vertex için 6 eleman tutuyoruz ama indeksleme vertex bazlı
            base_v = v_idx
            
            verts[v_idx]     = [v0[0], v0[1], v0[2], face_normal[0], face_normal[1], face_normal[2]]
            verts[v_idx + 1] = [v1_pt[0], v1_pt[1], v1_pt[2], face_normal[0], face_normal[1], face_normal[2]]
            verts[v_idx + 2] = [v2_pt[0], v2_pt[1], v2_pt[2], face_normal[0], face_normal[1], face_normal[2]]
            verts[v_idx + 3] = [v3[0], v3[1], v3[2], face_normal[0], face_normal[1], face_normal[2]]
            
            idxs[i_idx:i_idx+6] = [base_v, base_v+2, base_v+1, base_v, base_v+3, base_v+2]
            v_idx += 4
            i_idx += 6

        # ===== ÜST KAPAK =====
        base_v = v_idx
        verts[v_idx:v_idx+N, :3] = up
        verts[v_idx:v_idx+N, 3:] = normal
        v_idx += N
        
        idxs[i_idx:i_idx+num_tri*3] = base_v + tri
        i_idx += num_tri * 3

        # ===== ALT KAPAK =====
        base_v = v_idx
        verts[v_idx:v_idx+N, :3] = down
        verts[v_idx:v_idx+N, 3:] = -normal
        v_idx += N
        
        # Alt kapak için üçgen sıra tersi (triangulate sırasını değiştirerek veya index kaydırarak)
        alt_tri = tri.reshape(-1, 3)[:, [0, 2, 1]].flatten()
        idxs[i_idx:i_idx+num_tri*3] = base_v + alt_tri
        i_idx += num_tri * 3

        # Renkler
        color = np.array([1, 1, 0] if area.is_selected else [0.5, 0.8, 1.0], dtype=np.float32)
        colors = np.tile(color, (v_idx, 1))

        dt = (time.perf_counter() - t0) * 1000
        if dt > 1.0:
            logger.warning("[AreaBuilder] id=%s N=%d dt=%.2f ms",
                        getattr(area, "unique_id", "?"), N, dt)
            
        return verts.reshape(-1), colors, idxs
    
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

    def build_simple(self, area: Area) -> np.ndarray:
        points = np.array(
            [[n.x, n.y, n.z] for n in area.nodes],
            dtype=np.float32
        )

        if len(points) < 3:
            return np.array([], dtype=np.float32)

        center = np.mean(points, axis=0)

        verts = []

        for i in range(len(points)):
            p0 = points[i]
            p1 = points[(i + 1) % len(points)]

            # triangle: center - p0 - p1
            verts.extend(center)
            verts.extend([0.0, 0.0, 1.0])

            verts.extend(p0)
            verts.extend([0.0, 0.0, 1.0])

            verts.extend(p1)
            verts.extend([0.0, 0.0, 1.0])

        return np.array(verts, dtype=np.float32)