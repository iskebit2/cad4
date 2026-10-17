# tools/alignment_service.py
from __future__ import annotations
import numpy as np
from typing import List
from domain.plane import Plane
from data.enums import UnitSystem, PolygonType
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class AlignmentService:

    @staticmethod
    def _tolerance_mm_to_units(project_or_scene, mm: float) -> float:
        us = getattr(project_or_scene, "unit_system", UnitSystem.N_MM)
        if us in (UnitSystem.KN_M, UnitSystem.TON_M):
            return mm / 1000.0
        if us in (UnitSystem.KN_CM, UnitSystem.KGF_CM):
            return mm / 10.0
        return float(mm)

    @staticmethod
    def align_frames_to_polygons(scene, polygons: List, project=None,
                                  skip_vertical: bool = True,
                                  tolerance_mm: float = 50.0) -> int:
        """
        Frame'leri poly'lere bağlar.

        Filtreleme, poly.poly_type'a göre otomatik yapılır:
            SURFACE_ONEWAY / GENERIC → sadece primary yöndeki frame'ler
            SURFACE_TWOWAY           → her iki yöndeki frame'ler
        """
        if not polygons:
            return 0

        tolerance = AlignmentService._tolerance_mm_to_units(
            project or scene, tolerance_mm
        )
        matched = 0
        aligned = 0

        for poly in polygons:
            if len(poly.nodes) < 3:
                continue

            # Poly tipi
            poly_type = getattr(poly, "poly_type", PolygonType.GENERIC)
            is_two_way = (poly_type == PolygonType.SURFACE_TWOWAY)
            is_one_way = (poly_type in (PolygonType.SURFACE_ONEWAY,
                                        PolygonType.GENERIC))

            # ZONE / SECTION_CUT / LOAD_AREA için frame bağlama
            if poly_type in (PolygonType.SECTION_CUT, PolygonType.LOAD_AREA):
                continue
            # ZONE'lar ayrı bir akışta ele alınır (wind analysis)

            try:
                plane = Plane.from_polygon(poly)
            except ValueError as e:
                logger.warning(f"[Align] poly {getattr(poly,'unique_id','?')}: {e}")
                continue

            n_np = np.asarray(plane.normal, dtype=float)
            u_np = np.asarray(plane.u, dtype=float)
            v_np = np.asarray(plane.v, dtype=float)

            # Poly'nin 2D boyutları
            poly_2d = plane.polygon_to_2d(poly)
            us = [p[0] for p in poly_2d]
            vs = [p[1] for p in poly_2d]
            u_length = max(us) - min(us)
            v_length = max(vs) - min(vs)

            # Primary yön (one-way için): kısa doğrultu
            primary_is_u = (u_length <= v_length)

            logger.info(f"[Align] poly={getattr(poly,'unique_id','?')} "
                        f"type={poly_type.name} {plane} "
                        f"u_len={u_length:.1f} v_len={v_length:.1f} "
                        f"primary={'u' if primary_is_u else 'v'} "
                        f"two_way={is_two_way}")

            poly.associated_frame_ids = []

            for frame in scene.frames.values():
                if not frame.is_visible or not frame.node_i or not frame.node_j:
                    continue

                ni = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
                nj = (frame.node_j.x, frame.node_j.y, frame.node_j.z)

                # 1. Her iki uç da düzlemde mi?
                if plane.distance_abs(ni) > tolerance:
                    continue
                if plane.distance_abs(nj) > tolerance:
                    continue

                # 2. Frame'in boyu düzleme dik mi?
                ax = frame.get_axis()
                e1_np = np.asarray(ax, dtype=float)
                L = float(np.linalg.norm(e1_np))
                if L < 1e-9:
                    continue
                e1_np = e1_np / L

                e1_dot_n = abs(float(np.dot(e1_np, n_np)))
                if e1_dot_n > 0.99:
                    # Kiriş düzleme dik → yük almaz
                    continue

                # 3. One-way ise primary yön filtresi
                if is_one_way and not is_two_way:
                    e1_proj = e1_np - np.dot(e1_np, n_np) * n_np
                    e1_proj_len = float(np.linalg.norm(e1_proj))
                    if e1_proj_len < 1e-6:
                        continue
                    e1_proj = e1_proj / e1_proj_len

                    cu = abs(float(np.dot(e1_proj, u_np)))
                    cv = abs(float(np.dot(e1_proj, v_np)))
                    frame_is_u = cu > cv

                    if primary_is_u != frame_is_u:
                        continue   # primary yön dışı → atla

                # 4. Bağla
                if frame.unique_id not in poly.associated_frame_ids:
                    poly.associated_frame_ids.append(frame.unique_id)
                    matched += 1

                # 5. Hizalama
                angle = frame.align_to_polygon_plane(poly.nodes)
                if abs(angle) > 1e-6:
                    aligned += 1

        logger.info(f"[Align] {matched} bağlandı, {aligned} hizalandı")
        return matched