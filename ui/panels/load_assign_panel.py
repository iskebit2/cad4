# ui/panels/load_assign_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from core.units import Dimension, UnitSystem, convert_value
from domain.definition import AreaUniformLoad, DistType, LoadDirection, LoadPattern
from domain.polygon import Polygon
from logging_config import CadLogger
from structload.data.preset_loader import PresetLibrary
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)

_DEFAULT_PATTERN = {"G": ("DEAD", "Dead"), "Q": ("LIVE", "Live")}
_SOURCE_LOAD_SYSTEM = UnitSystem.KN_M
_NON_AREA_PRESET_CATEGORIES = {"hazir_kiris_senaryolari"}


class LoadAssignPanel(PanelBase):
    __abstract__ = False
    panel_name = "load_assign"
    title = "Hazır Alan Yükleri"
    category = Category.LOADS
    quick = False
    context = ("project", "selection_polygons", "patterns")
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True

    width = 620
    height = 700
    pos_first_use = (400.0, 120.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.project = None
        self.selection_polygons: list[Polygon] = []
        self._preset_library: PresetLibrary | None = None
        self._preset_error: str | None = None
        self._categories: list[tuple[str, str, str, list[dict]]] = []
        self._category_id = ""
        self._selected_presets: set[tuple[str, int]] = set()
        self._selected_patterns: dict[str, str] = {
            lt: default[0] for lt, default in _DEFAULT_PATTERN.items()
        }
        self._distribution_types = [
            DistType.ONE_WAY_U1, DistType.ONE_WAY_U2, DistType.TWO_WAY,
        ]
        self._distribution_type_index = 0
        self._status = ""

    # ------------------------------------------------------------------
    def _on_context_ready(self) -> None:
        self.project = getattr(self, "project", None)
        selected = getattr(self, "selection_polygons", None) or []
        self.selection_polygons = [p for p in selected if isinstance(p, Polygon)]
        self._load_presets()
        self._sync_pattern_choices()

    # ------------------------------------------------------------------
    # 1. HEADER
    # ------------------------------------------------------------------
    def draw_header(self) -> None:
        self.section_label("Hedef Polygon'lar:")
        imgui.same_line()
        if not self.selection_polygons:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.65, 0.4, 1.0),
                "(Atama için modelde en az bir polygon seçin)",
            )
            return
        labels = [
            p.label or f"Polygon {p.unique_id}"
            for p in self.selection_polygons[:6]
        ]
        text = ", ".join(labels)
        if len(self.selection_polygons) > 6:
            text += f" ... (+{len(self.selection_polygons) - 6})"
        imgui.text_colored(
            imgui.ImVec4(0.55, 0.85, 0.6, 1.0),
            f"{len(self.selection_polygons)} adet: {text}",
        )

    # ------------------------------------------------------------------
    # 2. SETTINGS
    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        if self._preset_error:
            self.status_line(
                f"Hazır yük kütüphanesi yüklenemedi: {self._preset_error}", "error",
            )
            return

        self._draw_pattern_selector("G", "Ölü yük pattern")
        self._draw_pattern_selector("Q", "Hareketli yük pattern")

        imgui.push_item_width(240)
        _, self._distribution_type_index = imgui.combo(
            "Frame aktarımı",
            self._distribution_type_index,
            [dt.value for dt in self._distribution_types],
        )
        imgui.pop_item_width()

        if not self._categories:
            imgui.text_disabled("Atanabilir hazır alan yükü bulunamadı.")
            return

        category = next(
            (c for c in self._categories if c[0] == self._category_id),
            self._categories[0],
        )
        imgui.push_item_width(320)
        if imgui.begin_combo("Kategori", category[1]):
            for cat_id, label, _, _ in self._categories:
                if imgui.selectable(label, cat_id == self._category_id)[1]:
                    self._category_id = cat_id
            imgui.end_combo()
        imgui.pop_item_width()

    # ------------------------------------------------------------------
    # 3. TABLE — mevcut atamalar + preset seçim
    # ------------------------------------------------------------------
    def draw_table(self) -> None:
        if not self._categories:
            return

        category = next(
            (c for c in self._categories if c[0] == self._category_id),
            self._categories[0],
        )
        items = category[3]

        # --- Mevcut atamalar (collapse) ---
        if self.selection_polygons:
            if imgui.collapsing_header("Seçili Polygon Yükleri##existing_loads"):
                self._draw_existing_assignments_table()

        # --- Preset listesi ---
        self.section_label(f"Hazır Yükler — {category[1]}")
        imgui.text_disabled("(seçmek için sol sütundaki checkbox)")

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
            | imgui.TableFlags_.scroll_y
        )
        if not imgui.begin_table(
            "##la_presets", 3, flags, imgui.ImVec2(0, 320),
        ):
            return

        imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 32)
        imgui.table_setup_column("Yük Adı", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Değer", imgui.TableColumnFlags_.width_fixed, 110)
        imgui.table_headers_row()

        for idx, item in enumerate(items):
            key = (category[0], idx)
            is_selected = key in self._selected_presets

            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.push_id(f"preset_{category[0]}_{idx}")
            changed, checked = imgui.checkbox("##chk", is_selected)
            if changed:
                if checked:
                    self._selected_presets.add(key)
                else:
                    self._selected_presets.discard(key)
            imgui.pop_id()

            imgui.table_set_column_index(1)
            imgui.text(str(item["name"]))

            imgui.table_set_column_index(2)
            imgui.text_disabled(f"{float(item['kn']):.2f} kN/m²")

        imgui.end_table()

    def _draw_existing_assignments_table(self) -> None:
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table(
            "##la_existing", 4, flags, imgui.ImVec2(0, 120),
        ):
            return

        imgui.table_setup_column("Polygon", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Pattern", imgui.TableColumnFlags_.width_fixed, 100)
        imgui.table_setup_column("Değer", imgui.TableColumnFlags_.width_fixed, 100)
        imgui.table_setup_column("Yön", imgui.TableColumnFlags_.width_fixed, 90)
        imgui.table_headers_row()

        for polygon in self.selection_polygons:
            analysis_data = self.project.polygon_analysis_data(polygon, create=False)
            if analysis_data is None:
                continue
            loads = analysis_data.assigned_loads or []
            name = polygon.label or f"Polygon {polygon.unique_id}"
            if not loads:
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(name)
                imgui.table_set_column_index(1)
                imgui.text_disabled("(yok)")
                continue

            for i, load in enumerate(loads):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(name if i == 0 else "")
                imgui.table_set_column_index(1)
                imgui.text(load.pattern_name)
                imgui.table_set_column_index(2)
                imgui.text_disabled(f"{load.value:g}")
                imgui.table_set_column_index(3)
                imgui.text_disabled(load.direction.value)

        imgui.end_table()

    # ------------------------------------------------------------------
    # 4. ACTIONS
    # ------------------------------------------------------------------
    def draw_actions(self) -> None:
        can_apply = bool(self.selection_polygons) and bool(self._selected_presets)
        if self.action_button(
            f"Seçili Yüklere Ata ({len(self._selected_presets)})",
            260, can_apply,
        ):
            try:
                self._apply_selected_presets()
            except ValueError as e:
                self._status = f"Hata: {e}"
                logger.exception("[LoadAssign] apply hatası")
            except Exception:
                self._status = "Hata — log'a bakın."
                logger.exception("[LoadAssign] apply hatası")

        imgui.same_line()
        if self.action_button("Seçimi Temizle", 130, bool(self._selected_presets)):
            self._selected_presets.clear()
            self._status = "Seçim temizlendi."

        if not self.selection_polygons:
            imgui.spacing()
            self.status_line("⚠ Hedef polygon seçilmedi", "warn")
        elif not self._selected_presets:
            imgui.spacing()
            self.status_line(
                f"ℹ {len(self._selected_presets)} hazır yük seçili", "info",
            )
        else:
            imgui.spacing()
            self.status_line(
                f"✓ {len(self._selected_presets)} yük × "
                f"{len(self.selection_polygons)} polygon = "
                f"{len(self._selected_presets) * len(self.selection_polygons)} atama",
                "info",
            )

        if self._status:
            imgui.separator()
            imgui.text_wrapped(self._status)

    # ------------------------------------------------------------------
    # YARDIMCILAR (mevcut mantık)
    # ------------------------------------------------------------------
    def _load_presets(self) -> None:
        if self._preset_library is not None or self._preset_error:
            return
        try:
            self._preset_library = PresetLibrary()
            categories = []
            for cat_id, label, load_type in self._preset_library.kategori_listesi():
                if load_type not in _DEFAULT_PATTERN or cat_id in _NON_AREA_PRESET_CATEGORIES:
                    continue
                items = self._preset_library.kategori_yukleri(cat_id)
                area_loads = [
                    it for it in items
                    if it.get("unit", "kN/m²") == "kN/m²"
                    and it.get("kgf") is not None
                    and it.get("kn") is not None
                ]
                if area_loads:
                    categories.append((cat_id, label, load_type, area_loads))
            self._categories = categories
            if self._categories and self._category_id not in {c[0] for c in self._categories}:
                self._category_id = self._categories[0][0]
        except (OSError, ValueError, KeyError) as e:
            self._preset_error = str(e)
            logger.exception("[LoadAssign] preset library yüklenemedi")

    def _matching_patterns(self, load_type: str) -> list[str]:
        if self.project is None:
            return []
        target = _DEFAULT_PATTERN[load_type][1].lower()
        return sorted(
            name for name, pat in self.project.load_patterns.items()
            if str(getattr(pat, "design_type", "")).strip().lower() == target
        )

    def _sync_pattern_choices(self) -> None:
        for load_type, (default_name, _) in _DEFAULT_PATTERN.items():
            options = self._matching_patterns(load_type)
            if self._selected_patterns[load_type] not in options:
                self._selected_patterns[load_type] = (
                    options[0] if options else self._available_default_name(load_type, default_name)
                )

    def _available_default_name(self, load_type: str, base_name: str) -> str:
        if self.project is None:
            return base_name
        _, design_type = _DEFAULT_PATTERN[load_type]
        for cand in (base_name, f"{base_name}_{load_type}"):
            pat = self.project.load_patterns.get(cand)
            if pat is None or str(pat.design_type).lower() == design_type.lower():
                return cand
        suffix = 1
        while f"{base_name}_{load_type}_{suffix}" in self.project.load_patterns:
            suffix += 1
        return f"{base_name}_{load_type}_{suffix}"

    def _draw_pattern_selector(self, load_type: str, label: str) -> None:
        options = self._matching_patterns(load_type)
        current = self._selected_patterns[load_type]
        display = current if options else f"{current} (yoksa oluşturulur)"
        imgui.push_item_width(240)
        if imgui.begin_combo(f"{label}##pat_{load_type}", display):
            for name in options:
                if imgui.selectable(name, name == current)[1]:
                    self._selected_patterns[load_type] = name
            imgui.end_combo()
        imgui.pop_item_width()

    def _ensure_pattern(self, load_type: str) -> str:
        name = self._selected_patterns[load_type]
        _, design_type = _DEFAULT_PATTERN[load_type]
        existing = self.project.load_patterns.get(name)
        if existing is None:
            self.project.add_load_pattern(LoadPattern(name=name, design_type=design_type))
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

        categories = {c[0]: c for c in self._categories}
        selected_items = []
        for cat_id, idx in sorted(self._selected_presets):
            cat = categories.get(cat_id)
            if cat is None or not 0 <= idx < len(cat[3]):
                raise ValueError("Seçilen hazır yük artık kütüphanede bulunmuyor.")
            selected_items.append((cat[2], cat[3][idx]))

        pattern_names = {
            lt: self._selected_patterns[lt] for lt, _ in selected_items
        }
        for lt, name in pattern_names.items():
            existing = self.project.load_patterns.get(name)
            expected = _DEFAULT_PATTERN[lt][1]
            if existing is not None and str(existing.design_type).strip().lower() != expected.lower():
                raise ValueError(
                    f"'{name}' pattern tipi {existing.design_type!r}; "
                    f"{expected!r} gerekli."
                )

        distribution = self._distribution_types[self._distribution_type_index]
        assignments: list[AreaUniformLoad] = []
        for lt, item in selected_items:
            pattern_name = self._ensure_pattern(lt)
            value = convert_value(
                Dimension.AREA_LOAD, float(item["kn"]),
                _SOURCE_LOAD_SYSTEM, self.project.unit_system,
            )
            assignments.append(AreaUniformLoad(
                pattern_name=pattern_name,
                direction=LoadDirection.GRAVITY,
                value=float(value),
                source_name=str(item["name"]),
            ))

        for polygon in self.selection_polygons:
            for load in assignments:
                self.project.loads.add_area_load_transfer(
                    polygon, load,
                    analysis_data=self.project.polygon_analysis_data(polygon),
                    transfer_target="frames",
                    dist_type=distribution,
                )
                self.project.math_model.mark_dirty()

        count = len(assignments) * len(self.selection_polygons)
        self._selected_presets.clear()
        self._status = (
            f"{len(assignments)} yük, {len(self.selection_polygons)} polygon'a "
            f"atandı ({count} atama)."
        )
        logger.info("[LoadAssign] %s", self._status)
        return count