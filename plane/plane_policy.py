# plane/plane_policy.py

from __future__ import annotations

from enum import Enum
import numpy as np


class SectionFilterMode(str, Enum):
    """
    Düzlem (Plane) filtresinin elemanları nasıl süzeceğini belirleyen politika.
    """
    INTERSECT = "intersect"  # Herhangi bir noktası değen/giren
    STRICT = "strict"        # Tamamı sınır/bant içinde olan
    CLIP = "clip"            # Sınır dışına taşan kısımları kırpılan (Clip/Crop - Görsel Şölen)


class PlaneFilterPolicy:
    """
    Plane ve elemanlar arasındaki geometrik süzme politikalarını uygulayan yardımcı motor.
    """

    def __init__(self, mode: SectionFilterMode = SectionFilterMode.INTERSECT):
        self.mode = mode

    # ------------------------------------------------------------------
    # Nokta / Segment / Poligon Süzme Testleri
    # ------------------------------------------------------------------
    def passes_point(self, plane, pt) -> bool:
        """Nokta testi."""
        return plane.contains_pt(pt)

    def passes_segment(self, plane, p1, p2) -> bool:
        """Çubuk/Çizgi segmenti testi."""
        pt1_in = plane.contains_pt(p1)
        pt2_in = plane.contains_pt(p2)

        if self.mode == SectionFilterMode.STRICT:
            return pt1_in and pt2_in
        elif self.mode == SectionFilterMode.INTERSECT:
            if pt1_in or pt2_in:
                return True
            # Segmentin bant/kutu kesişimi kontrolü
            l1 = plane.world_to_local(p1)
            l2 = plane.world_to_local(p2)
            lower, upper = plane._association_bounds()
            tol = plane._association_tolerance([p1, p2], np.array([l1, l2]))
            return plane._segment_intersects_box(l1, l2, lower, upper, tol)
        elif self.mode == SectionFilterMode.CLIP:
            # Clip modunda da en azından kesişmesi gerekir
            return pt1_in or pt2_in or self.passes_segment_intersect_check(plane, p1, p2)

        return True

    def passes_polygon(self, plane, points: list) -> bool:
        """Poligon / Yüzey testi."""
        in_flags = [plane.contains_pt(pt) for pt in points]

        if self.mode == SectionFilterMode.STRICT:
            return all(in_flags)
        elif self.mode == SectionFilterMode.INTERSECT:
            return any(in_flags) or self.passes_poly_intersect_check(plane, points)
        elif self.mode == SectionFilterMode.CLIP:
            return any(in_flags) or self.passes_poly_intersect_check(plane, points)

        return True

    # ------------------------------------------------------------------
    # Clip / Crop Geometrik Hesaplamaları (Görsel Şölen)
    # ------------------------------------------------------------------
    def clip_segment(self, plane, p1, p2) -> tuple[np.ndarray, np.ndarray] | None:
        """
        Çizgiyi/Çubuğu plane bounds ve depth sınırlarına göre kırpar (Crop).
        Eğer çizgi tamamen dışarıda kalırsa None döner.
        """
        l1 = plane.world_to_local(p1)
        l2 = plane.world_to_local(p2)
        lower, upper = plane._association_bounds()
        tol = plane._association_tolerance([p1, p2], np.array([l1, l2]))

        # 3D AABB Sutherland-Hodgman / Liang-Barsky kırpması
        s, e = 0.0, 1.0
        d = l2 - l1
        for ax in range(3):
            if abs(d[ax]) <= tol:
                if l1[ax] < lower[ax] - tol or l1[ax] > upper[ax] + tol:
                    return None
                continue
            t0 = (lower[ax] - l1[ax]) / d[ax]
            t1 = (upper[ax] - l1[ax]) / d[ax]
            s, e = max(s, min(t0, t1)), min(e, max(t0, t1))
            if s > e + tol:
                return None

        new_l1 = l1 + s * d
        new_l2 = l1 + e * d
        return plane.local_to_world(new_l1), plane.local_to_world(new_l2)

    def passes_segment_intersect_check(self, plane, p1, p2) -> bool:
        l1 = plane.world_to_local(p1)
        l2 = plane.world_to_local(p2)
        lower, upper = plane._association_bounds()
        tol = plane._association_tolerance([p1, p2], np.array([l1, l2]))
        return plane._segment_intersects_box(l1, l2, lower, upper, tol)

    def passes_poly_intersect_check(self, plane, points: list) -> bool:
        local = np.asarray([plane.world_to_local(pt) for pt in points], float)
        lower, upper = plane._association_bounds()
        tol = plane._association_tolerance(points, local)
        tris = plane._triangulate_surface(local)
        if not tris:
            return False
        return any(plane._polygon_intersects_box(t, lower, upper, tol) for t in tris)