# tools/alignment_service.py
"""
Seçili poligon düzlemine, o düzlemde bulunan frame'leri hizalar.

Kullanım:
    from tools.alignment_service import AlignmentService
    n = AlignmentService.align_frames_to_polygons(
        scene, polygons, tolerance=10.0
    )
"""
from __future__ import annotations

from typing import List, Tuple

import glm

from domain.element import Frame, Polygon
from domain.local_axes import align_frame_to_polygon_plane, polygon_plane_axes
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class AlignmentService:

    @staticmethod
    def align_frames_to_polygons(scene,
                                 polygons: List[Polygon],
                                 tolerance: float = 10.0,
                                 skip_vertical: bool = True) -> int:
        """
        Seçili poligonların düzleminde bulunan tüm frame'leri hizalar.

        Parametreler
        ------------
        scene : Scene
        polygons : List[Polygon]
            Hedef poligon(lar).
        tolerance : float
            Frame midpoint ile poligon düzlemi arasındaki maksimum mesafe (mm).
            Bu mesafeden yakın olan frame'ler hizalanır.
        skip_vertical : bool
            True ise poligon normal'ine paralel (düşey) frame'ler atlanır.

        Döner
        -----
        int : hizalanan frame sayısı.
        """
        if not polygons:
            return 0

        aligned_count = 0
        seen = set()  # aynı frame'i iki kez hizalamamak için

        for poly in polygons:
            if len(poly.nodes) < 3:
                continue

            try:
                _, _, n = polygon_plane_axes(poly.nodes)
            except Exception:
                logger.exception("[Align] polygon normal hesaplanamadı")
                continue

            origin = glm.vec3(poly.nodes[0].x, poly.nodes[0].y, poly.nodes[0].z)

            for frame in scene.frames.values():
                if frame.unique_id in seen:
                    continue
                if not frame.is_visible:
                    continue

                mid = frame.get_midpoint()
                mid_v = glm.vec3(mid[0] - origin.x,
                                 mid[1] - origin.y,
                                 mid[2] - origin.z)

                # Nokta-düzlem signed distance
                dist = abs(glm.dot(mid_v, n))
                if dist > tolerance:
                    continue

                # Frame poligon düzlemine paralel mi?
                e1 = glm.vec3(*frame.get_axis())
                L = glm.length(e1)
                if L < 1e-9:
                    continue
                e1 = e1 / L

                if skip_vertical and abs(glm.dot(e1, n)) > 0.999:
                    continue

                angle = align_frame_to_polygon_plane(frame, poly.nodes)
                if abs(angle) > 1e-6:
                    aligned_count += 1
                    seen.add(frame.unique_id)

        logger.info(f"[Align] {aligned_count} frame hizalandı "
                    f"({len(polygons)} poligon, tolerance={tolerance} mm)")
        return aligned_count