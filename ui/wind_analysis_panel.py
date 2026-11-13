"""Rüzgar analiz paneli — surface seç + yön + zone oluştur ve sonuçları görselleştir."""
from __future__ import annotations

import numpy as np
from imgui_bundle import imgui

from core.units import Dimension, UnitSystem, convert_value
from data.enums import PolygonType
from logging_config import CadLogger
from ui.base_panel import BasePanel
from tools.wind_scene_adapter import WindSceneAdapter
from domain.definition import WindDirectionResult

logger = CadLogger.get(__name__)


class WindAnalysisPanel(BasePanel):

    def __init__(self):
        super().__init__(
            title="Rüzgar Analizi",
            width=580,
            height=640,
            pos_first_use=(200, 100),
        )
        self.app = None
        self.project = None
        self.selected_dir_key = None
        self.show_zones_toggle = True

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.project = self._project()

    def open(self):
        super().open() if hasattr(super(), "open") else setattr(self, "visible", True)
        self._apply_wind_view_mode(True)

    def close(self):
        super().close() if hasattr(super(), "close") else setattr(self, "visible", False)
        self._apply_wind_view_mode(False)

    def _get_engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    def _apply_wind_view_mode(self, active: bool):
        if not self.project:
            return
        eng = self._get_engine()

        if active:
            if eng:
                if eng.renderer:
                    eng.renderer.set_show("frame", False)
                    eng.renderer.set_show("node", False)
                    eng.renderer.set_show("link", False)
                    eng.renderer.set_show("area", False)
                if eng.presentation_renderer:
                    eng.presentation_renderer.show["polygon"] = True
                    eng.presentation_renderer.show["zones"] = self.show_zones_toggle
                eng.update_geo(self.project)
        else:
            if eng:
                if eng.renderer:
                    eng.renderer.set_show("frame", True)
                    eng.renderer.set_show("node", True)
                    eng.renderer.set_show("link", True)
                    eng.renderer.set_show("area", True)
                    eng.renderer.set_show("polygon", True)
                if eng.presentation_renderer:
                    eng.presentation_renderer.show["zones"] = False
                eng.active_wind_vector = None
                eng.update_geo(self.project)

    def _draw_topbar(self):
        eng = self._get_engine()
        
        if eng and eng.presentation_renderer:
            current_state = eng.presentation_renderer.show.get("zones", False)
        else:
            current_state = self.show_zones_toggle

        changed, new_val = imgui.checkbox("Show Zones", current_state)
        if changed:
            self.show_zones_toggle = new_val
            if eng and eng.presentation_renderer:
                eng.presentation_renderer.show["zones"] = new_val
                eng.update_geo(self.project)

        imgui.same_line()
        if imgui.button("Analiz Et"):
            try:
                self._run_analysis_all()
            except Exception:
                logger.exception("[Wind] Analiz hatası")

        imgui.same_line()
        if imgui.button("Reset"):
            try:
                self._reset_analysis()
            except Exception:
                logger.exception("[Wind] Reset hatası")

        imgui.same_line()
        wind = self._wind_state()
        directions = wind.get("directions", {})
        if directions:
            target_key = self.selected_dir_key if self.selected_dir_key in directions else list(directions.keys())[0]
            dir_rec = directions.get(target_key)
            if dir_rec and imgui.button("📄 Rapor"):
                self._open_wind_report_table(dir_rec, target_key)

        imgui.same_line()
        changed, val = imgui.slider_float("Renk Hassasiyeti", getattr(self, "_color_gain", 1.0), 0.5, 3.0, "%.2f")
        if changed:
            self._color_gain = val
            if eng and eng.presentation_renderer:
                eng.presentation_renderer.color_gain = val
                eng.update_geo(self.project)

    def draw_content(self):
        if self.project is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje bağlı değil.",
            )
            return

        self._draw_topbar()
        imgui.separator()
        self._draw_surface_selection()
        imgui.separator()
        self._draw_directions()
        imgui.separator()
        self._draw_zone_editor_table()

    def _reset_analysis(self):
        if not self.project:
            return
        for p in self.project.polygons.values():
            p.zone_children_by_direction = {}
            p.show_zones_direction = None
            p.mark_dirty()
        wind = self._wind_state()
        wind["directions"] = {}
        self.selected_dir_key = None
        eng = self._get_engine()
        if eng:
            eng.update_geo(self.project)
        logger.debug("[Wind] Rüzgar analizi resetlendi.")

    def _draw_surface_selection(self):
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

    def _draw_directions(self):
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

        eng = self._get_engine()

        to_remove = None
        for key, rec in sorted(directions.items()):
            vec = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            is_selected = (self.selected_dir_key == key)
            
            label_btn = f"Yön {key} : ({vec[0]:.1f}, {vec[1]:.1f}, {vec[2]:.1f})##dir_{key}"
            if imgui.selectable(label_btn, is_selected)[0]:
                self.selected_dir_key = key
                if eng:
                    eng.active_wind_vector = vec
                    
                for p in self.project.polygons.values():
                    p.show_zones_direction = key
                    p.mark_dirty()
                if eng and hasattr(eng, "update_geo"):
                    eng.update_geo(self.project)

            imgui.same_line()
            if imgui.button(f"Remove##rem_{key}"):
                to_remove = key

        if to_remove is not None:
            self._remove_direction(to_remove)

        if imgui.button("+ Yeni Yön", imgui.ImVec2(120, 0)):
            self._add_default_direction()

    def _remove_direction(self, key: str):
        wind = self._wind_state()
        directions = wind.get("directions", {})
        if key in directions:
            del directions[key]
        for p in self.project.polygons.values():
            if p.zone_children_by_direction and key in p.zone_children_by_direction:
                p.zone_children_by_direction.pop(key, None)
            if p.show_zones_direction == key:
                p.show_zones_direction = None
            p.mark_dirty()
        if self.selected_dir_key == key:
            remaining = list(directions.keys())
            self.selected_dir_key = remaining[0] if remaining else None
        eng = self._get_engine()
        if eng:
            eng.update_geo(self.project)
        logger.debug("[Wind] Yön kaldırıldı: %s", key)

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
        logger.debug("[Wind] Yön eklendi: %02d = %s", n, vec)

    def _run_analysis_all(self):
        surfaces = [
            p for p in self.project.polygons.values()
            if getattr(p, "_wind_selected", False)
        ]
        if not surfaces:
            logger.debug("[Wind] Surface seçilmedi.")
            return

        wind = self._wind_state()
        directions = wind.get("directions", {})
        if not directions:
            logger.debug("[Wind] Yön yok.")
            return

        for dir_key, rec in directions.items():
            w_dir = getattr(rec, "w_dir", (1.0, 0.0, 0.0))
            if isinstance(w_dir, np.ndarray):
                vec = tuple(float(x) for x in w_dir)
            elif isinstance(w_dir, (list, tuple)):
                vec = tuple(float(x) for x in w_dir)
            else:
                vec = (1.0, 0.0, 0.0)

            try:
                points, polygons, wind_config = (
                    WindSceneAdapter.build_inputs_for_polygons(
                        self.project, surfaces,
                    )
                )
                zones, engine_data = WindSceneAdapter.analyze(
                    points, polygons, wind_config, vec,
                )
            except Exception:
                logger.exception("[Wind] Yön %s analiz hatası", dir_key)
                continue

            self._assign_zones_to_polygons(zones, surfaces, dir_key)
            WindSceneAdapter.store_zones(self.project, dir_key, zones, engine_data, vec)
            rec.engine = type("EngineMock", (), engine_data)()
            logger.debug("[Wind] Yön %s: %d zone üretildi.", dir_key, len(zones))

        if directions:
            if not self.selected_dir_key or self.selected_dir_key not in directions:
                self.selected_dir_key = list(directions.keys())[0]
            
            for p in surfaces:
                p.show_zones_direction = self.selected_dir_key
                p.mark_dirty()

            eng = self._get_engine()
            if eng:
                if eng.presentation_renderer:
                    eng.presentation_renderer.show["zones"] = self.show_zones_toggle
                eng.update_geo(self.project)

    def _assign_zones_to_polygons(self, zones, surfaces, dir_key):
        unit_system = self.project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)
        meters_to_project = float(
            convert_value(
                Dimension.LENGTH, 1.0, UnitSystem.N_M, unit_system,
            )
        )

        by_name = {
            (p.label or f"Polygon_{p.unique_id}"): p for p in surfaces
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
                "coords": [
                    tuple(float(c) * meters_to_project for c in xyz)
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

    def _draw_zone_editor_table(self):
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
                        p.mark_dirty()

                    imgui.table_set_column_index(5)
                    changed_max, new_c10_max = imgui.input_float(f"##c10max_{p.unique_id}_{idx}", c10_max, 0.0, 0.0, "%.3f")
                    if changed_max:
                        z["cpe10_override"] = (c10_min, new_c10_max)
                        p.mark_dirty()

                    imgui.table_set_column_index(6)
                    changed_c1min, new_c1_min = imgui.input_float(f"##c1min_{p.unique_id}_{idx}", c1_min, 0.0, 0.0, "%.3f")
                    if changed_c1min:
                        z["cpe1_override"] = (new_c1_min, c1_max)
                        p.mark_dirty()

                    imgui.table_set_column_index(7)
                    changed_c1max, new_c1_max = imgui.input_float(f"##c1max_{p.unique_id}_{idx}", c1_max, 0.0, 0.0, "%.3f")
                    if changed_c1max:
                        z["cpe1_override"] = (c1_min, new_c1_max)
                        p.mark_dirty()

                    imgui.table_set_column_index(8)
                    if z.get("cpe10_override") or z.get("cpe1_override"):
                        if imgui.button(f"Sıfırla##reset_{p.unique_id}_{idx}"):
                            z["cpe10_override"] = None
                            z["cpe1_override"] = None
                            p.mark_dirty()
                    else:
                        imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "Orijinal")

            imgui.end_table()

    def _open_wind_report_table(self, dir_rec, target_key: str):
        try:
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
                logger.debug("[WindPanel] Rapor oluşturulacak aktif zone bulunamadı.")
                return

            engine = getattr(dir_rec, "engine", None)
            if engine is None:
                from structload.windcalc.windengine import WindEngine
                polygons_dict = {str(p.unique_id): [str(v) for v in p.vertices or p.nodes] for p in self.project.polygons.values()}
                
                w_dir_val = getattr(dir_rec, "w_dir", (1.0, 0.0, 0.0))
                if isinstance(w_dir_val, np.ndarray):
                    w_dir_val = tuple(float(x) for x in w_dir_val)

                engine = WindEngine(
                    points={},
                    polygons=polygons_dict,
                    w_dir=w_dir_val
                )

            report_df = create_cpe_summary_df(zones_list, engine)
            logger.debug("[WindPanel] Rapor tablosu başarıyla oluşturuldu.")

            if self.app and hasattr(self.app, "show_popup_report"):
                self.app.show_popup_report(report_df)
            else:
                logger.debug(f"[WindPanel] Rapor Başlığı: {report_df.custom_title}, Satır Sayısı: {len(report_df)}")

        except Exception:
            logger.exception("[WindPanel] Rapor tablosu oluşturulurken hata oluştu")