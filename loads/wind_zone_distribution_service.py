# loads/wind_zone_distribution_service.py
"""
WindZoneDistributionService — Rüzgar zone'larını frame'lere dağıtır.

Mimari:
    SURFACE_ONEWAY / SURFACE_TWOWAY  →  AlignmentService ile frame'lere bağlanır
                                            ↓
                                         surface.associated_frame_ids
                                            ↓
    ZONE  →  zone.windplane["surface"] referansı ile surface'ı bulur
         →  surface'ın bağlı frame'lerine yük atar
         →  zone.coords kendi sınırı olarak kullanılır

Pattern şeması: WIND_{NN}_{KIND}_{CPE}_{CPI}
Örnek:          WIND_01_CPE10_MN_P
"""
from __future__ import annotations

import numpy as np
from typing import Optional, List, Dict, Any

from data.enums import PolygonType, UnitSystem
from domain.plane import Plane
from domain.definition import FrameDistributedLoad, LoadSegment
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class WindZoneDistributionService:
    """Zone poligonlarındaki rüzgar yüklerini, surface üzerinden frame'lere aktarır."""

    # --- Pattern şeması ---
    PATTERN_PREFIX = "WIND"
    KIND_CPE10 = "CPE10"
    KIND_CPE1 = "CPE1"
    CPE_MIN = "MN"
    CPE_MAX = "MX"
    CPI_POS = "P"
    CPI_NEG = "M"

    # --- Frame yük parametreleri ---
    # Rüzgar yükü poligon düzlemine DİK olduğu için, frame'in düzleme dik
    # local eksenine yüklenir. Çizimde bu Local 2 olarak doğrulandı.
    COORD_SYS = "Local"
    LOAD_DIR = "2"

    # --- Sayısal toleranslar ---
    EPS = 1e-9
    Q_ZERO = 1e-6
    E1_DOT_N_MAX = 0.99     # frame boyu düzleme bu kadar dikse → atla
    PLANE_TOL_MM = 50.0     # düzlem mesafesi toleransı (mm)

    # --- Rüzgar yönü vektörleri ---
    WIND_DIRS: Dict[int, np.ndarray] = {
        1: np.array([ 1.0,  0.0,  0.0]),
        2: np.array([ 0.0,  1.0,  0.0]),
        3: np.array([-1.0,  0.0,  0.0]),
        4: np.array([ 0.0, -1.0,  0.0]),
        5: np.array([ 0.0,  0.0,  1.0]),
        6: np.array([ 0.0,  0.0, -1.0]),
    }

    # ==================================================================
    # PUBLIC API
    # ==================================================================
    @classmethod
    def distribute(
        cls,
        scene,
        *,
        project=None,
        kind: str = "CPE10",
        cpi_positive: float = 0.2,
        cpi_negative: float = -0.3,
        tributary_width: float = 1.0,
        clear_existing: bool = True,
    ) -> int:
        """
        Sahnedeki tüm ZONE poligonlarını işler ve yükleri frame'lere dağıtır.

        Returns: atanan toplam segment sayısı
        """
        if scene is None:
            logger.warning("[WindZone] Sahne yok.")
            return 0

        if kind not in (cls.KIND_CPE10, cls.KIND_CPE1):
            raise ValueError(f"Geçersiz kind: {kind!r}. "
                             f"Beklenen: {cls.KIND_CPE10} veya {cls.KIND_CPE1}")

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
                project=project,
            )
            total += n

        logger.info(f"[WindZone] Toplam {total} segment atandı.")
        return total

    # ==================================================================
    # TOLERANS
    # ==================================================================
    @classmethod
    def _plane_tolerance(cls, project_or_scene) -> float:
        """Birim sistemine göre düzlem toleransı (sahne birimi cinsinden)."""
        us = getattr(project_or_scene, "unit_system", UnitSystem.N_MM)
        if us in (UnitSystem.KN_M, UnitSystem.TON_M):
            return cls.PLANE_TOL_MM / 1000.0
        if us in (UnitSystem.KN_CM, UnitSystem.KGF_CM):
            return cls.PLANE_TOL_MM / 10.0
        return float(cls.PLANE_TOL_MM)

    # ==================================================================
    # SURFACE BULMA
    # ==================================================================
    @classmethod
    def _find_surface(cls, scene, surface_ref) -> Optional[Any]:
        """
        zone.windplane["surface"] → surface Polygon.
        surface_ref: unique_id'nin string veya int hali.
        """
        if surface_ref is None:
            return None

        # int'e çevirmeyi dene
        try:
            sid = int(surface_ref)
        except (ValueError, TypeError):
            # unique_id fallback
            for poly in scene.polygons.values():
                if str(getattr(poly, "unique_id", "")) == str(surface_ref):
                    pt = getattr(poly, "poly_type", None)
                    if pt in (PolygonType.SURFACE_ONEWAY,
                              PolygonType.SURFACE_TWOWAY):
                        return poly
            return None

        for poly in scene.polygons.values():
            if poly.unique_id == sid:
                pt = getattr(poly, "poly_type", None)
                if pt in (PolygonType.SURFACE_ONEWAY,
                          PolygonType.SURFACE_TWOWAY):
                    return poly
                logger.warning(
                    f"[WindZone] surface_ref={surface_ref} bulundu ama tip "
                    f"SURFACE değil: {pt}"
                )
                return None

        return None

    # ==================================================================
    # ZONE İŞLEME
    # ==================================================================
    @classmethod
    def _distribute_one_zone(
        cls, scene, zone, *,
        kind: str,
        cpi_pos: float,
        cpi_neg: float,
        tributary_width: float,
        project,
    ) -> int:
        zone_id = getattr(zone, "unique_id", "?")

        # --- 1) Zone windplane verisi ---
        wp = getattr(zone, "windplane", {}) or {}
        if not wp:
            logger.warning(f"[WindZone] zone={zone_id} windplane boş")
            return 0

        dir_idx = int(wp.get("dir_idx", 1))
        q_p = float(wp.get("q_p", 0.5))

        # --- 2) cpe değerleri ---
        if kind == cls.KIND_CPE10:
            cpe_raw = wp.get("cpe10", [0.0, 0.0])
        else:
            cpe_raw = wp.get("cpe1", [0.0, 0.0])

        if isinstance(cpe_raw, (tuple, list)):
            cpe_min = float(cpe_raw[0]) if len(cpe_raw) > 0 else 0.0
            cpe_max = float(cpe_raw[1]) if len(cpe_raw) > 1 else cpe_min
        else:
            cpe_min = cpe_max = float(cpe_raw)

        combinations: List[tuple] = []
        if abs(cpe_min) > cls.EPS:
            combinations.append((cls.CPE_MIN, cls.CPI_POS, cpe_min, cpi_pos))
            combinations.append((cls.CPE_MIN, cls.CPI_NEG, cpe_min, cpi_neg))
        if abs(cpe_max) > cls.EPS:
            combinations.append((cls.CPE_MAX, cls.CPI_POS, cpe_max, cpi_pos))
            combinations.append((cls.CPE_MAX, cls.CPI_NEG, cpe_max, cpi_neg))

        if not combinations:
            logger.info(f"[WindZone] zone={zone_id} cpe kombinasyonu yok")
            return 0

        # --- 3) Surface'ı bul ---
        surface_ref = wp.get("surface")
        if surface_ref is None:
            logger.warning(f"[WindZone] zone={zone_id} windplane'de 'surface' yok")
            return 0

        surface_poly = cls._find_surface(scene, surface_ref)
        if surface_poly is None:
            logger.warning(f"[WindZone] zone={zone_id} surface='{surface_ref}' "
                           f"bulunamadı")
            return 0

        surface_id = getattr(surface_poly, "unique_id", "?")
        associated_ids = list(getattr(surface_poly, "associated_frame_ids", []))
        if not associated_ids:
            logger.warning(f"[WindZone] zone={zone_id} surface={surface_id} "
                           f"associated_frame_ids boş — önce alignment çalıştırın")
            return 0

        # --- 4) Zone'un düzlemi ve 2D sınırları ---
        if len(zone.nodes) < 3:
            logger.warning(f"[WindZone] zone={zone_id} < 3 node")
            return 0

        try:
            zone_plane = Plane.from_polygon(zone)
        except ValueError as e:
            logger.warning(f"[WindZone] zone={zone_id} plane hatası: {e}")
            return 0

        zone_2d = zone_plane.polygon_to_2d(zone)
        if len(zone_2d) < 3:
            return 0

        zone_normal_np = np.asarray(zone_plane.normal, dtype=float)

        # --- 5) İşaret düzeltmesi: rüzgar yönü vs zone normali ---
        wind_vec = cls.WIND_DIRS.get(dir_idx, np.array([1.0, 0.0, 0.0]))
        flip_sign = float(np.dot(zone_normal_np, wind_vec)) > 0.0

        logger.info(
            f"[WindZone] zone={zone_id} surface={surface_id} "
            f"dir={dir_idx} q_p={q_p:.3f} "
            f"cpe=[{cpe_min:.3f},{cpe_max:.3f}] "
            f"n·wind={float(np.dot(zone_normal_np, wind_vec)):+.3f} "
            f"flip={flip_sign} "
            f"assoc_frames={len(associated_ids)}"
        )

        # --- 6) Hedef frame'ler ---
        associated_set = set(associated_ids)
        target_frames = [f for f in scene.frames.values()
                         if f.unique_id in associated_set]

        tol = cls._plane_tolerance(project or scene)

        # --- 7) Her frame için zone sınırları içindeki kesişim aralığı ---
        frame_intervals: List[tuple] = []

        for frame in target_frames:
            if not frame.is_visible or not frame.node_i or not frame.node_j:
                continue

            p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
            p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)

            # Frame'in iki ucu da zone düzleminde mi?
            if zone_plane.distance_abs(p1) > tol:
                continue
            if zone_plane.distance_abs(p2) > tol:
                continue

            # Frame boyu zone düzlemine dik mi?
            ax = frame.get_axis()
            ax_np = np.asarray(ax, dtype=float)
            L = float(np.linalg.norm(ax_np))
            if L < 1e-9:
                continue
            ax_np = ax_np / L
            e1_dot_n = abs(float(np.dot(ax_np, zone_normal_np)))
            if e1_dot_n > cls.E1_DOT_N_MAX:
                continue

            # Zone'un 2D sınırları içindeki kesişim
            intervals = cls._line_polygon_intersections_2d(
                zone_plane.to_2d(p1), zone_plane.to_2d(p2), zone_2d
            )
            if intervals:
                frame_intervals.append((frame, intervals))

        if not frame_intervals:
            logger.info(f"[WindZone] zone={zone_id} için frame kesişimi yok")
            return 0

        # --- 8) Yük atama ---
        total = 0
        for cpe_kind, cpi_kind, cpe_val, cpi_val in combinations:
            w = q_p * (cpe_val - cpi_val) * tributary_width
            if flip_sign:
                w = -w

            if abs(w) < cls.Q_ZERO:
                continue

            pattern_name = (f"{cls.PATTERN_PREFIX}_{dir_idx:02d}_"
                            f"{kind}_{cpe_kind}_{cpi_kind}")

            if project is not None:
                cls._ensure_load_pattern(project, pattern_name)

            for frame, intervals in frame_intervals:
                new_segs: List[LoadSegment] = []
                for (t_start, t_end) in intervals:
                    if t_end - t_start < 1e-6:
                        continue
                    new_segs.append(LoadSegment(
                        x1=float(t_start), x2=float(t_end),
                        q1=float(w), q2=float(w),
                    ))
                if not new_segs:
                    continue

                existing = frame.dist_load_sets.get(pattern_name)
                if existing is not None:
                    existing.segments.extend(new_segs)
                    existing.segments = cls._merge_segments(existing.segments)
                    frame.mark_dirty()
                else:
                    new_load = FrameDistributedLoad(
                        pattern_name=pattern_name,
                        coord_sys=cls.COORD_SYS,
                        load_dir=cls.LOAD_DIR,
                        mode="REPLACE",
                        is_relative=True,
                        segments=cls._merge_segments(new_segs),
                    )
                    frame.dist_load_sets[pattern_name] = new_load
                    frame.mark_dirty()

                total += len(new_segs)

        return total

    # ==================================================================
    # 2D KESİŞİM
    # ==================================================================
    @staticmethod
    def _line_polygon_intersections_2d(
        p1_2d, p2_2d, poly_2d
    ) -> List[tuple]:
        """
        Bir çizgi parçasının (p1_2d → p2_2d) kapalı poligon (poly_2d) ile
        kesişim aralıklarını t ∈ [0, 1] cinsinden döndürür.
        Tüm koordinatlar zaten lokal 2D'dedir.
        """
        p1 = np.asarray(p1_2d, dtype=float)
        p2 = np.asarray(p2_2d, dtype=float)
        d = p2 - p1
        if float(np.dot(d, d)) < 1e-12:
            return []

        n = len(poly_2d)
        ts = [0.0, 1.0]

        for i in range(n):
            a = np.asarray(poly_2d[i], dtype=float)
            b = np.asarray(poly_2d[(i + 1) % n], dtype=float)
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
        intervals: List[tuple] = []
        for i in range(len(ts) - 1):
            t_start, t_end = ts[i], ts[i + 1]
            if t_end - t_start < 1e-9:
                continue
            t_mid = (t_start + t_end) * 0.5
            mid_pt = p1 + t_mid * d
            if Plane._point_in_polygon_2d(mid_pt[0], mid_pt[1], poly_2d):
                intervals.append((t_start, t_end))
        return intervals

    # ==================================================================
    # SEGMENT MERGE
    # ==================================================================
    @classmethod
    def _merge_segments(cls, segs: List[LoadSegment]) -> List[LoadSegment]:
        """Bitişik ve aynı q değerine sahip segmentleri birleştirir."""
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

    # ==================================================================
    # LOAD PATTERN
    # ==================================================================
    @classmethod
    def _ensure_load_pattern(cls, definitions, name: str) -> None:
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
    def _clear_wind_patterns(cls, scene) -> None:
        for frame in scene.frames.values():
            sets = getattr(frame, "dist_load_sets", {})
            if sets:
                for k in list(sets.keys()):
                    if k.startswith(cls.PATTERN_PREFIX):
                        del sets[k]
            if hasattr(frame, "mark_dirty"):
                frame.mark_dirty()

    # ==================================================================
    # ZONE TOPLAMA
    # ==================================================================
    @classmethod
    def _collect_zones(cls, scene) -> List[Any]:
        """Sahnedeki ZONE poligonlarını döndürür."""
        zones = []
        for poly in scene.polygons.values():
            pt = getattr(poly, "poly_type", None)

            is_zone = False
            if pt == PolygonType.ZONE:
                is_zone = True
            else:
                pt_str = getattr(pt, "name", None) or str(pt or "")
                if pt_str.upper() == "ZONE":
                    is_zone = True

            if not is_zone:
                # windplane dolu olanları da zone say
                wp = getattr(poly, "windplane", None)
                if wp and isinstance(wp, dict) and wp.get("surface") is not None:
                    is_zone = True

            if is_zone:
                zones.append(poly)
        return zones