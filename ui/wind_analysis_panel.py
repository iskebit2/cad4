# ui/wind_analysis_panel.py
"""Rüzgar analiz paneli — surface seç + yön + zone oluştur."""
from __future__ import annotations

import numpy as np
from imgui_bundle import imgui

from data.enums import PolygonType
from domain.element import Polygon
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class WindAnalysisPanel(BasePanel):

    def __init__(self):
        super().__init__(
            title="Rüzgar Analizi",
            width=520,
            height=560,
            pos_first_use=(200, 100),
        )
        self.app = None
        self.scene = None
        self.project = None

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.scene = ctx.get("scene")
        self.project = self._project()

    def draw_content(self):
        if self.scene is None or self.project is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Sahne/proje bağlı değil.",
            )
            return

        self._draw_surface_selection()
        imgui.separator()
        self._draw_directions()
        imgui.separator()
        self._draw_actions()
        imgui.separator()
        self._draw_zone_summary()

    # ------------------------------------------------------------------
    def _draw_surface_selection(self):
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Surface Polygon'lar",
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            "(LOAD_AREA / SURFACE_* — rüzgar analizine girecek)",
        )

        candidates = [
            p for p in self.scene.polygons.values()
            if not getattr(p, "is_temporary", False)
            and p.poly_type in (
                PolygonType.LOAD_AREA,
                PolygonType.SURFACE_ONEWAY,
                PolygonType.SURFACE_TWOWAY,
            )
        ]

        if not candidates:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Uygun polygon yok. Polygon çiz + tipi SURFACE/LOAD_AREA seç.",
            )
            return

        imgui.begin_child(
            "##surface_list", imgui.ImVec2(0, 140),
            imgui.ChildFlags_.borders,
        )
        try:
            for p in sorted(candidates, key=lambda x: x.label or ""):
                sel = getattr(p, "_wind_selected", False)
                changed, new_val = imgui.checkbox(
                    f"{p.label or 'Polygon'} (id={p.unique_id})##s_{p.unique_id}",
                    sel,
                )
                if changed:
                    p._wind_selected = bool(new_val)
        finally:
            imgui.end_child()

        selected_count = sum(
            1 for p in candidates if getattr(p, "_wind_selected", False)
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
            f"Seçili: {selected_count} polygon",
        )

    # ------------------------------------------------------------------
    def _draw_directions(self):
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Rüzgar Yönleri",
        )

        wind = self._wind_state()
        directions = wind.get("directions", {}) or {}

        if not directions:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Yön yok. 'Yeni Yön' ekle.",
            )

        for key, rec in sorted(directions.items()):
            vec = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            imgui.text(
                f"{key}:  ({vec[0]:.1f}, {vec[1]:.1f}, {vec[2]:.1f})"
            )

        if imgui.button("+ Yeni Yön", imgui.ImVec2(120, 0)):
            self._add_default_direction()

    def _wind_state(self) -> dict:
        analysis = self.project.analysis
        wind = analysis.wind
        if not isinstance(wind, dict):
            wind = {}
            analysis.wind = wind
        if "directions" not in wind or not isinstance(wind["directions"], dict):
            wind["directions"] = {}
        return wind

    def _add_default_direction(self):
        from domain.definition import WindDirectionResult
        wind = self._wind_state()
        dirs = wind["directions"]
        keys = sorted(dirs.keys())
        n = 1
        while f"{n:02d}" in dirs:
            n += 1
        # Basit: sırayla X+, Y+, X-, Y-
        presets = [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
        ]
        vec = presets[(n - 1) % len(presets)]
        dirs[f"{n:02d}"] = WindDirectionResult(w_dir=vec)
        logger.info("[Wind] Yön eklendi: %02d = %s", n, vec)

    # ------------------------------------------------------------------
    def _draw_actions(self):
        if imgui.button(
            "Analiz Et (tüm yönler)",
            imgui.ImVec2(-1, 30),
        ):
            try:
                self._run_analysis_all()
            except Exception:
                logger.exception("[Wind] Analiz hatası")

    def _run_analysis_all(self):
        surfaces = [
            p for p in self.scene.polygons.values()
            if getattr(p, "_wind_selected", False)
        ]
        if not surfaces:
            logger.warning("[Wind] Surface seçilmedi.")
            return

        wind = self._wind_state()
        directions = wind.get("directions", {})
        if not directions:
            logger.warning("[Wind] Yön yok.")
            return

        from tools.wind_scene_adapter import WindSceneAdapter

        for dir_key, rec in directions.items():
            vec = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            try:
                points, polygons, wind_config = (
                    WindSceneAdapter.build_inputs_for_polygons(
                        self.scene, self.project, surfaces,
                    )
                )
                zones, engine_data = WindSceneAdapter.analyze(
                    points, polygons, wind_config, vec,
                )
            except Exception:
                logger.exception("[Wind] Yön %s analiz hatası", dir_key)
                continue

            # Zone'ları surface polygon'lara dağıt
            self._assign_zones_to_polygons(zones, surfaces, dir_key)
            logger.info(
                "[Wind] Yön %s: %d zone", dir_key, len(zones),
            )


        self.scene.mark_dirty()

    def _assign_zones_to_polygons(self, zones, surfaces, dir_key):
        # surface adı → polygon
        by_name = {
            (p.label or f"Polygon_{p.unique_id}"): p for p in surfaces
        }

        # Temizle
        for p in surfaces:
            p.zone_children_by_direction[dir_key] = []

        for z in zones:
            surface_name = getattr(z, "surface", "")
            target = by_name.get(surface_name)
            if target is None:
                continue
            raw_coords = getattr(z, "coords", None)
            if raw_coords is None:
                continue
            coords = list(raw_coords)
            if len(coords) < 3:
                continue

            
            cpe10_raw = getattr(z, "cpe10", 0.0)
            cpe1_raw = getattr(z, "cpe1", 0.0)
            
            if np.isscalar(cpe10_raw) or np.asarray(cpe10_raw).ndim == 0:
                v = float(cpe10_raw)
                cpe10 = (v, v)
            else:
                vals = tuple(float(x) for x in cpe10_raw)
                cpe10 = (vals[0], vals[1]) if len(vals) >= 2 else (vals[0], vals[0])
            if np.isscalar(cpe1_raw) or np.asarray(cpe1_raw).ndim == 0:
                v = float(cpe1_raw)
                cpe1 = (v, v)
            else:
                vals = tuple(float(x) for x in cpe1_raw)
                cpe1 = (vals[0], vals[1]) if len(vals) >= 2 else (vals[0], vals[0])

            target.zone_children_by_direction[dir_key].append({
                "id": f"{target.unique_id}:{dir_key}:{len(target.zone_children_by_direction[dir_key])}",
                "label": str(z.label),
                "kind": str(getattr(z, "kind", "")),
                "coords": [tuple(float(c) for c in xyz) for xyz in coords],
                "cpe10": cpe10,
                "cpe1": cpe1,
                "pitch": float(getattr(z, "pitch", 0.0)),
                "table_type": str(getattr(z, "table_type", "")),
                "wind_relation": "",
                "skip_transfer": False,
                "label_override": None,
                "cpe10_override": None,
                "cpe1_override": None,
            })

    # ------------------------------------------------------------------
    def _draw_zone_summary(self):
        total = 0
        for p in self.scene.polygons.values():
            if getattr(p, "is_temporary", False):
                continue
            for zones in (p.zone_children_by_direction or {}).values():
                total += len(zones)
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.8, 0.9, 1.0),
            f"Toplam zone: {total}",
        )