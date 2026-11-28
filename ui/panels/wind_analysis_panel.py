# ui/panels/wind_analysis_panel.py
from __future__ import annotations

import copy
from typing import Any

import numpy as np
from imgui_bundle import imgui
import app.commands as cmd
# from app.commands.impl import RefreshGeometry, ToggleRenderFlag, UpdateElementFields
from core.units import Dimension, UnitSystem, convert_value
from data.enums import PolygonType
from domain.definition import WindDirectionResult
from logging_config import CadLogger
from tools.wind_scene_adapter import WindSceneAdapter
from ui.base.panel_base import Category, PanelBase

logger = CadLogger.get(__name__)

_WIND_MATH_KEYS = ("frame", "node", "link", "area")


class WindAnalysisPanel(PanelBase):
    __abstract__ = False
    panel_name = "wind"
    title = "Rüzgar Analizi"
    category = Category.LOADS
    quick = True
    context = ("project", "engine")
    uses_draft = False
    show_apply_bar = True
    preview_flags = {
        # "polygon": True,
        # "zones": True,
        # "loads": False,
        # "grid": False,
        # "lines": False,
    }

    width = 580
    height = 640
    pos_first_use = (200.0, 100.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.project = None
        self.selected_dir_key: str | None = None
        self._math_snapshot: dict[str, bool] | None = None
        self._committed_snapshot: dict[Any, dict] | None = None

    def has_pending_changes(self) -> bool:
        proj = self._project()
        if proj is None or self._committed_snapshot is None:
            return False
        for uid, p in proj.polygons.items():
            old = self._committed_snapshot.get(uid, {})
            cur = p.zone_children_by_direction or {}
            if old != cur:
                return True
        return False

    def _snapshot_wind_data(self) -> dict[Any, dict]:
        proj = self._project()
        if proj is None:
            return {}
        return {
            uid: copy.deepcopy(p.zone_children_by_direction or {})
            for uid, p in proj.polygons.items()
        }

    def on_apply_action(self) -> None:
        self._committed_snapshot = self._snapshot_wind_data()
        proj = self._project()
        if proj is not None and proj.math_model is not None:
            proj.math_model.mark_dirty()
        self.app.put_command(cmd.RefreshGeometry())

    def on_reset_action(self) -> None:
        self._reset_analysis()
        self._committed_snapshot = self._snapshot_wind_data()

    def set_context(self, ctx: dict) -> None:
        super().set_context(ctx)
        self.project = self._project()
        self._committed_snapshot = self._snapshot_wind_data()

    def open(self, **kw) -> None:
        super().open(**kw)
        # self._apply_math_preview(True)
        # self._set_zones_visible(True)
        self._committed_snapshot = self._snapshot_wind_data()

    def close(self) -> None:
        # self._apply_math_preview(False)
        # self._set_zones_visible(False)
        super().close()

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _get_engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    # def _enqueue(self, cmd) -> None:
    #     queue = getattr(self.app, "command_queue", None) if self.app else None
    #     if queue is not None:
    #         queue.put(cmd)

    # def _set_zones_visible(self, visible: bool) -> None:
        
    #     self.app.put_command(cmd.ToggleZones(enabled=None))
    #     # self._enqueue(ToggleRenderFlag(flag="zones", value=bool(visible)))

    def _apply_math_preview(self, active: bool) -> None:
        eng = self._get_engine()
        if eng is None:
            return
        mmr = eng.renderer.math_model_renderer if eng.renderer else None
        if mmr is None or not hasattr(mmr, "set_show"):
            return
        if active:
            self._math_snapshot = dict(mmr.get_show()) if hasattr(mmr, "get_show") else None
            for k in _WIND_MATH_KEYS:
                mmr.set_show(k, False)
        else:
            if self._math_snapshot:
                for k, v in self._math_snapshot.items():
                    mmr.set_show(k, v)
            self._math_snapshot = None

    def _apply_polygon_direction(self, poly, dir_key: str | None) -> None:
        self.app.put_command(cmd.UpdateElementFields(
                        element_uid=poly.unique_id,
                        changes={"show_zones_direction": dir_key},
                    ))
        

    def draw_content(self) -> None:
        if self.project is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje bağlı değil.",
            )
            return

        self._draw_surface_selection()
        imgui.separator()
        self._draw_directions()
        imgui.separator()
        self._draw_zone_editor_table()

    def _reset_analysis(self) -> None:
        if not self.project:
            return
        for p in self.project.polygons.values():
            p.zone_children_by_direction = {}
            self._apply_polygon_direction(p, None)
        wind = self._wind_state()
        wind["directions"] = {}
        self.selected_dir_key = None
        self._set_zones_visible(False)
        self.app.put_command(cmd.RefreshGeometry())

    def _draw_surface_selection(self) -> None:
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Surface Polygon'lar",
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            "(LOAD_AREA / SURFACE — yük analizine girecek)",
        )

        candidates = [
            p for p in self.project.polygons.values()
            if not getattr(p, "is_temporary", False)
            and p.poly_type in (
                PolygonType.LOAD_AREA,
                PolygonType.SURFACE,
            )
        ]

        if not candidates:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Uygun polygon yok. Polygon çiz + tipi SURFACE/LOAD_AREA seç.",
            )
            return

        imgui.begin_child(
            "##surface_list", imgui.ImVec2(0, 100),
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

    def _draw_directions(self) -> None:
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Rüzgar Yönleri ve Vektör Seçimi",
        )

        wind = self._wind_state()
        directions = wind.get("directions", {}) or {}

        if not directions:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Yön yok. '+ Yeni Yön' ekle.",
            )

        to_remove = None
        for key, rec in sorted(directions.items()):
            if imgui.button(f"Remove##rem_{key}"):
                to_remove = key
            imgui.same_line()
            vec = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            is_selected = (self.selected_dir_key == key)

            label_btn = f"Yön {key} : ({vec[0]:.1f}, {vec[1]:.1f}, {vec[2]:.1f})##dir_{key}"
            if imgui.selectable(label_btn, is_selected)[0]:
                self.selected_dir_key = key
                # self._set_zones_visible(True)
                for p in self.project.polygons.values():
                    self._apply_polygon_direction(p, key)
                # self._enqueue(RefreshGeometry())
                self.app.put_command(cmd.RefreshGeometry())
                self.app.put_command(cmd.ToggleZones(enabled=True))


        if to_remove is not None:
            self._remove_direction(to_remove)

        if imgui.button("+ Yeni Yön", imgui.ImVec2(120, 0)):
            self._add_default_direction()

        imgui.same_line()

        selected_surfaces = [
            p for p in self.project.polygons.values()
            if getattr(p, "_wind_selected", False)
        ]
        can_analyze = bool(directions) and bool(selected_surfaces)
        if not can_analyze:
            imgui.begin_disabled()
        if imgui.button("Analiz Et", imgui.ImVec2(120, 0)):
            self._run_analysis_all()
        if not can_analyze:
            imgui.end_disabled()

        imgui.same_line()
        if not directions:
            imgui.begin_disabled()
        if imgui.button("Analizi Temizle", imgui.ImVec2(140, 0)):
            self._reset_analysis()
        imgui.same_line()
        if imgui.button("Hide##sp_hide", imgui.ImVec2(80, 0)):
            self.app.put_command(cmd.ToggleZones(enabled=None))
        if not directions:
            imgui.end_disabled()

    def _remove_direction(self, key: str) -> None:
        wind = self._wind_state()
        directions = wind.get("directions", {})
        if key in directions:
            del directions[key]
        for p in self.project.polygons.values():
            if p.zone_children_by_direction and key in p.zone_children_by_direction:
                p.zone_children_by_direction.pop(key, None)
            next_dir = key if p.show_zones_direction != key else None
            if p.show_zones_direction == key:
                self._apply_polygon_direction(p, next_dir)
        if self.selected_dir_key == key:
            remaining = list(directions.keys())
            self.selected_dir_key = remaining[0] if remaining else None
        self.app.put_command(cmd.RefreshGeometry())

    def _wind_state(self) -> dict:
        analysis = self.project.analysis
        wind = analysis.wind
        if not isinstance(wind, dict):
            wind = {}
            analysis.wind = wind
        if "directions" not in wind or not isinstance(wind["directions"], dict):
            wind["directions"] = {}
        return wind

    def _add_default_direction(self) -> None:
        wind = self._wind_state()
        dirs = wind["directions"]
        n = 1
        while f"{n:02d}" in dirs:
            n += 1
        presets = [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
        ]
        vec = presets[(n - 1) % len(presets)]
        dirs[f"{n:02d}"] = WindDirectionResult(w_dir=vec)

    def _run_analysis_all(self) -> None:
        surfaces = [
            p for p in self.project.polygons.values()
            if getattr(p, "_wind_selected", False)
        ]
        if not surfaces:
            return

        wind = self._wind_state()
        directions = wind.get("directions", {})
        if not directions:
            return

        for dir_key, rec in directions.items():
            w_dir = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            if isinstance(w_dir, np.ndarray):
                vec = tuple(float(x) for x in w_dir)
            elif isinstance(w_dir, (list, tuple)):
                vec = tuple(float(x) for x in w_dir)
            else:
                vec = (1.0, 0.0, 0.0)

            points, polygons, wind_config = WindSceneAdapter.build_inputs_for_polygons(
                self.project, surfaces,
            )
            zones, engine_data = WindSceneAdapter.analyze(
                points, polygons, wind_config, vec,
            )
            self._assign_zones_to_polygons(zones, surfaces, dir_key)
            WindSceneAdapter.store_zones(self.project, dir_key, zones, engine_data, vec)
            rec.engine = type("EngineMock", (), engine_data)()

        if not self.selected_dir_key or self.selected_dir_key not in directions:
            self.selected_dir_key = list(directions.keys())[0]

        self._set_zones_visible(True)
        for p in surfaces:
            self._apply_polygon_direction(p, self.selected_dir_key)
        self.app.put_command(cmd.RefreshGeometry())

    def _assign_zones_to_polygons(self, zones, surfaces, dir_key: str) -> None:
        unit_system = self.project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)
        wind_to_project = float(
            convert_value(
                Dimension.LENGTH, 1.0, WindSceneAdapter.WIND_UNIT_SYSTEM, unit_system,
            )
        )

        by_name = {
            (p.label or f"POLYGON_{p.unique_id}"): p for p in surfaces
        }

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
                v10 = float(cpe10_raw)
                cpe10 = (v10, v10)
            else:
                vals10 = tuple(float(x) for x in cpe10_raw)
                cpe10 = (vals10[0], vals10[1]) if len(vals10) >= 2 else (vals10[0], vals10[0])

            if np.isscalar(cpe1_raw) or np.asarray(cpe1_raw).ndim == 0:
                v1 = float(cpe1_raw)
                cpe1 = (v1, v1)
            else:
                vals1 = tuple(float(x) for x in cpe1_raw)
                cpe1 = (vals1[0], vals1[1]) if len(vals1) >= 2 else (vals1[0], vals1[0])

            target.zone_children_by_direction[dir_key].append({
                "id": f"{target.unique_id}:{dir_key}:{len(target.zone_children_by_direction[dir_key])}",
                "label": str(z.label),
                "kind": str(getattr(z, "kind", "")),
                "coords": [
                    tuple(float(c) * wind_to_project for c in xyz)
                    for xyz in coords
                ],
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

    def _draw_zone_editor_table(self) -> None:
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Zone ve Basınç Katsayıları (Cpe & Tasarım Yükleri) Düzenleyicisi",
        )

        if not self.selected_dir_key:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), "Lütfen yukarıdan bir Rüzgar Yönü seçin.")
            return

        wind_state = self._wind_state()
        directions = wind_state.get("directions", {})
        dir_rec = directions.get(self.selected_dir_key)

        if not dir_rec:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), f"Yön {self.selected_dir_key} için analiz verisi bulunamadı.")
            return

        imgui.spacing()

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.scroll_y
        )

        if imgui.begin_table("##zone_edit_table", 9, flags, imgui.ImVec2(0, 260)):
            imgui.table_setup_column("Bölge", imgui.TableColumnFlags_.width_fixed, 50)
            imgui.table_setup_column("Yüzey", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("Tip", imgui.TableColumnFlags_.width_fixed, 70)
            imgui.table_setup_column("Eğim (°)", imgui.TableColumnFlags_.width_fixed, 60)
            imgui.table_setup_column("Cpe,10 Min", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("Cpe,10 Max", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("Cpe,1 Min", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("Cpe,1 Max", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("İşlemler", imgui.TableColumnFlags_.width_stretch, 100)
            imgui.table_headers_row()

            for p_name, p in self.project.polygons.items():
                if getattr(p, "is_temporary", False):
                    continue
                zones = (p.zone_children_by_direction or {}).get(self.selected_dir_key, [])
                for idx, z in enumerate(zones):
                    imgui.table_next_row()

                    imgui.table_set_column_index(0)
                    imgui.text(str(z.get("label", "")))

                    imgui.table_set_column_index(1)
                    imgui.text(str(p.label or p_name))

                    imgui.table_set_column_index(2)
                    imgui.text(str(z.get("table_type", "-")))

                    imgui.table_set_column_index(3)
                    pitch = z.get("pitch", 0.0)
                    imgui.text(f"{pitch:.1f}°")

                    cpe10 = z.get("cpe10_override") or z.get("cpe10", (0.0, 0.0))
                    cpe1 = z.get("cpe1_override") or z.get("cpe1", (0.0, 0.0))

                    c10_min = float(cpe10[0] if isinstance(cpe10, (list, tuple)) else cpe10)
                    c10_max = float(cpe10[1] if isinstance(cpe10, (list, tuple)) and len(cpe10) > 1 else c10_min)

                    c1_min = float(cpe1[0] if isinstance(cpe1, (list, tuple)) else cpe1)
                    c1_max = float(cpe1[1] if isinstance(cpe1, (list, tuple)) and len(cpe1) > 1 else c1_min)

                    imgui.table_set_column_index(4)
                    changed_min, new_c10_min = imgui.input_float(f"##c10min_{p.unique_id}_{idx}", c10_min, 0.0, 0.0, "%.3f")
                    if changed_min:
                        z["cpe10_override"] = (new_c10_min, c10_max)
                        self.app.put_command(cmd.RefreshGeometry())

                    imgui.table_set_column_index(5)
                    changed_max, new_c10_max = imgui.input_float(f"##c10max_{p.unique_id}_{idx}", c10_max, 0.0, 0.0, "%.3f")
                    if changed_max:
                        z["cpe10_override"] = (c10_min, new_c10_max)
                        self.app.put_command(cmd.RefreshGeometry())

                    imgui.table_set_column_index(6)
                    changed_c1min, new_c1_min = imgui.input_float(f"##c1min_{p.unique_id}_{idx}", c1_min, 0.0, 0.0, "%.3f")
                    if changed_c1min:
                        z["cpe1_override"] = (new_c1_min, c1_max)
                        self.app.put_command(cmd.RefreshGeometry())

                    imgui.table_set_column_index(7)
                    changed_c1max, new_c1_max = imgui.input_float(f"##c1max_{p.unique_id}_{idx}", c1_max, 0.0, 0.0, "%.3f")
                    if changed_c1max:
                        z["cpe1_override"] = (c1_min, new_c1_max)
                        self.app.put_command(cmd.RefreshGeometry())

                    imgui.table_set_column_index(8)
                    if z.get("cpe10_override") or z.get("cpe1_override"):
                        if imgui.button(f"Sıfırla##reset_{p.unique_id}_{idx}"):
                            z["cpe10_override"] = None
                            z["cpe1_override"] = None
                            self.app.put_command(cmd.RefreshGeometry())
                    else:
                        imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "Orijinal")

            imgui.end_table()

    def _open_wind_report_table(self, dir_rec, target_key: str) -> None:
        from structload.windcalc.wind_results import create_cpe_summary_df

        zones_list = []
        for p in self.project.polygons.values():
            if getattr(p, "is_temporary", False):
                continue
            for z in (p.zone_children_by_direction or {}).get(target_key, []):
                cpe10 = z.get("cpe10_override") or z.get("cpe10", (0.0, 0.0))
                cpe1 = z.get("cpe1_override") or z.get("cpe1", (0.0, 0.0))

                class ZoneAdapter:
                    def __init__(self, data, poly):
                        self.label = data.get("label", "")
                        self.surface = poly.label or f"Polygon_{poly.unique_id}"
                        self.table_type = data.get("table_type", "")
                        self.table_type_dir = 0.0
                        self.pitch = data.get("pitch", 0.0)
                        self.coords = data.get("coords", [])
                        self.cpe10 = cpe10
                        self.cpe1 = cpe1

                zones_list.append(ZoneAdapter(z, p))

        if not zones_list:
            return

        engine = getattr(dir_rec, "engine", None)
        if engine is None:
            from structload.windcalc.windengine import WindEngine
            polygons_dict = {
                str(p.unique_id): [str(v) for v in p.vertices or p.nodes]
                for p in self.project.polygons.values()
            }
            w_dir_val = getattr(dir_rec, "w_dir", (1.0, 0.0, 0.0))
            if isinstance(w_dir_val, np.ndarray):
                w_dir_val = tuple(float(x) for x in w_dir_val)
            engine = WindEngine(
                points={},
                polygons=polygons_dict,
                w_dir=w_dir_val,
            )

        report_df = create_cpe_summary_df(zones_list, engine)
        if self.app and hasattr(self.app, "show_popup_report"):
            self.app.show_popup_report(report_df)
        else:
            logger.info("Rapor başlığı: %s, satır: %d", report_df.custom_title, len(report_df))