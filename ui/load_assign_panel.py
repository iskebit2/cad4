"""Assign one or more prepared surface loads to selected polygons."""
from __future__ import annotations

from imgui_bundle import imgui

from core.units import Dimension, UnitSystem, convert_value
from domain.definition import AreaUniformLoad, DistType, LoadDirection, LoadPattern
from domain.element import Polygon
from logging_config import CadLogger
from structload.data.preset_loader import PresetLibrary
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)

_DEFAULT_PATTERN = {"G": ("DEAD", "Dead"), "Q": ("LIVE", "Live")}
_SOURCE_LOAD_SYSTEM = UnitSystem.KN_M
_NON_AREA_PRESET_CATEGORIES = {"hazir_kiris_senaryolari"}


class LoadAssignPanel(BasePanel):
    """ImGui preset library and assignment UI for selected model polygons."""

    def __init__(self, on_apply=None):
        super().__init__(
            title="Hazır Alan Yükleri",
            width=520.0,
            height=620.0,
            pos_first_use=(400, 120),
        )
        self.on_apply = on_apply
        self.project = None
        self.selection_polygons: list[Polygon] = []
        self._preset_library: PresetLibrary | None = None
        self._preset_error: str | None = None
        self._categories: list[tuple[str, str, str, list[dict]]] = []
        self._category_id = ""
        self._selected_presets: set[tuple[str, int]] = set()
        self._selected_patterns: dict[str, str] = {
            load_type: default[0]
            for load_type, default in _DEFAULT_PATTERN.items()
        }
        self._distribution_types = [
            DistType.ONE_WAY_U1,
            DistType.ONE_WAY_U2,
            DistType.TWO_WAY,
        ]
        self._distribution_type_index = 0
        self._status = ""

    def set_context(self, ctx: dict):
        previous_project = self.project
        super().set_context(ctx)
        self.project = ctx.get("project")
        if self.project is not previous_project:
            self._selected_presets.clear()
            self._status = ""
        selected = ctx.get("selection_polygons", [])
        self.selection_polygons = [
            polygon for polygon in selected if isinstance(polygon, Polygon)
        ]

    def open(self, **kwargs):
        super().open(**kwargs)
        self._load_presets()
        self._sync_pattern_choices()

    def _load_presets(self):
        if self._preset_library is not None or self._preset_error:
            return
        try:
            self._preset_library = PresetLibrary()
            categories = []
            for category_id, label, load_type in self._preset_library.kategori_listesi():
                if (
                    load_type not in _DEFAULT_PATTERN
                    or category_id in _NON_AREA_PRESET_CATEGORIES
                ):
                    continue
                items = self._preset_library.kategori_yukleri(category_id)
                area_loads = [
                    item for item in items
                    if item.get("unit", "kN/m²") == "kN/m²"
                    and item.get("kgf") is not None
                    and item.get("kn") is not None
                ]
                if area_loads:
                    categories.append(
                        (category_id, label, load_type, area_loads)
                    )
            self._categories = categories
            if self._categories and self._category_id not in {
                category[0] for category in self._categories
            }:
                self._category_id = self._categories[0][0]
        except (OSError, ValueError, KeyError) as error:
            self._preset_error = str(error)
            logger.exception("[LoadAssign] Hazır yük kütüphanesi yüklenemedi.")

    def _matching_patterns(self, load_type: str) -> list[str]:
        if self.project is None:
            return []
        target = _DEFAULT_PATTERN[load_type][1].lower()
        return sorted(
            name
            for name, pattern in self.project.load_patterns.items()
            if str(getattr(pattern, "design_type", "")).strip().lower() == target
        )

    def _sync_pattern_choices(self):
        for load_type, (default_name, _) in _DEFAULT_PATTERN.items():
            options = self._matching_patterns(load_type)
            if self._selected_patterns[load_type] not in options:
                self._selected_patterns[load_type] = (
                    options[0] if options else self._available_default_name(
                        load_type, default_name,
                    )
                )

    def _available_default_name(self, load_type: str, base_name: str) -> str:
        if self.project is None:
            return base_name
        _, design_type = _DEFAULT_PATTERN[load_type]
        for candidate in (base_name, f"{base_name}_{load_type}"):
            pattern = self.project.load_patterns.get(candidate)
            if pattern is None or str(pattern.design_type).lower() == design_type.lower():
                return candidate
        suffix = 1
        while f"{base_name}_{load_type}_{suffix}" in self.project.load_patterns:
            suffix += 1
        return f"{base_name}_{load_type}_{suffix}"

    def draw_content(self):
        self._load_presets()
        self._sync_pattern_choices()

        if self._preset_error:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.45, 0.4, 1.0),
                f"Hazır yük kütüphanesi yüklenemedi: {self._preset_error}",
            )
            return

        imgui.text("Modelden polygon seçip bir veya daha fazla hazır alan yükü seçin.")
        if self.selection_polygons:
            labels = [
                polygon.label or f"Polygon {polygon.unique_id}"
                for polygon in self.selection_polygons
            ]
            imgui.text_colored(
                imgui.ImVec4(0.55, 0.85, 0.6, 1.0),
                f"Seçili polygon: {len(labels)} — {', '.join(labels)}",
            )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.65, 0.4, 1.0),
                "Atama için modelde en az bir polygon seçin.",
            )

        self._draw_existing_assignments()
        imgui.separator()
        self._draw_pattern_selector("G", "Ölü yük pattern")
        self._draw_pattern_selector("Q", "Hareketli yük pattern")
        _, self._distribution_type_index = imgui.combo(
            "Frame aktarımı",
            self._distribution_type_index,
            [dist_type.value for dist_type in self._distribution_types],
        )
        imgui.separator()

        if not self._categories:
            imgui.text("Atanabilir hazır alan yükü bulunamadı.")
            return

        category = next(
            item for item in self._categories
            if item[0] == self._category_id
        )
        if imgui.begin_combo("Yük kategorisi", category[1]):
            for category_id, label, _, _ in self._categories:
                if imgui.selectable(
                    label, category_id == self._category_id,
                )[1]:
                    self._category_id = category_id
            imgui.end_combo()

        for item_index, item in enumerate(category[3]):
            key = (category[0], item_index)
            is_selected = key in self._selected_presets
            label = (
                f"{item['name']}  |  {float(item['kn']):.2f} kN/m²"
                f"  ({category[2]})##preset_{category[0]}_{item_index}"
            )
            changed, checked = imgui.checkbox(label, is_selected)
            if changed:
                if checked:
                    self._selected_presets.add(key)
                else:
                    self._selected_presets.discard(key)

        imgui.separator()
        imgui.text(f"Seçili hazır yük: {len(self._selected_presets)}")
        if self._status:
            imgui.text_colored(
                imgui.ImVec4(0.55, 0.85, 0.6, 1.0), self._status,
            )
        if imgui.button(
            "Seçili yüklere ata##apply_polygon_presets",
            imgui.ImVec2(-1, 0),
        ):
            self._apply_selected_presets()

    def _draw_pattern_selector(self, load_type: str, label: str):
        options = self._matching_patterns(load_type)
        current = self._selected_patterns[load_type]
        display = current
        if not options:
            display = f"{current} (yoksa oluşturulur)"
        if imgui.begin_combo(f"{label}##pattern_{load_type}", display):
            for name in options:
                if imgui.selectable(name, name == current)[1]:
                    self._selected_patterns[load_type] = name
            imgui.end_combo()

    def _draw_existing_assignments(self):
        if not self.selection_polygons:
            return
        imgui.text("Seçili polygon yükleri")
        for polygon in self.selection_polygons:
            loads = getattr(polygon, "assigned_loads", ())
            name = polygon.label or f"Polygon {polygon.unique_id}"
            if not loads:
                imgui.text(f"{name}: atanmış alan yükü yok")
                continue
            for load in loads:
                source = getattr(load, "source_name", "") or load.pattern_name
                imgui.bullet_text(
                    f"{name}: {source} — {load.pattern_name}, "
                    f"{load.value:g} ({load.direction.value})"
                )

    def _ensure_pattern(self, load_type: str) -> str:
        name = self._selected_patterns[load_type]
        _, design_type = _DEFAULT_PATTERN[load_type]
        existing = self.project.load_patterns.get(name)
        if existing is None:
            self.project.add_load_pattern(
                LoadPattern(name=name, design_type=design_type)
            )
        elif str(existing.design_type).strip().lower() != design_type.lower():
            raise ValueError(
                f"'{name}' pattern tipi {existing.design_type!r}; "
                f"{design_type!r} gerekli."
            )
        return name

    def _apply_selected_presets(self) -> int:
        if self.project is None:
            self._status = "Aktif proje bulunamadı."
            return 0
        if not self.selection_polygons:
            self._status = "Önce en az bir polygon seçin."
            return 0
        if not self._selected_presets:
            self._status = "Atanacak hazır yük seçilmedi."
            return 0

        categories = {category[0]: category for category in self._categories}
        selected_items = []
        for category_id, item_index in sorted(self._selected_presets):
            category = categories.get(category_id)
            if category is None or not 0 <= item_index < len(category[3]):
                raise ValueError("Seçilen hazır yük artık kütüphanede bulunmuyor.")
            selected_items.append(
                (category[2], category[3][item_index])
            )

        pattern_names = {
            load_type: self._selected_patterns[load_type]
            for load_type, _ in selected_items
        }
        for load_type, name in pattern_names.items():
            existing = self.project.load_patterns.get(name)
            expected_type = _DEFAULT_PATTERN[load_type][1]
            if (
                existing is not None
                and str(existing.design_type).strip().lower()
                != expected_type.lower()
            ):
                raise ValueError(
                    f"'{name}' pattern tipi {existing.design_type!r}; "
                    f"{expected_type!r} gerekli."
                )

        distribution = self._distribution_types[
            self._distribution_type_index
        ]
        assignments: list[AreaUniformLoad] = []
        for load_type, item in selected_items:
            pattern_name = self._ensure_pattern(load_type)
            value = convert_value(
                Dimension.AREA_LOAD,
                float(item["kn"]),
                _SOURCE_LOAD_SYSTEM,
                self.project.unit_system,
            )
            assignments.append(
                AreaUniformLoad(
                    pattern_name=pattern_name,
                    direction=LoadDirection.GRAVITY,
                    value=float(value),
                    source_name=str(item["name"]),
                )
            )

        for polygon in self.selection_polygons:
            for load in assignments:
                self.project.loads.add_area_load_transfer(
                    polygon,
                    load,
                    transfer_target="frames",
                    dist_type=distribution,
                )

        count = len(assignments) * len(self.selection_polygons)
        self._selected_presets.clear()
        self._status = (
            f"{len(assignments)} yük, {len(self.selection_polygons)} "
            f"polygon'a atandı ({count} atama)."
        )
        logger.info("[LoadAssign] %s", self._status)
        return count
