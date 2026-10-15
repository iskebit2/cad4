# tools/load_balance_report.py
"""
Poligon yük dağıtımının denge kontrolü.

Her polygon için, her pattern için:
  - Expected (kaynak yükünden türeyen toplam kuvvet)
  - Actual   (frame'lerdeki toplam kuvvet)
  - Fark ve tolerans kontrolü
"""
from __future__ import annotations

from typing import Dict, List, Optional

import glm

from domain.definition import LoadDirection
from domain.local_axes import polygon_plane_frame, frame_local_axes
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ============================================================================
# YÖN ÇÖZÜMLEYİCİ  (tek doğru kaynak — başka bir varyant OLMAYACAK)
# ============================================================================
def resolve_direction_vector(
    load_dir,
    frame_R=None,
    poly_u: Optional[glm.vec3] = None,
    poly_v: Optional[glm.vec3] = None,
    poly_n: Optional[glm.vec3] = None,
    default: Optional[glm.vec3] = None,
) -> glm.vec3:
    """
    LoadDirection → dünya birim vektörü.

    Öncelik:
        LOCAL_* için önce frame_R, yoksa poly_u/v/n kullanılır.
    """
    if default is None:
        default = glm.vec3(0.0, 0.0, -1.0)

    d = _coerce_to_enum(load_dir)
    if d is None:
        return default

    # GLOBAL / GRAV / PROJECTED
    _FIXED = {
        LoadDirection.GLOBAL_X:     glm.vec3(1.0, 0.0, 0.0),
        LoadDirection.GLOBAL_Y:     glm.vec3(0.0, 1.0, 0.0),
        LoadDirection.GLOBAL_Z:     glm.vec3(0.0, 0.0, 1.0),
        LoadDirection.GRAVITY:      glm.vec3(0.0, 0.0, -1.0),
        LoadDirection.PROJECTED_X:  glm.vec3(1.0, 0.0, 0.0),
        LoadDirection.PROJECTED_Y:  glm.vec3(0.0, 1.0, 0.0),
        LoadDirection.PROJECTED_Z:  glm.vec3(0.0, 0.0, 1.0),
    }
    if d in _FIXED:
        return _FIXED[d]

    # LOCAL_1/2/3
    if d in (LoadDirection.LOCAL_1, LoadDirection.LOCAL_2, LoadDirection.LOCAL_3):
        return _resolve_local(d, frame_R, poly_u, poly_v, poly_n, default)

    logger.warning(f"[resolve_direction_vector] Bilinmeyen LoadDirection: {d}")
    return default


def _coerce_to_enum(value) -> Optional[LoadDirection]:
    if value is None:
        return None
    if isinstance(value, LoadDirection):
        return value

    s = str(value).strip()
    try:
        return LoadDirection[s]
    except KeyError:
        pass
    for member in LoadDirection:
        if member.value == s:
            return member

    aliases = {
        "X": LoadDirection.GLOBAL_X, "Y": LoadDirection.GLOBAL_Y, "Z": LoadDirection.GLOBAL_Z,
        "GX": LoadDirection.GLOBAL_X, "GY": LoadDirection.GLOBAL_Y, "GZ": LoadDirection.GLOBAL_Z,
        "GRAVITY": LoadDirection.GRAVITY, "GRAV": LoadDirection.GRAVITY,
        "1": LoadDirection.LOCAL_1, "2": LoadDirection.LOCAL_2, "3": LoadDirection.LOCAL_3,
    }
    return aliases.get(s.upper())


def _resolve_local(d, frame_R, poly_u, poly_v, poly_n, default):
    """
    LOCAL_1/2/3 → dünya vektörü.
    glm.mat3 sütunları (column-major): R[0]=e1, R[1]=e2, R[2]=e3.
    """
    idx = {LoadDirection.LOCAL_1: 0,
           LoadDirection.LOCAL_2: 1,
           LoadDirection.LOCAL_3: 2}[d]

    # 1) Frame rotasyonu (öncelik)
    if frame_R is not None:
        try:
            col = frame_R[idx]                       # glm.mat3 sütunu
            v = glm.vec3(float(col[0]), float(col[1]), float(col[2]))
            L = glm.length(v)
            if L > 1e-9:
                return v / L
        except Exception:
            logger.exception("[resolve_direction_vector] frame_R erişim hatası")

    # 2) Polygon eksenleri (fallback)
    poly_axes = (poly_u, poly_v, poly_n)
    axis = poly_axes[idx]
    if axis is not None:
        L = glm.length(axis)
        if L > 1e-9:
            return axis / L

    logger.warning(f"[resolve_direction_vector] {d} için bağlam eksik.")
    return default


# ============================================================================
# POLYGON ALANI / BEKLENEN TOPLAMLAR
# ============================================================================
def polygon_area_m2(nodes) -> float:
    """
    3D polygon alanı (m²).
    Node koordinatları mm cinsinden varsayılır → 1e-6 ile m²'ye çevrilir.
    """
    if len(nodes) < 3:
        return 0.0
    origin = glm.vec3(nodes[0].x, nodes[0].y, nodes[0].z)
    area_v = glm.vec3(0.0, 0.0, 0.0)
    for i in range(1, len(nodes) - 1):
        p1 = glm.vec3(nodes[i].x, nodes[i].y, nodes[i].z) - origin
        p2 = glm.vec3(nodes[i + 1].x, nodes[i + 1].y, nodes[i + 1].z) - origin
        area_v += glm.cross(p1, p2)
    area_mm2 = glm.length(area_v) * 0.5
    return area_mm2 * 1e-6


def expected_polygon_totals(polygon) -> Dict[str, Dict[str, float]]:
    """
    Poligon yükünün beklenen global bileşenleri (kN).
    Döner: {pattern_name: {"fx": ..., "fy": ..., "fz": ...}}
    """
    if len(polygon.nodes) < 3:
        return {}

    _, u, v, n = polygon_plane_frame(polygon.nodes)
    area_m2 = polygon_area_m2(polygon.nodes)

    totals: Dict[str, Dict[str, float]] = {}
    for load in polygon.uniform_to_frame_loads:
        dir_v = resolve_direction_vector(
            load.direction, poly_u=u, poly_v=v, poly_n=n
        )
        F = load.value * area_m2
        entry = totals.setdefault(load.pattern_name, {"fx": 0.0, "fy": 0.0, "fz": 0.0})
        entry["fx"] += F * dir_v.x
        entry["fy"] += F * dir_v.y
        entry["fz"] += F * dir_v.z
    return totals


# ============================================================================
# FRAME TOPLAMLARI
# ============================================================================
def _frames_on_polygon_plane(scene, polygon, tolerance=15.0):
    """
    Dağıtımda kullanılanla AYNI filtre: poligon düzlemindeki tüm frame'ler.
    (Poligona node ile bağlı olması gerekmez.)
    """
    if len(polygon.nodes) < 3:
        return {}

    origin, _, _, n = polygon_plane_frame(polygon.nodes)
    result = {}
    for fid, frame in scene.frames.items():
        if not frame.node_i or not frame.node_j:
            continue
        pi = glm.vec3(frame.node_i.x, frame.node_i.y, frame.node_i.z)
        pj = glm.vec3(frame.node_j.x, frame.node_j.y, frame.node_j.z)
        di = abs(glm.dot(pi - origin, n))
        dj = abs(glm.dot(pj - origin, n))
        if di <= tolerance and dj <= tolerance:
            result[fid] = frame
    return result


def actual_frame_totals(scene, polygon, pattern_name) -> Dict[str, float]:
    """
    Poligon düzlemindeki frame'lerde o pattern için biriken toplam kuvvet (kN).
    """
    totals = {"fx": 0.0, "fy": 0.0, "fz": 0.0}

    _, u, v, n = polygon_plane_frame(polygon.nodes)
    frames = _frames_on_polygon_plane(scene, polygon)

    for fid, frame in frames.items():
        R = frame_local_axes(frame.node_i, frame.node_j, frame.rotation_deg)
        L_m = frame.get_length() * 1e-3

        for dl in frame.dist_loads:
            if dl.pattern_name != pattern_name:
                continue
            p_avg = (dl.p1 + dl.p2) * 0.5
            F = p_avg * L_m
            dir_v = resolve_direction_vector(
                dl.direction, frame_R=R, poly_u=u, poly_v=v, poly_n=n
            )
            totals["fx"] += F * dir_v.x
            totals["fy"] += F * dir_v.y
            totals["fz"] += F * dir_v.z
    return totals


# ============================================================================
# RAPOR API
# ============================================================================
class LoadBalanceReport:

    @staticmethod
    def check_all_polygons(scene, tolerance_ratio: float = 0.005) -> List[dict]:
        results = []
        for poly in scene.polygons.values():
            if not getattr(poly, "uniform_to_frame_loads", None):
                continue
            results.append(LoadBalanceReport.check_polygon(scene, poly, tolerance_ratio))
        return results

    @staticmethod
    def check_polygon(scene, polygon, tolerance_ratio: float = 0.005) -> dict:
        expected = expected_polygon_totals(polygon)
        patterns = []
        for pattern in expected:
            act = actual_frame_totals(scene, polygon, pattern)
            exp = expected[pattern]
            max_exp = max(abs(exp["fx"]), abs(exp["fy"]), abs(exp["fz"]), 1e-6)
            tol = max(0.001, tolerance_ratio * max_exp)
            diff = {k: act[k] - exp[k] for k in ("fx", "fy", "fz")}
            ok = all(abs(diff[k]) <= tol for k in diff)
            patterns.append({
                "pattern": pattern,
                "expected": exp,
                "actual": act,
                "diff": diff,
                "tolerance": tol,
                "ok": ok,
            })
        return {
            "polygon_label": polygon.label,
            "polygon_id": polygon.unique_id,
            "patterns": patterns,
        }

    @staticmethod
    def log_report(scene, tolerance_ratio: float = 0.005) -> int:
        """
        Tüm polygonlar için rapor basar. Başarısız pattern sayısını döner.
        """

        # Sadece 1 poligonu örnek olarak incele
        poly = next(iter(scene.polygons.values()))
        from domain.local_axes import polygon_plane_frame
        origin, u, v, n = polygon_plane_frame(poly.nodes)
        logger.info(f"[DEBUG] Polygon '{poly.label}' normal = {n}")

        # İlk frame
        f = next(iter(scene.frames.values()))
        from domain.local_axes import frame_local_axes
        R = frame_local_axes(f.node_i, f.node_j, f.rotation_deg)
        logger.info(f"[DEBUG] Frame '{f.label}' axis={f.get_axis()}, rot={f.rotation_deg}")
        logger.info(f"[DEBUG] Frame R[0]={R[0]}, R[1]={R[1]}, R[2]={R[2]}")
        logger.info(f"[DEBUG] Frame local 1={R[0]}, local 2={R[1]}, local 3={R[2]}")

        for dl in f.dist_loads:
            logger.info(f"[DEBUG] Frame load: pattern={dl.pattern_name}, dir={dl.direction}, p={dl.p1}")
            
        reports = LoadBalanceReport.check_all_polygons(scene, tolerance_ratio)
        if not reports:
            logger.info("[LoadBalance] Kontrol edilecek poligon yükü yok.")
            return 0

        failed = 0
        logger.info("=" * 78)
        logger.info("  LOAD BALANCE REPORT")
        logger.info("=" * 78)

        for rep in reports:
            logger.info(f"Polygon '{rep['polygon_label']}' (id={rep['polygon_id']})")
            logger.info(
                f"  {'Pattern':<12} | {'Ex FX':>9} {'Ex FY':>9} {'Ex FZ':>9} | "
                f"{'Ac FX':>9} {'Ac FY':>9} {'Ac FZ':>9} | Status"
            )
            for p in rep["patterns"]:
                exp, act = p["expected"], p["actual"]
                status = "OK" if p["ok"] else "FAIL"
                if not p["ok"]:
                    failed += 1
                logger.info(
                    f"  {p['pattern']:<12} | "
                    f"{exp['fx']:>9.2f} {exp['fy']:>9.2f} {exp['fz']:>9.2f} | "
                    f"{act['fx']:>9.2f} {act['fy']:>9.2f} {act['fz']:>9.2f} | {status}"
                )
            logger.info("-" * 78)

        logger.info(f"[LoadBalance] Toplam {failed} başarısız pattern.")
        return failed