# ui/panels/project_panels.py
from __future__ import annotations

from copy import deepcopy
from typing import Any

from imgui_bundle import imgui

from app.settings.categories import Category
from ui.base.panel_base import PanelBase


class ProjectInfoPanel(PanelBase):
    panel_name = "project_info"
    title = "Proje Bilgileri"
    category = Category.MANAGEMENT
    quick = True
    menu_label = "Proje Bilgileri"
    context = ("project",)
    uses_draft = True
    show_apply_bar = True
    width = 480
    height = 560
    pos_first_use = (500.0, 150.0)

    def __init__(self, app=None, **overrides):
        self.project: Any = None
        self._draft_info: Any = None
        self._draft_general: Any = None
        self._draft_site: Any = None
        super().__init__(app=app, **overrides)

    def _refresh_draft(self) -> None:
        proj = self._resolve_project()
        self._original = proj
        if proj is None:
            self.draft = None
            self._draft_info = None
            self._draft_general = None
            self._draft_site = None
            self._dirty = False
            return
        self._draft_info = deepcopy(getattr(proj, "info", None))
        self._draft_general = deepcopy(getattr(proj, "general_info", None))
        self._draft_site = deepcopy(getattr(proj, "site_info", None))
        self.draft = {
            "info": self._draft_info,
            "general_info": self._draft_general,
            "site_info": self._draft_site,
        }
        self._dirty = False

    def has_pending_changes(self) -> bool:
        return bool(self._dirty)

    def _emit_commands(self) -> None:
        proj = self._resolve_project()
        if proj is None:
            return
        if self._draft_info is not None:
            proj.info = deepcopy(self._draft_info)
        if self._draft_general is not None:
            proj.general_info = deepcopy(self._draft_general)
        if self._draft_site is not None:
            proj.site_info = deepcopy(self._draft_site)
        if getattr(proj, "scene", None) is not None and hasattr(proj.scene, "mark_dirty"):
            proj.scene.mark_dirty()
        ui = getattr(self.app, "ui", None) if self.app is not None else None
        if ui is not None and hasattr(ui, "on_project_changed"):
            ui.on_project_changed()

    def on_reset_action(self) -> None:
        self._refresh_draft()

    def draw_content(self) -> None:
        if self._resolve_project() is None:
            imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.4, 1.0), "Proje bağlı değil.")
            return

        self.section_label("Genel")
        imgui.separator()
        if self._draft_general is not None:
            self._field("Firma", "company_name", self._draft_general, "gen")
            self._field("Müşteri", "client_name", self._draft_general, "gen")
            self._field("Proje Adı", "project_name", self._draft_general, "gen")
            self._field("Proje No", "project_number", self._draft_general, "gen")
            self._field("Model Adı", "model_name", self._draft_general, "gen")
            self._field("Revizyon", "revision_number", self._draft_general, "gen")
            self._field("Mühendis", "engineer", self._draft_general, "gen")
            self._field("Kontrol", "checker", self._draft_general, "gen")
            self._field("Şef", "supervisor", self._draft_general, "gen")

        imgui.spacing()
        self.section_label("Saha")
        imgui.separator()
        if self._draft_site is not None:
            self._field("Zemin Sınıfı", "soil_class", self._draft_site, "site")
            self._field_float("Yatak Katsayısı", "subgrade_modulus_kn_m3", self._draft_site, "site")
            self._field_float("Hareketli Yük Kat.", "live_load_factor", self._draft_site, "site")
            self._field("Kadastro", "cadastral_info", self._draft_site, "site")
            self._field("Tarih", "date", self._draft_site, "site")

        imgui.spacing()
        self.section_label("Metadata")
        imgui.separator()
        if self._draft_info is not None:
            self._field("Proje Adı (Kısa)", "name", self._draft_info, "meta")
            self._field("Yazar", "author", self._draft_info, "meta")
            self._field("Açıklama", "description", self._draft_info, "meta")

    def _field(self, label: str, attr: str, obj: Any, scope: str) -> None:
        val = str(getattr(obj, attr, "") or "")
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        changed, new_val = imgui.input_text(f"##info_{scope}_{attr}", val, 256)
        imgui.pop_item_width()
        if changed and new_val != val:
            setattr(obj, attr, new_val)
            self.mark_dirty()

    def _field_float(self, label: str, attr: str, obj: Any, scope: str) -> None:
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        changed, new_val = imgui.input_float(f"##info_{scope}_{attr}", val)
        imgui.pop_item_width()
        if changed and new_val != val:
            setattr(obj, attr, float(new_val))
            self.mark_dirty()


class ProjectConfigPanel(PanelBase):
    panel_name = "project_config"
    title = "Proje Yapılandırması"
    category = Category.MANAGEMENT
    quick = True
    menu_label = "Proje Yapılandırması"
    context = ("project",)
    uses_draft = True
    show_apply_bar = True
    width = 450
    height = 560
    pos_first_use = (520.0, 180.0)

    def __init__(self, app=None, **overrides):
        self.project: Any = None
        self._draft_config: Any = None
        super().__init__(app=app, **overrides)

    def _refresh_draft(self) -> None:
        proj = self._resolve_project()
        self._original = proj
        if proj is None or getattr(proj, "config", None) is None:
            self.draft = None
            self._draft_config = None
            self._dirty = False
            return
        self._draft_config = deepcopy(proj.config)
        self.draft = self._draft_config
        self._dirty = False

    def has_pending_changes(self) -> bool:
        return bool(self._dirty)

    def _emit_commands(self) -> None:
        proj = self._resolve_project()
        if proj is None or self._draft_config is None:
            return
        proj.config = deepcopy(self._draft_config)
        ui = getattr(self.app, "ui", None) if self.app is not None else None
        if ui is not None and hasattr(ui, "on_project_changed"):
            ui.on_project_changed()

    def on_reset_action(self) -> None:
        self._refresh_draft()

    def draw_content(self) -> None:
        if self._resolve_project() is None:
            imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.4, 1.0), "Proje bağlı değil.")
            return
        if self._draft_config is None:
            imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "Config yok")
            return

        default_open = imgui.TreeNodeFlags_.default_open
        if imgui.collapsing_header("Rüzgar (TS EN 1991-1-4)", flags=default_open):
            w = self._draft_config.wind
            self._float("vb0 (m/s)", w, "vb0", "wind")
            self._combo("Arazi Kat.", w, "terrain_category", ["I", "II", "III", "IV"], "wind")
            self._float("z0", w, "z0", "wind")
            self._float("z1", w, "z1", "wind")
            self._float("z2", w, "z2", "wind")
            self._float("cpi+", w, "cpi_positive", "wind")
            self._float("cpi-", w, "cpi_negative", "wind")

        if imgui.collapsing_header("Kar (TS EN 1991-1-3)", flags=default_open):
            s = self._draft_config.snow
            self._float("sk (kN/m²)", s, "sk", "snow")
            self._float("Ce", s, "exposure_coefficient", "snow")
            self._float("Ct", s, "thermal_coefficient", "snow")
            self._float("μ", s, "shape_coefficient", "snow")

        if imgui.collapsing_header("Deprem (TBDY 2018)", flags=default_open):
            e = self._draft_config.seismic
            self._float("Ss", e, "ss", "seis")
            self._float("S1", e, "s1", "seis")
            self._combo("Zemin", e, "soil_class", ["ZA", "ZB", "ZC", "ZD", "ZE", "ZF"], "seis")
            self._float("Önem (I)", e, "importance_factor", "seis")
            self._float("R", e, "behavior_factor", "seis")
            self._float("D", e, "overstrength_factor", "seis")

    def _float(self, label: str, obj: Any, attr: str, scope: str, step: float = 0.1) -> None:
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label)
        imgui.same_line(180)
        imgui.push_item_width(-1)
        changed, new_val = imgui.input_float(f"##cfg_{scope}_{attr}", val, step=step)
        imgui.pop_item_width()
        if changed and new_val != val:
            setattr(obj, attr, float(new_val))
            self.mark_dirty()

    def _combo(self, label: str, obj: Any, attr: str, choices: list[str], scope: str) -> None:
        cur = str(getattr(obj, attr, "") or "")
        idx = choices.index(cur) if cur in choices else 0
        imgui.text(label)
        imgui.same_line(180)
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo(f"##cfg_{scope}_{attr}", idx, choices)
        imgui.pop_item_width()
        if changed and 0 <= new_idx < len(choices) and choices[new_idx] != cur:
            setattr(obj, attr, choices[new_idx])
            self.mark_dirty()