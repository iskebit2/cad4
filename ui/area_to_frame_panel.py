"""User-controlled polygon-to-frame area-load transfer panel."""
from __future__ import annotations
from copy import deepcopy

import numpy as np
from imgui_bundle import imgui

from core.units import Dimension, UnitSystem, convert_value
from data.enums import DistType, LoadDirection, PolygonType
from domain.definition import AreaUniformLoad, LoadPattern
from domain.element import Frame, Node, Polygon
from tools.polygon_load_transfer import  build_polygon_frame_loads
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class AreaToFramePanel(BasePanel):
    def __init__(self, on_transfer_complete=None):
        super().__init__(
            title="Area to Frame",
            width=520,
            height=560,
            pos_first_use=(420, 140),
        )
        self.project = None
        self.scene = None
        self.selection_polygons: list[Polygon] = []
        self.on_transfer_complete = on_transfer_complete
        self._selected_polygon_id: int | None = None
        self._status = ""
        self._selected_wind_zone: tuple[str, int] | None = None
        self._wind_cpe_index = 0
        self._cpi_positive = 0.2
        self._cpi_negative = -0.3

        self._step: float = 200.0
        self._step_initialized: bool = False
        self._n_bins: int = 12

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.project = ctx.get("project")
        self.scene = ctx.get("scene")

        if self.project is not None and not self._step_initialized:
            self._step = convert_value(
                Dimension.LENGTH, 200.0, UnitSystem.N_MM,
                self.project.unit_system,
            )
            self._step_initialized = True

        self.selection_polygons = [
            item for item in (ctx.get("selection_polygons") or [])
            if isinstance(item, Polygon)
        ]
        polygons = self._polygons()
        available_ids = {int(item.unique_id) for item in polygons}
        selected_ids = {
            int(item.unique_id) for item in self.selection_polygons
        }
        if self._selected_polygon_id not in available_ids:
            self._selected_polygon_id = (
                next(iter(selected_ids & available_ids), None)
                or (int(polygons[0].unique_id) if polygons else None)
            )

    def _polygons(self) -> list[Polygon]:
        if self.scene is None:
            return []
        return sorted(
            self.scene.polygons.values(),
            key=lambda polygon: (
                polygon.label or "", int(polygon.unique_id),
            ),
        )

    def _selected_polygon(self) -> Polygon | None:
        return next(
            (
                polygon for polygon in self._polygons()
                if int(polygon.unique_id) == self._selected_polygon_id
            ),
            None,
        )

    def draw_content(self):
        if self.project is None or self.scene is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje veya sahne bağlı değil.",
            )
            return

        polygons = self._polygons()
        if not polygons:
            imgui.text("Sahnede aktarım yapılabilecek polygon yok.")
            return

        # --- Polygon seçimi ---
        selected = self._selected_polygon()
        if selected is None:
            selected = polygons[0]
            self._selected_polygon_id = int(selected.unique_id)

        current_label = self._polygon_label(selected)
        if imgui.begin_combo("Polygon", current_label):
            for polygon in polygons:
                is_selected = int(polygon.unique_id) == self._selected_polygon_id
                if imgui.selectable(self._polygon_label(polygon), is_selected)[1]:
                    self._selected_polygon_id = int(polygon.unique_id)
                    selected = polygon
            imgui.end_combo()

        # --- Polygon yükleri ---
        self._draw_polygon_loads(selected)
        imgui.separator()

        # --- Frame assoc ---
        self._draw_frame_associations(selected)
        imgui.separator()

        # --- Tributary dağıtımı ---
        distribution_labels = ["One way (U1)", "One way (U2)", "Two way"]
        distribution_values = ["one_way_u1", "one_way_u2", "two_way"]
        current_dist_idx = self._distribution_index(selected.transfer_dist_type)
        changed, new_dist_idx = imgui.combo(
            "Tributary dağıtımı",
            current_dist_idx,
            distribution_labels,
        )
        if changed:
            selected.transfer_dist_type = distribution_values[new_dist_idx]
            selected.mark_dirty()

        # --- Rüzgar zone aktarımı ---
        self._draw_wind_zone_transfers(selected)
        imgui.separator()

        # --- Grid ayarları (proje biriminde) ---
        self._draw_grid_settings()
        imgui.separator()

        # --- Durum + Aktar ---
        if self._status:
            imgui.text_wrapped(self._status)

        if selected.assigned_loads and imgui.button(
            "Seçili frame'lere aktar##area_to_frame",
            imgui.ImVec2(-1, 0),
        ):
            try:
                self._transfer(selected)
            except (TypeError, ValueError) as error:
                self._status = str(error)
                logger.warning("[AreaToFrame] %s", error)
            except Exception:
                self._status = "Alan yükü aktarımı başarısız oldu; log'a bakın."
                logger.exception("[AreaToFrame] Aktarım başarısız.")


    def _draw_grid_settings(self) -> None:
        """Grid adımı ve bin sayısı — proje biriminde."""
        length_unit = self.project.unit_system.length_unit

        # 1 metre'nin proje birimindeki karşılığı
        one_meter = convert_value(
            Dimension.LENGTH, 1.0, UnitSystem.N_M,
            self.project.unit_system,
        )
        step_min = 0.05 * one_meter   # 5 cm
        step_max = 2.00 * one_meter   # 2 m

        # Grid adımı
        imgui.text(f"Grid adımı ({length_unit})")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._step = imgui.input_float(
            "##step", self._step,
            0.01 * one_meter, 0.1 * one_meter,
        )
        imgui.pop_item_width()
        self._step = max(step_min, min(step_max, self._step))

        # Bin sayısı
        imgui.text("Bin sayısı")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._n_bins = imgui.input_int("##n_bins", self._n_bins)
        imgui.pop_item_width()
        self._n_bins = max(3, min(50, self._n_bins))

    def _draw_polygon_loads(self, polygon: Polygon):
        transfers = self.project.loads.area_load_transfers_for_polygon(
            int(polygon.unique_id),
        )
        imgui.text(
            f"Atanmış alan yükü: {len(getattr(polygon, 'assigned_loads', ())) }"
        )
        for load in polygon.assigned_loads:
            unit = self._area_load_unit()   # "kN/m²" veya "N/mm²"
            imgui.bullet_text(f"{load.pattern_name} | {load.value:.3f} {unit}")

        wind_transfers = [
            item for item in transfers
            if item.get("source_type") == "wind_zone"
        ]
        for item in wind_transfers:
            imgui.bullet_text(
                f"Rüzgar {item.get('direction_key')} / "
                f"{item.get('zone_label')} / {item.get('cpe_kind')}"
            )
        if not polygon.assigned_loads and not wind_transfers:
            imgui.text_disabled(
                "Bu polygon üzerinde Load Manager'a aktarılmış yük yok."
            )
        if transfers:
            transferred = sorted({
                int(frame_id)
                for item in transfers
                for frame_id in item.get("transferred_frame_ids", ())
            })
            if transferred:
                imgui.text_disabled(
                    "Son aktarım frame ID'leri: "
                    + ", ".join(str(item) for item in transferred)
                )

    def _draw_frame_associations(self, polygon: Polygon):
        """Seçili frame'leri polygona assoc et."""
        
        # Sahnede seçili frame'ler
        selected_frames = self._selected_frames_from_scene()
        
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            "Aktarım Hedefi",
        )
        
        # Sahnede kaç frame seçili
        if selected_frames:
            ids_str = ", ".join(str(f.unique_id) for f in selected_frames[:8])
            if len(selected_frames) > 8:
                ids_str += f" ... (+{len(selected_frames) - 8})"
            imgui.text(f"Sahnede seçili: {len(selected_frames)} frame")
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
                f"  ID: {ids_str}",
            )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Sahnede frame seçili değil.",
            )
        
        # Ata butonu
        can_assign = bool(selected_frames)
        if not can_assign:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0),
            )
        
        if imgui.button(
            "Seçili frame'leri polygona ata##af_assign",
            imgui.ImVec2(-1, 0),
        ) and can_assign:
            polygon.associated_frame_ids = sorted(
                int(f.unique_id) for f in selected_frames
            )
            polygon.mark_dirty()
            self.scene.mark_dirty()
            self._status = (
                f"{len(polygon.associated_frame_ids)} frame polygona atandı."
            )
            logger.info(
                "[AreaToFrame] %s: %d frame assoc",
                polygon.label, len(polygon.associated_frame_ids),
            )
        
        if not can_assign:
            imgui.pop_style_color(1)
        
        # Mevcut assoc durum
        assoc_count = len(polygon.associated_frame_ids)
        imgui.spacing()
        if assoc_count > 0:
            imgui.text_colored(
                imgui.ImVec4(0.55, 0.85, 0.6, 1.0),
                f"Assoc edilmiş: {assoc_count} frame",
            )
            imgui.same_line()
            if imgui.small_button("Temizle##af_clear"):
                polygon.associated_frame_ids = []
                polygon.mark_dirty()
                self.scene.mark_dirty()
                self._status = "Assoc temizlendi."
        else:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "⚠ Henüz assoc yok — sahne üzerinden frame seçip 'ata' butonuna basın.",
            )


    def _selected_frames_from_scene(self) -> list[Frame]:
        """Sahnede seçili frame'leri döndür."""
        if self.scene is None:
            return []
        try:
            return [
                el for el in self.scene.get_selected()
                if isinstance(el, Frame)
            ]
        except Exception:
            return []

    def _wind_zone_entries(self, polygon: Polygon):
        source_refs = {
            f"POLYGON_{int(polygon.unique_id)}",
            f"AREA_{int(polygon.unique_id)}",
        }
        entries = []
        for direction_key, zones in self.project.loads.wind_zones.items():
            for index, zone in enumerate(zones):
                if str(getattr(zone, "surface", "")) in source_refs:
                    entries.append((str(direction_key), index, zone))
        return entries

    def _draw_wind_zone_transfers(self, polygon: Polygon):
        entries = self._wind_zone_entries(polygon)
        imgui.text("Rüzgar analiz bölgeleri")
        if not entries:
            imgui.text_disabled(
                "Bu polygon için Load Manager'da rüzgar bölgesi yok."
            )
            return

        entry_keys = [(key, index) for key, index, _ in entries]
        if self._selected_wind_zone not in entry_keys:
            self._selected_wind_zone = entry_keys[0]
        selected_entry = next(
            item for item in entries
            if (item[0], item[1]) == self._selected_wind_zone
        )
        direction_key, zone_index, zone = selected_entry
        label = f"{direction_key} | {zone.label} ({zone_index + 1})"
        if imgui.begin_combo("Wind zone", label):
            for key, index, item in entries:
                is_selected = (key, index) == self._selected_wind_zone
                item_label = f"{key} | {item.label} ({index + 1})"
                if imgui.selectable(item_label, is_selected)[1]:
                    self._selected_wind_zone = (key, index)
                    direction_key, zone_index, zone = key, index, item
            imgui.end_combo()

        _, self._wind_cpe_index = imgui.combo(
            "Cpe türü", self._wind_cpe_index, ["Cpe10", "Cpe1"],
        )
        _, self._cpi_positive = imgui.input_float(
            "Cpi (+)", self._cpi_positive,
        )
        _, self._cpi_negative = imgui.input_float(
            "Cpi (-)", self._cpi_negative,
        )
        if imgui.button("Rüzgar bölgesini seçili frame'lere aktar"):
            try:
                self._transfer_wind_zone(
                    polygon, direction_key, zone_index, zone,
                )
            except (TypeError, ValueError, KeyError) as error:
                self._status = str(error)
                logger.warning("[AreaToFrame] Wind zone aktarımı: %s", error)
            except Exception:
                self._status = (
                    "Rüzgar bölgesi aktarımı başarısız oldu; log'a bakın."
                )
                logger.exception("[AreaToFrame] Wind zone aktarımı başarısız.")

    def _transfer_wind_zone(
        self, surface: Polygon, direction_key: str, zone_index: int, zone,
    ) -> int:
        if not surface.associated_frame_ids:
            raise ValueError("Önce rüzgar polygon'u için frame hedeflerini seçin.")
        pressure_result = self.project.loads.wind_results.get(direction_key)
        if pressure_result is None:
            directions = getattr(
                getattr(self.project.analysis, "wind", None),
                "directions",
                {},
            )
            pressure_result = directions.get(direction_key)
        if pressure_result is None:
            raise ValueError(
                f"{direction_key} yönü için rüzgar basınç sonucu bulunamadı."
            )

        q_p = float(getattr(pressure_result, "q_p", 0.0))
        if q_p <= 0.0:
            raise ValueError("Rüzgar tepe basıncı sıfır veya geçersiz.")
        wind_direction = getattr(
            pressure_result, "direction",
            getattr(pressure_result, "w_dir", (0.0, 0.0, 0.0)),
        )
        wind_direction = np.asarray(wind_direction, dtype=float)
        if wind_direction.shape != (3,) or not np.isfinite(wind_direction).all():
            raise ValueError("Rüzgar yön vektörü geçersiz.")

        length_factor = convert_value(
            Dimension.LENGTH,
            1.0,
            UnitSystem.N_M,
            self.project.unit_system,
        )
        coords = np.asarray(zone.coords, dtype=float)
        if coords.ndim != 2 or coords.shape[0] < 3 or coords.shape[1] != 3:
            raise ValueError("Rüzgar zone geometrisi geçersiz.")
        zone_nodes = [
            Node(*(coords[index] * length_factor))
            for index in range(len(coords))
        ]
        zone_polygon = Polygon(
            zone_nodes,
            label=f"{zone.label} wind zone",
            poly_type=PolygonType.ZONE,
        )
        zone_polygon.associated_frame_ids = list(surface.associated_frame_ids)

        coefficient_kind = "cpe10" if self._wind_cpe_index == 0 else "cpe1"
        raw_coefficients = getattr(zone, coefficient_kind)
        if np.isscalar(raw_coefficients):
            coefficients = (float(raw_coefficients), float(raw_coefficients))
        else:
            values = tuple(float(value) for value in raw_coefficients)
            if not values:
                raise ValueError("Wind zone Cpe katsayısı boş.")
            coefficients = (values[0], values[1] if len(values) > 1 else values[0])

        normal = np.asarray(Polygon.calculate_normal(zone_nodes), dtype=float)
        if float(np.dot(normal, wind_direction)) > 0.0:
            sign = -1.0
        else:
            sign = 1.0

        loads = []
        kind_label = "CPE10" if self._wind_cpe_index == 0 else "CPE1"
        for cpe_label, cpe in zip(("MN", "MX"), coefficients):
            for cpi_label, cpi in (
                ("P", self._cpi_positive),
                ("M", self._cpi_negative),
            ):
                pattern_name = (
                    f"WIND_{direction_key}_{kind_label}_{cpe_label}_{cpi_label}"
                )
                pressure = sign * q_p * (cpe - cpi)
                value = convert_value(
                                        Dimension.AREA_LOAD, pressure, UnitSystem.KN_M,
                                        self.project.unit_system,
                                    )
                loads.append(AreaUniformLoad(
                    pattern_name=pattern_name,
                    direction=LoadDirection.LOCAL_2,
                    value=float(value),
                    source_name=f"{zone.label} {kind_label} {cpe_label}/{cpi_label}",
                ))
                existing = self.project.load_patterns.get(pattern_name)
                if existing is None:
                    self.project.add_load_pattern(LoadPattern(
                        name=pattern_name,
                        design_type="Wind",
                        self_wt_mult=0.0,
                    ))
                elif str(existing.design_type).lower() != "wind":
                    raise ValueError(
                        f"'{pattern_name}' mevcut Load Pattern tipi "
                        f"{existing.design_type!r}; Wind gerekli."
                    )

        source_key = f"wind:{direction_key}:{zone_index}"
        distribution = DistType.from_input(surface.transfer_dist_type)
        generated = build_polygon_frame_loads(
                                                self.scene,
                                                zone_polygon,
                                                loads,
                                                dist_type=distribution,
                                                step=self._step,        # ★ ekle
                                                n_bins=self._n_bins,    # ★ ekle
                                            )
        manager = self.project.loads
        manager.record_wind_zone_transfer(
            int(surface.unique_id),
            source_key=source_key,
            direction_key=direction_key,
            zone_label=str(zone.label),
            cpe_kind=kind_label,
            dist_type=distribution,
            loads=loads,
        )
        manager.replace_polygon_frame_transfers(
            self.scene,
            int(surface.unique_id),
            generated,
            source_key=source_key,
            metadata={
                "source_type": "wind_zone",
                "direction_key": direction_key,
                "zone_label": str(zone.label),
            },
        )

        self.scene.mark_dirty()
        frames = {
            int(frame.unique_id): frame
            for frame in self.scene.frames.values()
        }
        touched = [frames[frame_id] for frame_id in generated if frame_id in frames]
        if touched and callable(self.on_transfer_complete):
            self.on_transfer_complete(touched)
        segment_count = sum(
            len(load_set.segments)
            for pattern_loads in generated.values()
            for load_set in pattern_loads.values()
        )
        self._status = (
            f"{zone.label}: {segment_count} rüzgar yük segmenti aktarıldı."
        )
        logger.info("[AreaToFrame] %s", self._status)
        return segment_count

    def _transfer(self, polygon: Polygon) -> int:

        generated = build_polygon_frame_loads(
            self.scene, polygon,
            step=self._step,
            n_bins=self._n_bins,
        )

        if not generated:
            self._status = "Aktarım için segment üretilemedi."
            return 0

        # ★ Frame'lere YAZ
        manager = getattr(
            getattr(self.scene, "project", None), "loads", None,
        )
        if manager is not None and hasattr(
            manager, "replace_polygon_frame_transfers"
        ):
            manager.replace_polygon_frame_transfers(
                self.scene, int(polygon.unique_id), generated,
            )
        else:
            # Fallback — doğrudan yaz
            frames_map = {
                int(frame.unique_id): frame
                for frame in self.scene.frames.values()
            }
            for frame_id, pattern_loads in generated.items():
                frame = frames_map.get(frame_id)
                if frame is None:
                    continue
                for pattern_name, load_set in pattern_loads.items():
                    frame.dist_load_sets[pattern_name] = deepcopy(load_set)
                    frame.mark_dirty()

        self.scene.mark_dirty()

        touched = {
            int(fid) for fid in generated
        }
        if touched and callable(self.on_transfer_complete):
            self.on_transfer_complete(list(touched))

        segment_count = sum(
            len(load_set.segments)
            for pattern_loads in generated.values()
            for load_set in pattern_loads.values()
        )
        self._status = (
            f"{segment_count} yayılı yük segmenti "
            f"{len(generated)} frame'e aktarıldı."
        )
        logger.info("[AreaToFrame] %s", self._status)
        return segment_count

    @staticmethod
    def _polygon_label(polygon: Polygon) -> str:
        return polygon.label or f"Polygon {polygon.unique_id}"

    def _area_load_unit(self) -> str:
        unit = self.project.unit_system
        return f"{unit.force_unit}/{unit.length_unit}²"

    @staticmethod
    def _distribution_index(value) -> int:
        text = str(getattr(value, "value", value)).lower()
        if "two" in text:
            return 2
        if "u2" in text:
            return 1
        return 0
