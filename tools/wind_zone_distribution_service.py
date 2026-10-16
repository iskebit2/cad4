# tools/wind_zone_distribution_service.py
import numpy as np
from typing import List, Tuple, Optional

from domain.element import Frame, Polygon, PolygonType
from domain.definition import (
    FrameDistributedLoadSet, LoadSegment,
    FrameDistributedLoad, LoadDirection,
)
from tools.frame_load_service import FrameLoadService
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class WindZoneDistributionService:
    """
    Zone poligonlarını frame'lere dağıtır.
    Pattern şeması: WIND_{NN}_{KIND}_{CPE}_{CPI}
    Örnek: WIND_01_CPE10_MN_P
    """

    # Pattern şeması sabitleri
    PATTERN_PREFIX = "WIND"
    KIND_CPE10 = "CPE10"
    KIND_CPE1 = "CPE1"
    CPE_MIN = "MN"
    CPE_MAX = "MX"
    CPI_POS = "P"
    CPI_NEG = "M"

    # Frame yük yönü (rüzgar kirişe dik → Local 2)
    COORD_SYS = "Local"
    LOAD_DIR = "2"

    # Toleranslar
    EPS = 1e-9
    Q_ZERO = 1e-6

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    @classmethod
    def distribute(
        cls,
        scene,
        *,
        definitions=None,
        kind: str = "CPE10",
        cpi_positive: float = 0.2,
        cpi_negative: float = -0.3,
        tributary_width: float = 1.0,
        clear_existing: bool = True,
        unit_scale_to_m: Optional[float] = None,
    ) -> int:
        if scene is None:
            logger.warning("[WindZone] Sahne yok.")
            return 0

        if kind not in (cls.KIND_CPE10, cls.KIND_CPE1):
            raise ValueError(f"Geçersiz kind: {kind!r}.")

        if unit_scale_to_m is None:
            unit_scale_to_m = cls._infer_unit_scale(scene)

        zones = cls._collect_zones(scene)
        if not zones:
            logger.info("[WindZone] Zone poligonu yok.")
            return 0

        logger.info(f"[WindZone] {len(zones)} zone, {len(scene.frames)} frame, KIND={kind}")

        # Tüm frame'lerde dist_load_sets dict olduğundan emin ol
        for frame in scene.frames.values():
            if not hasattr(frame, "dist_load_sets") or frame.dist_load_sets is None:
                frame.dist_load_sets = {}

        if clear_existing:
            cls._clear_wind_patterns(scene)

        total = 0
        for zone in zones:
            n = cls._distribute_one_zone(
                scene, zone,
                kind=kind,
                cpi_pos=cpi_positive,
                cpi_neg=cpi_negative,
                tributary_width=tributary_width,
                unit_scale_to_m=unit_scale_to_m,
                definitions=definitions,
            )
            total += n

        logger.info(f"[WindZone] Toplam {total} segment atandı.")
        return total

    # ------------------------------------------------------------------
    # ZONE İŞLEME
    # ------------------------------------------------------------------
    @classmethod
    def _distribute_one_zone(
        cls, scene, zone, *,
        kind, cpi_pos, cpi_neg, tributary_width,
        unit_scale_to_m, definitions,
    ) -> int:
        wp = getattr(zone, "windplane", {}) or {}
        dir_idx = int(wp.get("dir_idx", 1))
        q_p = float(wp.get("q_p", 0.5))

        if kind == cls.KIND_CPE10:
            cpe_raw = wp.get("cpe10", [0.0, 0.0])
        else:
            cpe_raw = wp.get("cpe1", [0.0, 0.0])

        if isinstance(cpe_raw, (tuple, list)):
            cpe_min = float(cpe_raw[0]) if len(cpe_raw) > 0 else 0.0
            cpe_max = float(cpe_raw[1]) if len(cpe_raw) > 1 else cpe_min
        else:
            cpe_min = cpe_max = float(cpe_raw)

        combinations = []
        if abs(cpe_min) > cls.EPS:
            combinations.append((cls.CPE_MIN, cls.CPI_POS, cpe_min, cpi_pos))
            combinations.append((cls.CPE_MIN, cls.CPI_NEG, cpe_min, cpi_neg))
        if abs(cpe_max) > cls.EPS:
            combinations.append((cls.CPE_MAX, cls.CPI_POS, cpe_max, cpi_pos))
            combinations.append((cls.CPE_MAX, cls.CPI_NEG, cpe_max, cpi_neg))

        if not combinations:
            return 0

        poly_2d = cls._polygon_to_2d(zone)
        if len(poly_2d) < 3:
            return 0

        # Frame kesişimlerini bir kere hesapla
        frame_intervals = []
        for frame in scene.frames.values():
            if not frame.node_i or not frame.node_j:
                continue
            p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
            p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
            intervals = cls.compute_line_polygon_intersections(p1, p2, poly_2d)
            if intervals:
                frame_intervals.append((frame, intervals))

        if not frame_intervals:
            return 0

        total = 0
        for cpe_kind, cpi_kind, cpe_val, cpi_val in combinations:
            w = q_p * (cpe_val - cpi_val) * tributary_width
            if abs(w) < cls.Q_ZERO:
                continue

            pattern_name = f"{cls.PATTERN_PREFIX}_{dir_idx:02d}_{kind}_{cpe_kind}_{cpi_kind}"

            if definitions is not None:
                cls._ensure_load_pattern(definitions, pattern_name)

            for frame, intervals in frame_intervals:
                new_segs = []
                for (t_start, t_end) in intervals:
                    if t_end - t_start < 1e-6:
                        continue
                    new_segs.append(LoadSegment(
                        x1=float(t_start), x2=float(t_end),
                        q1=w, q2=w,
                    ))
                if not new_segs:
                    continue

                existing = frame.dist_load_sets.get(pattern_name)
                if existing:
                    existing.segments.extend(new_segs)
                    existing.segments.sort(key=lambda s: s.x1)
                    existing.segments = cls._merge_segments(existing.segments)
                    frame.mark_dirty()
                else:
                    new_set = FrameDistributedLoadSet(
                        pattern_name=pattern_name,
                        coord_sys=cls.COORD_SYS,
                        load_dir=cls.LOAD_DIR,
                        mode="REPLACE",
                        is_relative=True,
                        segments=cls._merge_segments(new_segs),
                    )
                    FrameLoadService.assign_distributed_load_set(frame, new_set)

                total += len(new_segs)

        return total

    @classmethod
    def _merge_segments(cls, segs):
        if not segs:
            return []
        segs = sorted(segs, key=lambda s: (s.x1, s.x2))
        merged = [segs[0]]
        for s in segs[1:]:
            last = merged[-1]
            if s.x1 <= last.x2 + 1e-6:
                if abs(s.q1 - last.q2) < 1e-6 and abs(s.q2 - last.q2) < 1e-6:
                    last.x2 = max(last.x2, s.x2)
                    last.q2 = s.q2
                else:
                    if s.x1 < last.x2:
                        last.x2 = s.x1
                    merged.append(s)
            else:
                merged.append(s)
        return merged

    @classmethod
    def _ensure_load_pattern(cls, definitions, name):
        if definitions is None:
            return
        try:
            if name not in definitions.load_patterns:
                from domain.definition import LoadPattern
                definitions.load_patterns[name] = LoadPattern(
                    name=name,
                    design_type="WIND",
                    self_wt_mult=0.0,
                )
        except Exception as e:
            logger.warning(f"[WindZone] LoadPattern kaydedilemedi: {e}")

    @classmethod
    def _clear_wind_patterns(cls, scene):
        for frame in scene.frames.values():
            sets = getattr(frame, "dist_load_sets", {})
            if sets:
                for k in list(sets.keys()):
                    if k.startswith(cls.PATTERN_PREFIX):
                        del sets[k]
            dist = getattr(frame, "dist_loads", None)
            if dist:
                frame.dist_loads = [
                    dl for dl in dist
                    if not dl.pattern_name.startswith(cls.PATTERN_PREFIX)
                ]
            if hasattr(frame, "mark_dirty"):
                frame.mark_dirty()

    # ------------------------------------------------------------------
    # GEOMETRİ
    # ------------------------------------------------------------------
    @classmethod
    def compute_line_polygon_intersections(cls, line_p1, line_p2, poly_nodes_2d):
        p1 = np.array(line_p1[:2], dtype=float)
        p2 = np.array(line_p2[:2], dtype=float)
        d = p2 - p1
        if float(np.dot(d, d)) < 1e-12:
            return []

        ts = [0.0, 1.0]
        n = len(poly_nodes_2d)
        for i in range(n):
            a = np.array(poly_nodes_2d[i][:2], dtype=float)
            b = np.array(poly_nodes_2d[(i + 1) % n][:2], dtype=float)
            v = b - a
            cross = d[0] * v[1] - d[1] * v[0]
            if abs(cross) < 1e-12:
                continue
            delta = a - p1
            t = (delta[0] * v[1] - delta[1] * v[0]) / cross
            s = (delta[0] * d[1] - delta[1] * d[0]) / cross
            if 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0:
                ts.append(float(t))

        ts = sorted(set(ts))
        intervals = []
        for i in range(len(ts) - 1):
            t_start, t_end = ts[i], ts[i + 1]
            if t_end - t_start < cls.EPS:
                continue
            t_mid = (t_start + t_end) * 0.5
            mid_pt = p1 + t_mid * d
            if cls._is_point_inside_2d(mid_pt, poly_nodes_2d):
                intervals.append((t_start, t_end))
        return intervals

    @staticmethod
    def _is_point_inside_2d(pt, poly_nodes_2d):
        x, y = float(pt[0]), float(pt[1])
        inside = False
        n = len(poly_nodes_2d)
        j = n - 1
        for i in range(n):
            xi, yi = poly_nodes_2d[i][0], poly_nodes_2d[i][1]
            xj, yj = poly_nodes_2d[j][0], poly_nodes_2d[j][1]
            if ((yi > y) != (yj > y)) and \
               (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    # ------------------------------------------------------------------
    # YARDIMCILAR
    # ------------------------------------------------------------------
    @classmethod
    def _collect_zones(cls, scene):
        zones = []
        for poly in scene.polygons.values():
            pt = getattr(poly, "poly_type", None)
            lbl = (poly.label or "").upper()
            is_zone = False
            try:
                if pt == PolygonType.ZONE:
                    is_zone = True
            except Exception:
                pass
            if not is_zone:
                pt_str = getattr(pt, "name", None) or str(pt or "")
                if pt_str.upper() == "ZONE":
                    is_zone = True
            if not is_zone and (lbl.startswith("ZONE_") or lbl.startswith("ZONE")):
                is_zone = True
            if not is_zone:
                wp = getattr(poly, "windplane", {}) or {}
                if wp.get("cpe10") is not None or wp.get("q_p") is not None:
                    is_zone = True
            if is_zone:
                zones.append(poly)
        return zones

    @staticmethod
    def _polygon_to_2d(poly):
        return [(n.x, n.y) for n in poly.nodes]

    @staticmethod
    def _infer_unit_scale(scene):
        us = getattr(scene, "unit_system", None)
        if us is None:
            return 1e-3
        length = getattr(us, "length_unit", "mm")
        return {"mm": 1e-3, "cm": 1e-2, "m": 1.0,
                "in": 0.0254, "ft": 0.3048}.get(length.lower(), 1e-3)