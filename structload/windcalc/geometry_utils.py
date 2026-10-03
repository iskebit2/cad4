#windcalc/geometry_utils.py
from structload.data.wind_data import TOL, EPS
import math
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Union, Any

def close_polygon(polygon: np.ndarray, tol: float = 1e-8) -> np.ndarray:
        """Poligonu kapatır"""
        polygon = np.asarray(polygon, dtype=float)
        if len(polygon) == 0:
            return polygon
        if not np.allclose(polygon[0], polygon[-1], atol=tol):
            polygon = np.vstack([polygon, polygon[0]])
        return polygon

def polygon_centroid(polygon: np.ndarray) -> np.ndarray:
    """Poligonun merkezini hesaplar"""
    pts = np.asarray(polygon, dtype=float)

    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]

    return np.mean(pts, axis=0)

def _make_local_sys(poly_coords, tol=1e-9):
    """
    Düzlemsel 3D bir poligon için sağ elli yerel koordinat sistemi oluşturur.

    Returns
    -------
    dict
        {
            "origin_3d": ...,
            "u_dir": ...,
            "v_dir": ...,
            "normal": ...
        }

    Koordinat sistemi:
        u_dir : poligon düzlemindeki ilk eksen
        v_dir : poligon düzlemindeki ikinci eksen
        normal: u_dir x v_dir
    """

    poly = np.asarray(poly_coords, dtype=float)

    if poly.ndim != 2 or poly.shape[1] != 3:
        raise ValueError("poly_coords (n, 3) şeklinde olmalıdır.")

    if len(poly) < 3:
        raise ValueError("En az üç nokta gerekli.")

    origin = poly[0]

    # ------------------------------------------------------------
    # 1. İlk anlamlı kenarı bul -> u_dir adayı
    # ------------------------------------------------------------

    u_dir = None

    for i in range(1, len(poly)):
        v = poly[i] - origin
        length = np.linalg.norm(v)

        if length > tol:
            u_dir = v / length
            break

    if u_dir is None:
        raise ValueError("Poligon dejenere: bütün noktalar aynı.")

    # ------------------------------------------------------------
    # 2. u_dir'e paralel olmayan bir vektör bul
    #    ve normal'i oluştur
    # ------------------------------------------------------------

    normal = None

    for i in range(1, len(poly)):
        v = poly[i] - origin

        cross = np.cross(u_dir, v)
        cross_len = np.linalg.norm(cross)

        if cross_len > tol:
            normal = cross / cross_len
            break

    if normal is None:
        raise ValueError(
            "Poligon dejenere: bütün noktalar aynı doğru üzerinde."
        )

    # ------------------------------------------------------------
    # 3. Gerçek v_dir'i normal ve u_dir'den üret
    #
    # u x v = normal olacak şekilde
    # ------------------------------------------------------------

    v_dir = np.cross(normal, u_dir)
    v_dir /= np.linalg.norm(v_dir)

    return {
        "origin_3d": origin.copy(),
        "u_dir": u_dir,
        "v_dir": v_dir,
        "normal": normal,
    }

def _project_3d_to_local_2d(poly_coords, local_sys):

    poly = np.asarray(poly_coords, dtype=float)

    origin = local_sys["origin_3d"]
    u_dir = local_sys["u_dir"]
    v_dir = local_sys["v_dir"]

    pts_2d = []

    for pt in poly:
        vec = pt - origin

        u = np.dot(vec, u_dir)
        v = np.dot(vec, v_dir)

        pts_2d.append([u, v])

    return np.asarray(pts_2d)

def _unproject_local_2d_to_3d(pts_2d, local_sys):

    pts_2d = np.asarray(pts_2d, dtype=float)

    origin = local_sys["origin_3d"]
    u_dir = local_sys["u_dir"]
    v_dir = local_sys["v_dir"]

    pts_3d = []

    for u, v in pts_2d:
        point = (
            origin
            + u * u_dir
            + v * v_dir
        )

        pts_3d.append(point)

    return np.asarray(pts_3d)

# ================================================================
# Geometri yardımcıları (modül seviyesinde, saf fonksiyonlar)
# ================================================================

def _close_polygon(polygon: np.ndarray, tol: float = TOL) -> np.ndarray:
    """Poligonu kapatır (ilk nokta == son nokta)."""
    polygon = np.asarray(polygon, dtype=float)
    if len(polygon) == 0:
        return polygon
    if not np.allclose(polygon[0], polygon[-1], atol=tol):
        polygon = np.vstack([polygon, polygon[0]])
    return polygon


def _open_polygon(polygon: np.ndarray, tol: float = TOL) -> np.ndarray:
    """Kapalı poligondan tekrar eden son noktayı kaldırır."""
    polygon = np.asarray(polygon, dtype=float)
    if len(polygon) > 1 and np.allclose(polygon[0], polygon[-1], atol=tol):
        return polygon[:-1]
    return polygon


def _area2(poly: np.ndarray) -> float:
    """İki katlı işaretli alan (shoelace)."""
    poly = np.asarray(poly, dtype=float)
    return float(np.sum(
        poly[:, 0] * np.roll(poly[:, 1], -1)
        - poly[:, 1] * np.roll(poly[:, 0], -1)
    ))


def _clean_vertices(pts: np.ndarray, tol: float = EPS) -> np.ndarray:
    """Ardışık mükerrer noktaları ve kapanış tekrarını temizler."""
    pts = np.asarray(pts, dtype=float)
    if len(pts) == 0:
        return pts
    cleaned = [pts[0]]
    for p in pts[1:]:
        if np.linalg.norm(p - cleaned[-1]) > tol:
            cleaned.append(p)
    if len(cleaned) > 1 and np.linalg.norm(cleaned[0] - cleaned[-1]) <= tol:
        cleaned.pop()
    return np.asarray(cleaned)


def _split_by_line_2d(pts_2d, p1, p2, tol: float = EPS):
    """Poligonu p1->p2 doğrusu boyunca ikiye böler (Sutherland-Hodgman)."""
    poly = np.asarray(pts_2d, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)

    empty = np.empty((0, 2))
    if len(poly) < 3:
        return empty, empty

    line = p2 - p1
    if np.linalg.norm(line) <= tol:
        raise ValueError("p1 ve p2 aynı nokta olamaz.")

    area2 = _area2(poly)
    if abs(area2) <= tol:
        print("Poligon alanı sıfıra çok yakın.")
        return empty, empty
        # raise ValueError("Poligon alanı sıfıra çok yakın.")
    ccw = area2 > 0

    def side(pt: np.ndarray) -> float:
        v = pt - p1
        return line[0] * v[1] - line[1] * v[0]

    def clip(keep_left: bool) -> np.ndarray:
        result: List[np.ndarray] = []
        s = poly[-1]
        s_s = side(s)

        for e in poly:
            e_s = side(e)
            s_in = (s_s >= -tol) if keep_left else (s_s <= tol)
            e_in = (e_s >= -tol) if keep_left else (e_s <= tol)

            if e_in:
                if not s_in:
                    denom = s_s - e_s
                    t = s_s / denom if abs(denom) > tol else 0.0
                    result.append(s + t * (e - s))
                result.append(e.copy())
            elif s_in:
                denom = s_s - e_s
                t = s_s / denom if abs(denom) > tol else 0.0
                result.append(s + t * (e - s))

            s, s_s = e, e_s

        if not result:
            return empty
        cleaned = _clean_vertices(np.asarray(result), tol)
        return cleaned if len(cleaned) >= 3 else empty

    def fix_orientation(p: np.ndarray) -> np.ndarray:
        if len(p) < 3:
            return p
        if (_area2(p) > 0) != ccw:
            return p[::-1].copy()
        return p

    return fix_orientation(clip(True)), fix_orientation(clip(False))


def _clip_line_to_polygon_2d(line_p1, line_p2, polygon):
    """Sonsuz 2D çizginin poligon sınırıyla iki kesişimini döner."""
    p1 = np.asarray(line_p1, dtype=float)
    p2 = np.asarray(line_p2, dtype=float)
    direction = p2 - p1
    norm = np.linalg.norm(direction)
    if norm < TOL:
        return None
    direction /= norm

    pts = _open_polygon(polygon)
    n = len(pts)
    if n < 3:
        return None

    intersections: List[np.ndarray] = []
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        edge = b - a

        cross = direction[0] * edge[1] - direction[1] * edge[0]
        if abs(cross) < 1e-10:
            continue

        q = a - p1
        t = (q[0] * edge[1] - q[1] * edge[0]) / cross
        u = (q[0] * direction[1] - q[1] * direction[0]) / cross

        if -TOL <= u <= 1 + TOL:
            pt = p1 + t * direction
            if not any(np.linalg.norm(pt - prev) < 1e-6 for prev in intersections):
                intersections.append(pt)

    if len(intersections) < 2:
        return None

    intersections.sort(key=lambda p: float(np.dot(p - p1, direction)))
    return intersections[0], intersections[-1]





def _valid_polygon(poly) -> bool:
    return poly is not None and len(poly) >= 3

def _offset_edge_2d(polygon_2d, p1_2d, p2_2d, w_vector_2d, d_L):
    """Kenarı w yönünde offsetler ve poligona kırpar."""
    p1 = np.asarray(p1_2d, dtype=float)
    p2 = np.asarray(p2_2d, dtype=float)
    w_2d = np.asarray(w_vector_2d, dtype=float)
    w_len = np.linalg.norm(w_2d)
    if w_len < TOL:
        return None
    offset = (w_2d / w_len) * d_L
    return _clip_line_to_polygon_2d(p1 + offset, p2 + offset, polygon_2d)

def _create_edge_perp_2d(polygon_2d, p1_2d, p2_2d, w_vector_2d, d_L):
    """Kenara dik iki yardımcı çizgi üretir."""
    p1 = np.asarray(p1_2d, dtype=float)
    p2 = np.asarray(p2_2d, dtype=float)
    edge_vec = p2 - p1
    edge_len = np.linalg.norm(edge_vec)
    if edge_len < TOL:
        return None
    edge_dir = edge_vec / edge_len
    perp_dir = np.array([-edge_dir[1], edge_dir[0]])
    EXT = d_L * 2

    line_L_p1 = p1 + edge_dir * d_L
    line_R_p1 = p2 - edge_dir * d_L

    result_L = _clip_line_to_polygon_2d(line_L_p1, line_L_p1 + perp_dir * EXT, polygon_2d)
    result_R = _clip_line_to_polygon_2d(line_R_p1, line_R_p1 + perp_dir * EXT, polygon_2d)

    if result_L is None and result_R is None:
        return None
    return result_L, result_R

def _normalize_wind(wind_vector: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if wind_vector is None:
        return None
    w = np.asarray(wind_vector, dtype=float)
    if w.size < 2:
        return None
    w2 = w[:2]
    norm = np.linalg.norm(w2)
    return w2 / norm if norm >= 1e-12 else None

def dict_tree(data, indent=""):
    lines = []

    items = list(data.items())

    for i, (key, value) in enumerate(items):
        last = i == len(items) - 1

        branch = "└── " if last else "├── "
        lines.append(f"{indent}{branch}{key}")

        if isinstance(value, dict):
            new_indent = indent + ("    " if last else "│   ")
            lines.append(dict_tree(value, new_indent))

        else:
            # Yukarıdaki key satırını value ile birleştir
            lines[-1] = f"{indent}{branch}{key} : {value}"

    return "\n".join(lines)