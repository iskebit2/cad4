# ui/panels/load_manager_panel.py
from __future__ import annotations

from copy import deepcopy
from typing import Any

from imgui_bundle import imgui

from app.settings.categories import Category
from domain.definition import ComboItem, LoadCase, LoadCombination, LoadPattern, StaticLoadAssignment
from ui.base.panel_base import PanelBase


_PATTERN_TYPES = ("Dead", "Live", "Snow", "Wind", "Quake", "Other")
_CASE_TYPES = ("LinStatic", "LinModal", "ResponseSpectrum")
_COMBO_TYPES = ("Linear Add", "Envelope", "SRSS")


class LoadManagerPanel(PanelBase):
    panel_name = "load_manager"
    title = "Load Manager"
    category = Category.LOADS
    quick = True
    menu_label = "Load Manager"
    context = ("project",)
    uses_draft = True
    show_apply_bar = True
    width = 720
    height = 680
    pos_first_use = (400.0, 80.0)

    def __init__(self, app=None, **overrides):
        self.project: Any = None
        self._draft_patterns: dict[str, LoadPattern] = {}
        self._draft_cases: dict[str, LoadCase] = {}
        self._draft_combos: dict[str, LoadCombination] = {}
        self._draft_config: Any = None

        self._new_pat_name: str = ""
        self._new_pat_type_idx: int = 0
        self._new_pat_sw: float = 0.0

        self._new_case_name: str = ""
        self._new_case_type_idx: int = 0
        self._new_case_pat_idx: int = 0
        self._new_case_sf: float = 1.0

        self._new_combo_name: str = ""
        self._new_combo_type_idx: int = 0
        self._new_combo_item_idx: int = 0
        self._new_combo_sf: float = 1.0

        self._dirty_flag: bool = False
        self._status_text: str = ""
        super().__init__(app=app, **overrides)

    def _source_project(self) -> Any:
        if self.project is not None:
            return self.project
        if self.app is not None:
            return getattr(self.app, "current_project", None)
        return None

    def _refresh_draft(self) -> None:
        proj = self._source_project()
        self._original = proj
        if proj is None:
            self.draft = None
            self._draft_patterns = {}
            self._draft_cases = {}
            self._draft_combos = {}
            self._draft_config = None
            self._dirty = False
            self._dirty_flag = False
            return

        self._draft_patterns = deepcopy(getattr(proj, "load_patterns", {}) or {})
        self._draft_cases = deepcopy(getattr(proj, "load_cases", {}) or {})
        self._draft_combos = deepcopy(getattr(proj, "combinations", {}) or {})
        self._draft_config = deepcopy(getattr(proj, "config", None))
        self.draft = {
            "load_patterns": self._draft_patterns,
            "load_cases": self._draft_cases,
            "combinations": self._draft_combos,
            "config": self._draft_config,
        }
        self._dirty = False
        self._dirty_flag = False

    def _mark_changed(self, msg: str = "") -> None:
        self._dirty_flag = True
        self._dirty = True
        if msg:
            self._status_text = msg

    def has_pending_changes(self) -> bool:
        return bool(self._dirty_flag or self._dirty)

    def on_apply_action(self) -> None:
        proj = self._source_project()
        if proj is None:
            return
        proj.load_patterns = deepcopy(self._draft_patterns)
        proj.load_cases = deepcopy(self._draft_cases)
        proj.combinations = deepcopy(self._draft_combos)
        if self._draft_config is not None:
            proj.config = deepcopy(self._draft_config)
        self._status_text = "Proje yük tanımları uygulandı."
        if self.app is not None and getattr(self.app, "ui", None) is not None:
            self.app.ui.on_project_changed()
        self._refresh_draft()

    def on_reset_action(self) -> None:
        self._refresh_draft()
        self._status_text = "Değişiklikler geri alındı."

    def draw_content(self) -> None:
        if self._source_project() is None:
            imgui.text_colored(imgui.ImVec4(0.95, 0.55, 0.4, 1.0), "Proje bağlı değil.")
            return

        default_open = imgui.TreeNodeFlags_.default_open
        if imgui.collapsing_header("Yük Paternleri (Ölü, Hareketli, Kar, Rüzgar, Deprem)", flags=default_open):
            self._draw_patterns_section()

        if imgui.collapsing_header("Rüzgar ve Kar Yükü Parametreleri", flags=default_open):
            self._draw_wind_snow_section()

        if imgui.collapsing_header("Yük Durumları (Load Cases)"):
            self._draw_cases_section()

        if imgui.collapsing_header("Yük Kombinasyonları (Load Combinations)"):
            self._draw_combinations_section()

        if self._status_text:
            imgui.separator()
            self.status_line(self._status_text, "info")

    def _draw_patterns_section(self) -> None:
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if self._draft_patterns and imgui.begin_table("##lm_pat_tbl", 4, flags):
            imgui.table_setup_column("Ad", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("Tür", imgui.TableColumnFlags_.width_fixed, 110)
            imgui.table_setup_column("Öz Ağırlık", imgui.TableColumnFlags_.width_fixed, 100)
            imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 45)
            imgui.table_headers_row()

            for name in sorted(self._draft_patterns.keys()):
                pat = self._draft_patterns[name]
                imgui.table_next_row()

                imgui.table_set_column_index(0)
                imgui.text(name)

                imgui.table_set_column_index(1)
                cur_type = str(getattr(pat, "design_type", "Dead"))
                cur_idx = _PATTERN_TYPES.index(cur_type) if cur_type in _PATTERN_TYPES else 0
                imgui.push_item_width(-1)
                ch_t, new_idx = imgui.combo(f"##pt_{name}", cur_idx, list(_PATTERN_TYPES))
                imgui.pop_item_width()
                if ch_t and _PATTERN_TYPES[new_idx] != cur_type:
                    pat.design_type = _PATTERN_TYPES[new_idx]
                    self._mark_changed()

                imgui.table_set_column_index(2)
                cur_sw = float(getattr(pat, "self_wt_mult", 0.0) or 0.0)
                imgui.push_item_width(-1)
                ch_sw, new_sw = imgui.input_float(f"##psw_{name}", cur_sw, step=0.1, format="%.2f")
                imgui.pop_item_width()
                if ch_sw and abs(new_sw - cur_sw) > 1e-9:
                    pat.self_wt_mult = float(new_sw)
                    self._mark_changed()

                imgui.table_set_column_index(3)
                if imgui.button(f"X##pdel_{name}", imgui.ImVec2(32, 0)):
                    del self._draft_patterns[name]
                    self._mark_changed(f"'{name}' taslaktan kaldırıldı.")
                    break

            imgui.end_table()

        imgui.spacing()
        imgui.text("Ad")
        imgui.same_line(90)
        imgui.push_item_width(170)
        _, self._new_pat_name = imgui.input_text("##new_pat_name", self._new_pat_name, 128)
        imgui.pop_item_width()

        imgui.same_line()
        imgui.text("Tür")
        imgui.same_line()
        imgui.push_item_width(110)
        _, self._new_pat_type_idx = imgui.combo("##new_pat_type", self._new_pat_type_idx, list(_PATTERN_TYPES))
        imgui.pop_item_width()

        imgui.same_line()
        imgui.text("SelfWt")
        imgui.same_line()
        imgui.push_item_width(80)
        _, self._new_pat_sw = imgui.input_float("##new_pat_sw", self._new_pat_sw, step=0.1, format="%.2f")
        imgui.pop_item_width()

        clean = self._new_pat_name.strip()
        can_add = bool(clean) and clean not in self._draft_patterns
        imgui.same_line()
        if self.action_button("+ Ekle", width=70, enabled=can_add):
            ptype = _PATTERN_TYPES[self._new_pat_type_idx]
            self._draft_patterns[clean] = LoadPattern(
                name=clean,
                design_type=ptype,
                self_wt_mult=float(self._new_pat_sw),
            )
            self._new_pat_name = ""
            self._new_pat_sw = 0.0
            self._mark_changed(f"'{clean}' ({ptype}) taslağa eklendi.")

    def _draw_wind_snow_section(self) -> None:
        if self._draft_config is None:
            imgui.text_disabled("Yapılandırma bulunamadı.")
            return

        w = self._draft_config.wind
        self._config_float("Rüzgar vb0 (m/s)", w, "vb0", "##w_vb0")
        self._config_float("Rüzgar z0", w, "z0", "##w_z0")
        self._config_float("Rüzgar z1", w, "z1", "##w_z1")
        self._config_float("Rüzgar z2", w, "z2", "##w_z2")

        s = self._draft_config.snow
        self._config_float("Kar sk (kN/m²)", s, "sk", "##s_sk")
        self._config_float("Kar Ce", s, "exposure_coefficient", "##s_ce")
        self._config_float("Kar Ct", s, "thermal_coefficient", "##s_ct")
        self._config_float("Kar μ", s, "shape_coefficient", "##s_mu")

    def _config_float(self, label: str, obj: Any, attr: str, widget_id: str) -> None:
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label)
        imgui.same_line(190)
        imgui.push_item_width(140)
        changed, new_val = imgui.input_float(widget_id, val, step=0.1, format="%.3f")
        imgui.pop_item_width()
        if changed and abs(new_val - val) > 1e-9:
            setattr(obj, attr, float(new_val))
            self._mark_changed()

    def _draw_cases_section(self) -> None:
        for cname in sorted(self._draft_cases.keys()):
            lc = self._draft_cases[cname]
            imgui.text(f"{cname} [{getattr(lc, 'case_type', 'LinStatic')}]")
            imgui.same_line(260)
            run_val = bool(getattr(lc, "run_case", True))
            ch_r, new_r = imgui.checkbox(f"Çalıştır##case_run_{cname}", run_val)
            if ch_r and new_r != run_val:
                lc.run_case = new_r
                self._mark_changed()
            imgui.same_line()
            if imgui.button(f"Sil##case_del_{cname}", imgui.ImVec2(50, 0)):
                del self._draft_cases[cname]
                self._mark_changed(f"'{cname}' yük durumu silindi.")
                break

        imgui.spacing()
        imgui.text("Durum Adı")
        imgui.same_line(110)
        imgui.push_item_width(150)
        _, self._new_case_name = imgui.input_text("##new_case_name", self._new_case_name, 128)
        imgui.pop_item_width()

        imgui.same_line()
        imgui.push_item_width(130)
        _, self._new_case_type_idx = imgui.combo("##new_case_type", self._new_case_type_idx, list(_CASE_TYPES))
        imgui.pop_item_width()

        pat_names = sorted(self._draft_patterns.keys())
        if pat_names:
            if self._new_case_pat_idx >= len(pat_names):
                self._new_case_pat_idx = 0
            imgui.same_line()
            imgui.push_item_width(120)
            _, self._new_case_pat_idx = imgui.combo("##new_case_pat", self._new_case_pat_idx, pat_names)
            imgui.pop_item_width()

            imgui.same_line()
            imgui.push_item_width(70)
            _, self._new_case_sf = imgui.input_float("##new_case_sf", self._new_case_sf, step=0.1, format="%.2f")
            imgui.pop_item_width()

        clean_case = self._new_case_name.strip()
        can_add_case = bool(clean_case) and clean_case not in self._draft_cases
        if self.action_button("+ Durum Ekle", width=110, enabled=can_add_case):
            ctype = _CASE_TYPES[self._new_case_type_idx]
            assigns: list[StaticLoadAssignment] = []
            if pat_names and ctype == "LinStatic":
                assigns.append(
                    StaticLoadAssignment(
                        load_type="Load pattern",
                        load_name=pat_names[self._new_case_pat_idx],
                        load_sf=float(self._new_case_sf),
                    )
                )
            self._draft_cases[clean_case] = LoadCase(
                name=clean_case,
                case_type=ctype,
                design_type=_PATTERN_TYPES[self._new_pat_type_idx] if self._new_pat_type_idx < len(_PATTERN_TYPES) else "Dead",
                run_case=True,
                static_assignments=assigns,
            )
            self._new_case_name = ""
            self._mark_changed(f"'{clean_case}' yük durumu eklendi.")

    def _draw_combinations_section(self) -> None:
        for cb_name in sorted(self._draft_combos.keys()):
            combo = self._draft_combos[cb_name]
            desc = ", ".join(f"{it.scale_factor:+.2f}*{it.case_or_pattern_name}" for it in combo.items)
            imgui.text(f"{cb_name} ({combo.combo_type}): {desc}")
            imgui.same_line()
            if imgui.button(f"Sil##combo_del_{cb_name}", imgui.ImVec2(50, 0)):
                del self._draft_combos[cb_name]
                self._mark_changed(f"'{cb_name}' kombinasyonu silindi.")
                break

        imgui.spacing()
        imgui.text("Kombo Adı")
        imgui.same_line(110)
        imgui.push_item_width(150)
        _, self._new_combo_name = imgui.input_text("##new_combo_name", self._new_combo_name, 128)
        imgui.pop_item_width()

        imgui.same_line()
        imgui.push_item_width(120)
        _, self._new_combo_type_idx = imgui.combo("##new_combo_type", self._new_combo_type_idx, list(_COMBO_TYPES))
        imgui.pop_item_width()

        source_names = sorted(set(self._draft_cases.keys()) | set(self._draft_patterns.keys()))
        if source_names:
            if self._new_combo_item_idx >= len(source_names):
                self._new_combo_item_idx = 0
            imgui.same_line()
            imgui.push_item_width(120)
            _, self._new_combo_item_idx = imgui.combo("##new_combo_src", self._new_combo_item_idx, source_names)
            imgui.pop_item_width()

            imgui.same_line()
            imgui.push_item_width(70)
            _, self._new_combo_sf = imgui.input_float("##new_combo_sf", self._new_combo_sf, step=0.1, format="%.2f")
            imgui.pop_item_width()

        clean_combo = self._new_combo_name.strip()
        can_add_combo = bool(clean_combo) and clean_combo not in self._draft_combos
        if self.action_button("+ Kombo Ekle", width=110, enabled=can_add_combo):
            items: list[ComboItem] = []
            if source_names:
                items.append(
                    ComboItem(
                        case_or_pattern_name=source_names[self._new_combo_item_idx],
                        scale_factor=float(self._new_combo_sf),
                    )
                )
            self._draft_combos[clean_combo] = LoadCombination(
                name=clean_combo,
                combo_type=_COMBO_TYPES[self._new_combo_type_idx],
                items=items,
            )
            self._new_combo_name = ""
            self._mark_changed(f"'{clean_combo}' kombinasyonu eklendi.")