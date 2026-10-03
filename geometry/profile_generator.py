# geometry/profile_generator.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Callable, Any, Union
import numpy as np
import math
from enum import Enum
# from domain.element import SectionType
from domain.definition import SectionType
from logging_config import CadLogger
from logging_config import CadLogger

logger = CadLogger.get(__name__)


def normalize(v: np.ndarray) -> np.ndarray:
    """Normalize vector with safe division."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm


class ProfileGenerator:
    """
    2D profil geometrisi üretici sınıf
    - FrameGeometryBuilder tarafından kullanılır
    - Her kesit tipi için ayrı metod
    - Parametre validasyonu
    """
    
    def __init__(self):
        """Profil üretici fonksiyonlarının mapping'i"""
        self._generators = {
            SectionType.RECT: self._rect_profile,
            SectionType.CIRCLE: self._circle_profile,
            SectionType.I: self._i_profile,
            SectionType.L: self._l_profile,
            SectionType.T: self._t_profile,
            SectionType.PIPE: self._pipe_profile,
            SectionType.TUBE: self._tube_profile,
            SectionType.BOX: self._tube_profile,
            SectionType.C: self._c_profile,
            SectionType.CHANNEL: self._c_profile,
            SectionType.CUSTOM: self._custom_profile,
        }
    
    def get_profile(self, 
                   section_type: Union[SectionType, str], 
                   params: dict) -> np.ndarray:
        """
        Ana profil üretici fonksiyon - FrameGeometryBuilder bunu çağırır
        
        Args:
            section_type: SectionType enum veya string ("RECT", "I", etc.)
            params: Kesit parametreleri (b, h, t, etc.)
            
        Returns:
            (N,2) numpy array: profil noktaları, merkez orijinde
        """
        # String ise SectionType'a çevir
        if isinstance(section_type, str):
            try:
                section_type = SectionType(section_type.upper())
            except ValueError:
                logger.debug(f"Uyarı: Bilinmeyen kesit tipi '{section_type}', RECT kullanılıyor")
                section_type = SectionType.RECT
        # logger.debug(f"[ProfileGenerator] section_type: {section_type}")

        # Parametreleri doğrula
        validated_params = self._validate_params(section_type, params)
        
        # Üretici fonksiyonu bul
        if section_type in self._generators:
            points = self._generators[section_type](validated_params)
            # logger.debug(f"[ProfileGenerator] Üretici fonksiyonu bul: {points}")
        else:
            # Varsayılan: RECT
            points = self._rect_profile(validated_params)
        
        # Numpy array'e çevir
        points = np.array(points, dtype=np.float32)
        
        return points
    
    def _validate_params(self, section_type: SectionType, params: dict) -> dict:
        """Parametreleri doğrula ve varsayılan değerleri ekle"""
        validated = params.copy()
        
        # Ortak validasyonlar
        for key in ['b', 'h', 't', 'tw', 'tf', 'r', 'ro', 'ri']:
            if key in validated:
                validated[key] = max(0.1, float(validated[key]))
        
        # Tip-specific validasyonlar
        if section_type == SectionType.CIRCLE:
            validated.setdefault('r', 50.0)
            validated.setdefault('n', 16)
            validated['n'] = max(3, int(validated.get('n', 16)))
        
        elif section_type == SectionType.PIPE:
            validated.setdefault('ro', 60.0)
            validated.setdefault('ri', 50.0)
            validated.setdefault('n', 24)
            validated['ri'] = min(validated['ro'] - 0.1, validated['ri'])
            validated['n'] = max(3, int(validated['n']))
        
        elif section_type in [SectionType.I, SectionType.T, SectionType.CHANNEL]:
            validated.setdefault('b', 100.0)
            validated.setdefault('h', 200.0)
            validated.setdefault('tw', 10.0)
            validated.setdefault('tf', 14.0)
        
        elif section_type in [SectionType.L, SectionType.C]:
            validated.setdefault('b', 80.0)
            validated.setdefault('h', 100.0)
            validated.setdefault('t', 8.0)
        
        elif section_type in [SectionType.TUBE, SectionType.BOX]:
            validated.setdefault('b', 100.0)
            validated.setdefault('h', 200.0)
            validated.setdefault('t', 10.0)
        
        return validated
    
    # ========== PROFİL ÜRETİCİLERİ ==========
    
    def _rect_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Dikdörtgen profil"""
        b = params.get('b', 100.0)
        h = params.get('h', 200.0)
        return [
            (-b/2, -h/2), (b/2, -h/2),
            (b/2, h/2), (-b/2, h/2)
        ]
    
    def _circle_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Daire profil"""
        r = params.get('r', 50.0)
        n = params.get('n', 16)
        return [
            (r * math.cos(a), r * math.sin(a))
            for a in np.linspace(0, 2*math.pi, n, endpoint=False)
        ]
    
    def _i_profile(self, params: dict) -> List[Tuple[float, float]]:
        """I-profil (IPE, HEA, HEB)"""
        b = params.get('b', 100.0)
        h = params.get('h', 200.0)
        tw = params.get('tw', 10.0)
        tf = params.get('tf', 14.0)
        return [
            (-b/2, h/2), (b/2, h/2), (b/2, h/2 - tf),
            (tw/2, h/2 - tf), (tw/2, -h/2 + tf), (b/2, -h/2 + tf),
            (b/2, -h/2), (-b/2, -h/2), (-b/2, -h/2 + tf),
            (-tw/2, -h/2 + tf), (-tw/2, h/2 - tf), (-b/2, h/2 - tf),
        ]
    
    def _l_profile(self, params: dict) -> List[Tuple[float, float]]:
        """L-profil (köşebent)"""
        b = params.get('b', 80.0)
        h = params.get('h', 100.0)
        t = params.get('t', 8.0)
        
        return [
            (0, 0), (t, 0), (t, h - t),
            (b, h - t), (b, h), (0, h)
        ]
    
    def _t_profile(self, params: dict) -> List[Tuple[float, float]]:
        """T-profil"""
        b = params.get('b', 120.0)
        h = params.get('h', 150.0)
        tw = params.get('tw', 10.0)
        tf = params.get('tf', 15.0)
        
        return [
            (-b/2, h/2), (b/2, h/2), (b/2, h/2 - tf),
            (tw/2, h/2 - tf), (tw/2, -h/2), (-tw/2, -h/2),
            (-tw/2, h/2 - tf), (-b/2, h/2 - tf),
        ]
    
    def _pipe_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Boru profil"""
        ro = params.get('ro', 60.0)
        ri = params.get('ri', 50.0)
        n = params.get('n', 24)
        
        # Dış çember (CW)
        outer = [
            (ro * math.cos(a), ro * math.sin(a))
            for a in np.linspace(0, 2*math.pi, n, endpoint=False)
        ]
        
        # İç çember (CCW) - boşluk için
        inner = [
            (ri * math.cos(a), ri * math.sin(a))
            for a in np.linspace(2*math.pi, 0, n, endpoint=False)
        ]
        
        return outer + inner
    
    def _tube_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Kutu profil"""
        b = params.get('b', 100.0)
        h = params.get('h', 200.0)
        t = params.get('t', 10.0)
        
        # Dış dikdörtgen (CW)
        outer = [
            (-b/2, -h/2), (b/2, -h/2), (b/2, h/2), (-b/2, h/2)
        ]
        
        # İç dikdörtgen (CCW) - boşluk için
        inner = [
            (-b/2 + t, -h/2 + t), (-b/2 + t, h/2 - t),
            (b/2 - t, h/2 - t), (b/2 - t, -h/2 + t)
        ]
        
        return outer + inner
    
    def _c_profile(self, params: dict) -> List[Tuple[float, float]]:
        """C-profil (U-profil, kanal)"""
        b = params.get('b', 80.0)
        h = params.get('h', 100.0)
        t = params.get('t', 6.0)
        
        return [
            (0, 0), (t, 0), (t, h), (b, h), (b, h - t),
            (2*t, h - t), (2*t, t), (b, t), (b, 0)
        ]
    
    def _custom_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Özel profil - points parametresinden alır"""
        if 'points' not in params:
            return self._default_profile(params)
        return params['points']
    
    def _default_profile(self, params: dict) -> List[Tuple[float, float]]:
        """Varsayılan profil (100x100 kare)"""
        return [(-50, -50), (50, -50), (50, 50), (-50, 50)]
    
    # ========== YARDIMCI METODLAR ==========
    
    def get_profile_info(self, profile: np.ndarray) -> dict:
        """Profil hakkında bilgi döndür (alan, centroid, bounds)"""
        return {
            'area': get_profile_area(profile),
            'centroid': get_profile_centroid(profile),
            'bounds': get_profile_bounds(profile),
            'point_count': len(profile)
        }


# Kayıt işlemlerini manuel yapalım
ProfileGenerator._generators = {
    SectionType.RECT: ProfileGenerator._rect_profile,
    SectionType.CIRCLE: ProfileGenerator._circle_profile,
    SectionType.I: ProfileGenerator._i_profile,
    SectionType.L: ProfileGenerator._l_profile,
    SectionType.T: ProfileGenerator._t_profile,
    SectionType.PIPE: ProfileGenerator._pipe_profile,
    SectionType.TUBE: ProfileGenerator._tube_profile,
    SectionType.BOX: ProfileGenerator._tube_profile,
    SectionType.C: ProfileGenerator._c_profile,
    SectionType.CHANNEL: ProfileGenerator._c_profile,
    SectionType.CUSTOM: ProfileGenerator._custom_profile,
}


def rotate_outline_2d(outline: np.ndarray, angle_deg: float) -> np.ndarray:
    """
    2D outline'ı döndür
    outline: (N,2) numpy array
    angle_deg: derece cinsinden açı
    """
    theta = np.radians(angle_deg)
    c, s = np.cos(theta), np.sin(theta)
    R = np.array([[c, -s], [s, c]])
    return (R @ outline.T).T


def create_mesh_from_outline(outline: np.ndarray, 
                            start: np.ndarray, 
                            end: np.ndarray,
                            closed: bool = True,
                            include_caps: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """
    outline: (N,2) veya (N,3) numpy array, 2D kesit
    start, end: (3,) numpy array, extrusion direction
    closed: profil kapalı mı?
    include_caps: uç kapakları ekle (default: False)
    
    Returns:
        vertex_data: (M,6) [x,y,z, nx,ny,nz]
        indices: (T,3) triangle indices
    """
    outline = np.asarray(outline)
    
    # 2D ise 3D'ye çevir (z=0)
    if outline.shape[1] == 2:
        outline_3d = np.hstack([outline, np.zeros((outline.shape[0], 1))])
    else:
        outline_3d = outline
    
    N = len(outline_3d)
    
    # Extrude vertices
    vertices_start = outline_3d + start
    vertices_end = outline_3d + end
    all_vertices = np.vstack([vertices_start, vertices_end])
    
    vertex_data = []
    indices = []
    
    # Side faces
    for i in range(N):
        i_next = (i + 1) % N if closed else i + 1
        if not closed and i == N-1:
            continue
            
        v0, v1 = i, i_next
        v2, v3 = i_next + N, i + N
        
        # Face normal
        p0, p1, p2 = all_vertices[v0], all_vertices[v1], all_vertices[v2]
        normal = normalize(np.cross(p1 - p0, p2 - p0))
        
        # Add vertices with normal
        base_idx = len(vertex_data) // 6
        for vi in [v0, v1, v2, v3]:
            vertex_data.extend([*all_vertices[vi], *normal])
        
        # Two triangles per quad
        indices.extend([
            base_idx, base_idx + 1, base_idx + 2,
            base_idx + 2, base_idx + 3, base_idx
        ])
    
    # End caps (optional)
    if include_caps and closed:
        # Start cap
        center_start = np.mean(vertices_start, axis=0)
        normal_start = normalize(start - end)  # outward normal
        
        # End cap
        center_end = np.mean(vertices_end, axis=0)
        normal_end = normalize(end - start)  # outward normal
        
        # TODO: Triangulate caps
        # (karmaşık, ayrı bir fonksiyonda yapılmalı)
        pass
    
    return np.array(vertex_data, dtype=np.float32), np.array(indices, dtype=np.uint32)


# ========== YARDIMCI FONKSİYONLAR ==========

def get_profile_area(profile: np.ndarray) -> float:
    """Profil alanını hesapla (shoelace formula)"""
    if len(profile) < 3:
        return 0.0
    
    x = profile[:, 0]
    y = profile[:, 1]
    
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def get_profile_centroid(profile: np.ndarray) -> Tuple[float, float]:
    """Profil ağırlık merkezini hesapla"""
    if len(profile) < 3:
        return (0.0, 0.0)
    
    x = profile[:, 0]
    y = profile[:, 1]
    
    # Shoelace for centroid
    A = get_profile_area(profile)
    if A < 1e-10:
        return (0.0, 0.0)
    
    cx = np.sum((x[:-1] * y[1:] - x[1:] * y[:-1]) * (x[:-1] + x[1:])) / (6 * A)
    cy = np.sum((x[:-1] * y[1:] - x[1:] * y[:-1]) * (y[:-1] + y[1:])) / (6 * A)
    
    return (cx, cy)


def get_profile_bounds(profile: np.ndarray) -> Tuple[float, float, float, float]:
    """Profil sınırlarını hesapla (min_x, max_x, min_y, max_y)"""
    return (np.min(profile[:, 0]), np.max(profile[:, 0]),
            np.min(profile[:, 1]), np.max(profile[:, 1]))



