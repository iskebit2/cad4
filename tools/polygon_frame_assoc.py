# tools/polygon_frame_assoc.py
"""
Polygon ↔ Frame otomatik ilişkilendirme için saf geometri yardımcıları.

Bu modül state tutmaz. `Polygon.refresh_assoc` tarafından çağrılır.
`plane` paketinden bağımsızdır.
"""
from __future__ import annotations

import math

import numpy as np

from data.enums import DistType


def segment_intersects_box(a, b, lower, upper, tol) -> bool:
    """Liang-Barsky: [a,b] segmenti 3B AABB [lower, upper] ile kesişiyor mu?"""
    s, e = 0.0, 1.0
    d = b - a
    for ax in range(3):
        if abs(d[ax]) <= tol:
            if a[ax] < lower[ax] - tol or a[ax] > upper[ax] + tol:
                return False
            continue
        t0 = (lower[ax] - a[ax]) / d[ax]
        t1 = (upper[ax] - a[ax]) / d[ax]
        s, e = max(s, min(t0, t1)), min(e, max(t0, t1))
        if s > e + tol:
            return False
    return True


def segment_hits_band_and_box(a_local, b_local, lower, upper,
                              *, ignore_bounds: bool, tol: float) -> bool:
    """Segmentin depth bandı + (opsiyonel) uv kutusuyla kesişimi."""
    lo = lower.copy()
    hi = upper.copy()
    if ignore_bounds:
        lo[0] = lo[1] = -np.inf
        hi[0] = hi[1] = np.inf
    return segment_intersects_box(a_local, b_local, lo, hi, tol)


def angle_to_axis_deg(vec: np.ndarray, axis: np.ndarray) -> float:
    """0..90 derece arası mutlak açı. Sıfır vektör → 90 döner."""
    v_len = float(np.linalg.norm(vec))
    a_len = float(np.linalg.norm(axis))
    if v_len < 1e-12 or a_len < 1e-12:
        return 90.0
    c = abs(float(np.dot(vec, axis))) / (v_len * a_len)
    return math.degrees(math.acos(min(1.0, max(0.0, c))))


def _axis_for(direction: DistType, plane_u, plane_v):
    if direction == DistType.TWO_WAY:
        return None
    if direction in (DistType.ONE_WAY, DistType.ONE_WAY_U1):
        return plane_u
    if direction == DistType.ONE_WAY_U2:
        return plane_v
    return None


def passes_direction_filter(frame_vec: np.ndarray,
                            plane_u: np.ndarray, plane_v: np.ndarray,
                            direction: DistType, tol_deg: float) -> bool:
    """`direction` filtresine göre frame vektörü uygun mu?"""
    axis = _axis_for(direction, plane_u, plane_v)
    if axis is None:
        return True
    return angle_to_axis_deg(frame_vec, axis) <= tol_deg