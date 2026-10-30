# ui/definition_panel.py
"""
Tüm dataclass tanımlarını tek panelde yöneten jenerik editör.
dataclasses.fields() + get_type_hints() üzerinden reflection yapar.

Yeni tanım tipi eklemek için DEFINITIONS listesine bir satır ekle.
"""
from __future__ import annotations

import dataclasses
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import (
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from imgui_bundle import imgui

from data.enums import ConstraintType, LinkPropType, SectionType
from domain.definition import (
    AreaSection,
    AutoSeismicTSC2018,
    ConstraintDefinition,
    LinkProp,
    LinkPropLinear,
    LoadCase,
    LoadCombination,
    LoadPattern,
    Material,
    ModalCase,
    ResponseSpectrumCase,
    Section,
    SectionCut,
    SpectrumFunction,
)
from logging_config import CadLogger
from tools.section_preview import draw_section_preview
from ui.base_panel import BasePanel
from ui.widgets.color_picker import color_edit3

logger = CadLogger.get(__name__)


# ============================================================================
# YARDIMCILAR
# ============================================================================
def _unique_name(container: dict, base: str) -> str:
    """'{base}_{n}' formatında benzersiz isim üret."""
    if base not in container:
        return base
    n = 1
    while f"{base}_{n}" in container:
        n += 1
    return f"{base}_{n}"


def _is_enum_type(tp) -> bool:
    try:
        return isinstance(tp, type) and issubclass(tp, Enum)
    except TypeError:
        return False


def _is_union(origin) -> bool:
    """Union[int, str] veya int | str (Py3.10+)."""
    if origin is Union:
        return True
    if hasattr(types, "UnionType") and origin is types.UnionType:
        return True
    return False


def _strip_optional(tp):
    """Optional[X] → X, Union[X, None] → X."""
    origin = get_origin(tp)
    if not _is_union(origin):
        return tp
    args = get_args(tp)
    non_none = [a for a in args if a is not type(None)]
    return non_none[0] if len(non_none) == 1 else tp


def _name_attr(obj) -> str:
    """Dataclass'ın isim alanı hangisi?"""
    for cand in ("name", "load_pattern", "combo_name", "prop_name", "cut_name"):
        if hasattr(obj, cand):
            return cand
    return "name"


# ============================================================================
# DEFINITION REGISTRY
# ============================================================================
# (cls, container_attr, label, factory, clone)
DEFINITIONS: list[tuple] = [
    (Material, "materials", "MATERIAL PROPERTIES",
        lambda p: Material(name=_unique_name(p.materials, "MALZEME")),
        lambda m: dataclasses.replace(m, color=tuple(m.color))),

    (Section, "sections", "FRAME SECTION PROPERTIES",
        lambda p: Section(
            name=_unique_name(p.sections, "KESIT"),
            profile_type=SectionType.RECT,
            profile_params={"h": 300.0, "b": 600.0},
            material=next(iter(p.materials.values()), None),
        ),
        lambda s: Section(
            name=s.name, profile_type=s.profile_type,
            profile_params=dict(s.profile_params),
            material=s.material, color=tuple(s.color),
            rebar_column=dict(s.rebar_column or {}),
            rebar_beam=dict(s.rebar_beam or {}),
            time_dependent=dict(s.time_dependent or {}),
            sd_section=s.sd_section,        # referans (kopya değil)
        )),

    # ★ YENİ: AreaSection
    (AreaSection, "area_sections", "AREA SECTION PROPERTIES",
        lambda p: AreaSection(
            name=_unique_name(p.area_sections, "ASEC"),
            material=next(iter(p.materials.values()), None),
        ),
        lambda s: AreaSection(
            name=s.name, prop_type=s.prop_type, area_type=s.area_type,
            material=s.material, mat_angle=s.mat_angle,
            thickness=s.thickness, bend_thick=s.bend_thick,
            drill_dof=s.drill_dof, color=tuple(s.color),
            membrane_f11=s.membrane_f11, membrane_f22=s.membrane_f22,
            membrane_f12=s.membrane_f12,
            bending_m11=s.bending_m11, bending_m22=s.bending_m22,
            bending_m12=s.bending_m12,
            shear_v13=s.shear_v13, shear_v23=s.shear_v23,
            mass=s.mass, weight=s.weight,
            rebar_mat=s.rebar_mat, rebar_opt=s.rebar_opt,
            type_size=s.type_size, auto_sf_size=s.auto_sf_size,
        )),

    # ★ YENİ: ConstraintDefinition
    (ConstraintDefinition, "constraint_definitions", "CONSTRAINT DEFINITIONS",
        lambda p: ConstraintDefinition(
            name=_unique_name(p.constraint_definitions, "CONSTR"),
            constraint_type=ConstraintType.DIAPHRAGM,
        ),
        dataclasses.replace),

    (LoadPattern, "load_patterns", "LOAD PATTERN DEFINITIONS",
        lambda p: LoadPattern(name=_unique_name(p.load_patterns, "PATTERN")),
        dataclasses.replace),

    (LoadCase, "load_cases", "LOAD CASE DEFINITIONS",
        lambda p: LoadCase(name=_unique_name(p.load_cases, "CASE")),
        lambda c: dataclasses.replace(
            c, static_assignments=[dataclasses.replace(a) for a in c.static_assignments])),

    (ModalCase, "modal_cases", "CASE - MODAL",
        lambda p: ModalCase(name=_unique_name(p.modal_cases, "MODAL")),
        dataclasses.replace),

    (LoadCombination, "combinations", "COMBINATION DEFINITIONS",
        lambda p: LoadCombination(name=_unique_name(p.combinations, "COMBO")),
        lambda c: dataclasses.replace(
            c, items=[dataclasses.replace(i) for i in c.items])),

    (SpectrumFunction, "spectrum_functions", "FUNCTION - RESPONSE SPECTRUM",
        lambda p: SpectrumFunction(name=_unique_name(p.spectrum_functions, "SPEC")),
        dataclasses.replace),

    (ResponseSpectrumCase, "response_spectrum_cases", "CASE - RESPONSE SPECTRUM",
        lambda p: ResponseSpectrumCase(name=_unique_name(p.response_spectrum_cases, "RSC")),
        lambda c: dataclasses.replace(
            c, assignments=[dataclasses.replace(a) for a in c.assignments])),

    (AutoSeismicTSC2018, "auto_seismics", "AUTO SEISMIC - TSC2018",
        lambda p: AutoSeismicTSC2018(load_pattern=_unique_name(p.auto_seismics, "SEISMIC")),
        dataclasses.replace),

    (LinkProp, "link_props", "LINK PROPERTY DEFINITIONS",
        lambda p: LinkPropLinear(
            name=_unique_name(p.link_props, "LINK"),
            prop_type=LinkPropType.LINEAR,
        ),
        lambda lp: LinkPropLinear(
            name=lp.name, prop_type=lp.prop_type,
            DOF=dict(getattr(lp, "DOF", {}) or {}),
            Fixed=dict(getattr(lp, "Fixed", {}) or {}),
            Ke=dict(getattr(lp, "Ke", {}) or {}),
            Ce=dict(getattr(lp, "Ce", {}) or {}),
        )),

    (SectionCut, "section_cuts", "SECTION CUTS",
        lambda p: SectionCut(name=_unique_name(p.section_cuts, "CUT")),
        dataclasses.replace),
]


# Kesit tipi varsayılan parametreleri
_DEFAULT_SECTION_PARAMS: dict[SectionType, dict[str, float]] = {
    SectionType.RECT:    {"h": 300.0, "b": 600.0},
    SectionType.CIRCLE:  {"d": 400.0},
    SectionType.PIPE:    {"d": 400.0, "t": 20.0},
    SectionType.BOX:     {"h": 400.0, "b": 400.0, "t": 20.0},
    SectionType.TUBE:    {"h": 200.0, "b": 200.0, "t": 10.0},
    SectionType.I:       {"h": 400.0, "b": 200.0, "tw": 10.0, "tf": 15.0},
    SectionType.C:       {"h": 300.0, "b": 100.0, "tw": 8.0, "tf": 12.0},
    SectionType.CHANNEL: {"h": 300.0, "b": 100.0, "tw": 8.0, "tf": 12.0},
    SectionType.L:       {"h": 100.0, "b": 100.0, "t": 10.0},
    SectionType.T:       {"h": 200.0, "b": 150.0, "tw": 8.0, "tf": 12.0},
}


# ============================================================================
# PANEL
# ============================================================================
class DefinitionPanel(BasePanel):
    def __init__(self):
        self.visible = False
        self.app = None
        self.on_changed = None                 # Callable[[str], None]

        self._current_idx: int = 0
        self._selected_name: str | None = None
        self._draft: Any = None
        self._is_new: bool = False
        self._search: str = ""
        self._confirm_delete_name: str | None = None

        # Her frame'de temizlenir, o frame'deki tespitleri tutar
        self._render_errors: set[str] = set()
        self._unsupported_fields: set[str] = set()

        # Tip çözümleme cache'i: (cls) -> {field_name: type}
        self._hints_cache: dict[type, dict[str, Any]] = {}

        self._catalog_search: dict[int, str] = {}
    # -----------------------------------------------------------------
    # LIFECYCLE
    # -----------------------------------------------------------------
    def open(self):
        self.visible = True

    def close(self):
        self.visible = False
        self._clear_draft()

    def _clear_draft(self):
        self._draft = None
        self._selected_name = None
        self._is_new = False

    # -----------------------------------------------------------------
    # TYPE HINTS — cache'li
    # -----------------------------------------------------------------
    def _get_hints(self, cls) -> dict[str, Any]:
        cached = self._hints_cache.get(cls)
        if cached is not None:
            return cached
        try:
            hints = get_type_hints(cls)
        except Exception:
            logger.debug(f"[DefinitionPanel] get_type_hints({cls.__name__}) başarısız")
            hints = {}
        self._hints_cache[cls] = hints
        return hints

    # -----------------------------------------------------------------
    # ANA DRAW
    # -----------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        # Frame başında tanılama setlerini temizle
        self._render_errors.clear()
        self._unsupported_fields.clear()

        imgui.set_next_window_size(imgui.ImVec2(1000, 680), imgui.Cond_.first_use_ever)
        expanded, opened = imgui.begin("Definition Manager", True)
        if not opened:
            self.close()
            imgui.end()
            return

        project = getattr(self.app, "current_project", None)
        if project is None:
            imgui.text_colored(imgui.ImVec4(1, 0.5, 0.5, 1.0), 'Proje yok.')
            imgui.end()
            return

        self._draw_type_selector()
        imgui.separator()

        cls, container_attr, label, factory, clone = DEFINITIONS[self._current_idx]
        container = getattr(project, container_attr, {})

        self._draw_toolbar(container, container_attr)
        imgui.separator()

        imgui.columns(2, "def_cols", borders=True)
        self._draw_list(container)
        imgui.next_column()
        self._draw_editor(cls, container, project)
        imgui.columns(1)

        self._draw_delete_confirm(container, project)
        self._draw_diagnostics()
        imgui.end()

    # -----------------------------------------------------------------
    # TİP SEÇİCİ
    # -----------------------------------------------------------------
    def _draw_type_selector(self):
        labels = [d[2] for d in DEFINITIONS]
        imgui.set_next_item_width(320)
        if imgui.begin_combo("Table", labels[self._current_idx]):
            for i, lbl in enumerate(labels):
                clicked, _ = imgui.selectable(lbl, i == self._current_idx)
                if clicked and i != self._current_idx:
                    self._current_idx = i
                    self._selected_name = None
                    self._clear_draft()
            imgui.end_combo()

    # -----------------------------------------------------------------
    # ARAÇ ÇUBUĞU
    # -----------------------------------------------------------------
    def _draw_toolbar(self, container, container_attr: str):
        if imgui.button("+ New"):
            self._create_new()
        imgui.same_line()

        can_dup = self._selected_name in container

        # Duplicate
        if not can_dup:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1))
        if imgui.button("Duplicate") and can_dup:
            self._duplicate(container)
        if not can_dup:
            imgui.pop_style_color()
        imgui.same_line()

        # Delete
        if not can_dup:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1))
        if imgui.button("Delete") and can_dup:
            self._confirm_delete_name = self._selected_name
        if not can_dup:
            imgui.pop_style_color()
        imgui.same_line()

        # Search
        imgui.set_next_item_width(250)
        _, self._search = imgui.input_text("Search", self._search)
        imgui.same_line()

        # Select in Scene
        cls = DEFINITIONS[self._current_idx][0]
        if not can_dup:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1))
        if imgui.button("Select 🔍") and can_dup:
            self._select_by_definition(cls, self._selected_name, container_attr)
        if not can_dup:
            imgui.pop_style_color()
        if imgui.is_item_hovered() and not can_dup:
            imgui.set_tooltip(
                "Selects all scene elements using the selected record."
            )

    # -----------------------------------------------------------------
    # LİSTE
    # -----------------------------------------------------------------
    def _draw_list(self, container):
        imgui.text(f"Toplam: {len(container)}")
        imgui.begin_child(
            "def_list", imgui.ImVec2(0, 0), imgui.ChildFlags_.borders
        )
        q = self._search.lower()
        for name in sorted(container.keys()):
            if q and q not in name.lower():
                continue
            is_sel = (name == self._selected_name)
            clicked, _ = imgui.selectable(name, is_sel)
            if clicked:
                self._select_existing(container[name])
        imgui.end_child()

    # -----------------------------------------------------------------
    # EDİTÖR
    # -----------------------------------------------------------------
    def _draw_editor(self, cls, container, project):
        if self._draft is None:
            imgui.text_disabled("Soldan bir kayıt seçin veya + Yeni'ye basın.")
            return

        obj = self._draft
        hints = self._get_hints(type(obj))

        dirty = False
        for f in fields(obj):
            imgui.push_id(f"{type(obj).__name__}_{f.name}")
            try:
                if self._draw_field(obj, f, hints, project):
                    dirty = True
            finally:
                imgui.pop_id()

        # İsim validasyonu
        imgui.separator()
        name_key = _name_attr(obj)
        name_val = str(getattr(obj, name_key, "") or "")
        is_name_valid = bool(name_val.strip())
        if self._is_new and name_val in container:
            imgui.text_colored(imgui.ImVec4(1, 0.5, 0.3, 1.0), '⚠ Bu isimde kayıt zaten var!')
            is_name_valid = False

        # Aksiyonlar
        if not is_name_valid:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1))
        if imgui.button("Uygula", imgui.ImVec2(120, 0)) and is_name_valid:
            self._apply(container, project, name_key)
        if not is_name_valid:
            imgui.pop_style_color()
        imgui.same_line()
        if imgui.button("İptal", imgui.ImVec2(120, 0)):
            self._clear_draft()

    # -----------------------------------------------------------------
    # TEK FIELD EDITOR
    # -----------------------------------------------------------------
    def _draw_field(self, obj, f, hints, project) -> bool:
        name = f.name
        cur = getattr(obj, name, None)
        tp = hints.get(name, f.type)
        tp = _strip_optional(tp)

        imgui.set_next_item_width(300)
        try:
            return self._render_input(obj, name, tp, cur, project)
        except Exception as e:
            msg = f"{type(obj).__name__}.{name}: {type(e).__name__}: {e}"
            logger.debug(f"[DefinitionPanel] Render hata — {msg}")
            self._render_errors.add(msg)
            imgui.text_colored(imgui.ImVec4(1, 0.5, 0.3, 1.0), f'{name}: ⚠ render hata')
            if imgui.is_item_hovered():
                imgui.set_tooltip(msg)
            return False
    
    # -----------------------------------------------------------------
    # RENDER DISPATCH
    # -----------------------------------------------------------------
    def _render_input(self, obj, name, tp, cur, project) -> bool:
        # --- Section özel ---
        if isinstance(obj, Section):
            if name == "profile_type":
                return self._draw_section_type_editor(obj)
            if name == "profile_params":
                return self._draw_section_params(obj)
            if name == "sd_section":
                return self._draw_sd_section_summary(obj)
            if name == "rebar_column":
                return self._draw_rebar_dict(obj, name)
            if name == "rebar_beam":
                return self._draw_rebar_dict(obj, name)
            if name == "time_dependent":
                return self._draw_time_dependent(obj)

        # --- AreaSection özel ---
        if isinstance(obj, AreaSection):
            if name == "prop_type":
                return self._draw_areasec_prop_type(obj)
            if name == "thickness":
                return self._draw_float_named(obj, name, "Kalınlık", step=1.0)

        # --- ConstraintDefinition özel ---
        if isinstance(obj, ConstraintDefinition):
            if name == "constraint_type":
                return self._draw_constraint_type_editor(obj)
            if name in ("ux", "uy", "uz", "rx", "ry", "rz"):
                return self._draw_bool_named(obj, name, name.upper())
            if name in ("u1", "u2", "u3", "r1", "r2", "r3"):
                return self._draw_bool_named(obj, name, name.upper())

        # --- LinkProp özel ---
        if isinstance(obj, LinkProp):
            if name == "prop_type":
                return self._draw_linkprop_type_editor(obj)
            if name in ("DOF", "Fixed", "Ke", "Ce"):
                return self._draw_linkprop_dict(obj, name)

        # --- Material.name katalog ---
        if isinstance(obj, Material) and name == "name":
            return self._draw_material_name_with_catalog(obj)
        if isinstance(obj, LoadCombination) and name == "items":
            return self._draw_combination_items(obj)

        # --- Renk ---
        if name == "color" and get_origin(tp) is tuple and len(get_args(tp)) == 3:
            changed, new_color = color_edit3(name, cur or (0.8, 0.8, 0.8))
            if changed:
                setattr(obj, name, new_color)
                if hasattr(self, "_on_section_color_changed"):
                    self._on_section_color_changed(obj)
            return changed

        # --- Enum ---
        if _is_enum_type(tp):
            return self._render_enum(obj, name, tp, cur)

        # --- bool / int / float / str ---
        if tp is bool:
            c, v = imgui.checkbox(name, bool(cur))
            if c:
                setattr(obj, name, v); return True
            return False
        if tp is int:
            c, v = imgui.input_int(name, int(cur or 0))
            if c:
                setattr(obj, name, v); return True
            return False
        if tp is float:
            c, v = imgui.input_float(name, float(cur or 0.0))
            if c:
                setattr(obj, name, v); return True
            return False
        if tp is str:
            c, v = imgui.input_text(name, str(cur or ""))
            if c:
                setattr(obj, name, v); return True
            return False

        # --- dataclass referansı ---
        if isinstance(tp, type) and is_dataclass(tp):
            return self._render_dataclass_ref(obj, name, tp, cur, project)

        # --- tuple[float, ...] ---
        origin = get_origin(tp)
        args = get_args(tp)
        if origin is tuple and args and all(a is float for a in args):
            return self._render_float_tuple(obj, name, args, cur)

        self._mark_unsupported(obj, name, tp, cur)
        return False

    def _render_enum(self, obj, name, tp, cur) -> bool:
        values = list(tp)
        # 1) sap_label varsa onu kullan, yoksa value veya name
        labels = []
        for v in values:
            if hasattr(v, "sap_label"):
                labels.append(v.sap_label)          # "Steel", "Concrete", ...
            else:
                labels.append(str(getattr(v, "value", v.name)))
        try:
            cur_idx = values.index(cur)
        except (ValueError, TypeError):
            cur_idx = 0

        changed = False
        if imgui.begin_combo(name, labels[cur_idx]):
            for i, lbl in enumerate(labels):
                c, _ = imgui.selectable(lbl, i == cur_idx)
                if c and i != cur_idx:
                    setattr(obj, name, values[i])
                    changed = True
            imgui.end_combo()
        return changed

    def _render_dataclass_ref(self, obj, name, tp, cur, project) -> bool:
        ref = self._find_container_by_type(tp, project)
        if ref is None:
            imgui.text_disabled(f"{name}: <{tp.__name__} referansı>")
            return False

        cur_name = getattr(cur, "name", "") if cur else ""
        changed = False
        if imgui.begin_combo(name, cur_name or "<yok>"):
            if imgui.selectable("<yok>", not cur)[0]:
                setattr(obj, name, None)
                changed = True
            for k, v in sorted(ref.items()):
                c, _ = imgui.selectable(k, k == cur_name)
                if c:
                    setattr(obj, name, v)
                    changed = True
            imgui.end_combo()
        return changed

    def _render_float_tuple(self, obj, name, args, cur) -> bool:
        n = len(args)
        vals = list(cur) if cur else [0.0] * n
        if len(vals) != n:
            vals = [0.0] * n
        changed = False
        imgui.text(f"{name}:")
        for i in range(n):
            imgui.same_line()
            imgui.push_item_width(60)          # ← width yerine push_item_width
            c, v = imgui.input_float(f"##{name}_{i}", float(vals[i]))
            imgui.pop_item_width()
            if c:
                vals[i] = v
                changed = True
        if changed:
            setattr(obj, name, tuple(vals))
        return changed

    def _mark_unsupported(self, obj, name, tp, cur):
        display_tp = tp.__name__ if hasattr(tp, "__name__") else str(tp)
        display_val = type(cur).__name__ if cur is not None else "None"
        imgui.text_disabled(f"{name}: [{display_val}]")
        imgui.same_line()
        imgui.text_colored(imgui.ImVec4(1, 0.7, 0.3, 1.0), '(desteklenmiyor)')
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"Tip: {display_tp}\nDeğer: {repr(cur)[:200]}")
        self._unsupported_fields.add(f"{type(obj).__name__}.{name} ({display_tp})")

    # -----------------------------------------------------------------
    # ÖZEL: SECTION profile_type
    # -----------------------------------------------------------------
    def _draw_section_type_editor(self, section) -> bool:
        values = list(SectionType)
        labels = [st.value for st in values]
        try:
            cur_idx = values.index(section.profile_type)
        except (ValueError, TypeError):
            cur_idx = 0

        changed = False
        if imgui.begin_combo("profile_type", labels[cur_idx]):
            for i, lbl in enumerate(labels):
                c, _ = imgui.selectable(lbl, i == cur_idx)
                if c and i != cur_idx:
                    new_type = values[i]
                    # SD'ye geçerken sd_section korunmalı
                    if new_type == SectionType.SD:
                        if getattr(section, "sd_section", None) is None:
                            imgui.close_current_popup()
                            return False
                        # params temizlenmez
                    elif section.profile_type == SectionType.SD:
                        # SD'den çıkarken sd_section temizlenmeli mi? Şimdilik koru
                        pass
                    section.profile_type = new_type
                    if new_type not in (SectionType.SD,):
                        section.profile_params.clear()
                        section.profile_params.update(
                            _DEFAULT_SECTION_PARAMS.get(new_type, {}))
                    changed = True
            imgui.end_combo()

        if section.profile_type == SectionType.SD or getattr(section, "sd_section", None) is not None:
            return changed   # SD önizlemesi _draw_section_params'ta

        # ★ Önizleme — SD için sd_section, CUSTOM için h/b
        imgui.separator()
        try:
            draw_section_preview(section, avail_w=280, avail_h=200)
        except Exception as e:
            imgui.text_colored(imgui.ImVec4(1.0, 0.5, 0.3, 1.0), f"Preview error: {e}")
        return changed

    # -----------------------------------------------------------------
    # ÖZEL: SECTION profile_params
    # -----------------------------------------------------------------
    def _draw_section_params(self, section) -> bool:
        imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), 'Profil Parametreleri (mm)')
        p = section.profile_params
        st = section.profile_type
        changed = False

        def _float_field(key: str, label: str):
            nonlocal changed
            val = float(p.get(key, 0.0))
            imgui.set_next_item_width(200)
            c, v = imgui.input_float(label, val, 1.0, 10.0)
            if c:
                p[key] = v
                changed = True
        # ★ SD Section → özel gösterim
        if st == SectionType.SD or getattr(section, "sd_section", None) is not None:
            sd = section.sd_section
            if sd is None:
                imgui.text_disabled("SD Section has no geometry")
                return False

            imgui.text_colored(imgui.ImVec4(0.65, 0.8, 1.0, 1.0),
                            f"SD Section: {sd.design_type}")
            imgui.bullet_text(f"Shapes: {len(sd.shapes or [])}")
            total_pts = sum(len(sh.points) for sh in (sd.shapes or []))
            imgui.bullet_text(f"Points: {total_pts}")
            imgui.bullet_text(f"AxisAngle: {sd.axis_angle:g}°")
            imgui.bullet_text(f"nPolygon: {sd.n_polygon or len(sd.shapes or [])}")
            
            # Önizleme
            imgui.separator()
            try:
                self._draw_sd_preview(sd, avail_w=280, avail_h=200)
            except Exception as e:
                imgui.text_colored(imgui.ImVec4(1.0, 0.5, 0.3, 1.0), f"Preview error: {e}")

            return changed


        if st == SectionType.RECT:
            _float_field("h", "Yükseklik h")
            _float_field("b", "Genişlik b")
        elif st == SectionType.CIRCLE:
            _float_field("d", "Çap d")
        elif st == SectionType.PIPE:
            _float_field("d", "Dış çap")
            _float_field("t", "Kalınlık")
        elif st in (SectionType.BOX, SectionType.TUBE):
            _float_field("h", "Yükseklik")
            _float_field("b", "Genişlik")
            _float_field("t", "Kalınlık")
        elif st in (SectionType.I, SectionType.C, SectionType.CHANNEL):
            _float_field("h", "Yükseklik")
            _float_field("b", "Genişlik")
            _float_field("tw", "Gövde kalınlığı")
            _float_field("tf", "Başlık kalınlığı")
        elif st == SectionType.L:
            _float_field("h", "Bacak 1")
            _float_field("b", "Bacak 2")
            _float_field("t", "Kalınlık")
        elif st == SectionType.T:
            _float_field("h", "Yükseklik")
            _float_field("b", "Başlık genişliği")
            _float_field("tw", "Gövde kalınlığı")
            _float_field("tf", "Başlık kalınlığı")
        else:
            imgui.text_disabled(f"{st.value} — özel parametre editörü yok")

        # Eğer katalogdan gelmişse, gerçek değerler:
        if section.catalog_props:
            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.6, 0.8, 1.0, 1.0), f'Katalog: {section.catalog_source}')
            for key in ("A", "I33", "I22", "J", "Z33", "Z22"):
                v = section.catalog_props.get(key)
                if v is not None:
                    imgui.bullet_text(f"{key} = {v:.4g}")
        else:
            # Hesapla (eski davranış)
            A, I33, I22, J = self._compute_section_props(section)
            imgui.bullet_text(f"A   = {A:,.2f} mm²")
            imgui.bullet_text(f"I33 = {I33:.4e} mm⁴")
            imgui.bullet_text(f"I22 = {I22:.4e} mm⁴")
            imgui.bullet_text(f"J   = {J:.4e} mm⁴")

        # ★ SD varsa SD özet
        # if getattr(section, "sd_section", None) is not None:
        #     return changed
        
        # # ★ Önizleme geri gelsin
        # imgui.separator()
        # imgui.text_colored(imgui.ImVec4(0.6, 0.75, 1.0, 1.0), "Önizleme:")
        # try:
        #     draw_section_preview(section, avail_w=280, avail_h=200)
        # except Exception as e:
        #     imgui.text_colored(imgui.ImVec4(1.0, 0.5, 0.3, 1.0), f"Önizleme hatası: {e}")
            
        return changed

    def _compute_section_props(self, section):
        p = section.profile_params
        st = section.profile_type
        pi = 3.141592653589793
        try:
            h = float(p.get("h", 0.0))
            b = float(p.get("b", 0.0))
            d = float(p.get("d", 0.0))
            t = float(p.get("t", 0.0))
            if st == SectionType.RECT:
                return h * b, b * h**3 / 12, h * b**3 / 12, (b * h**3 + h * b**3) / 12
            if st == SectionType.CIRCLE:
                r = d / 2
                I = pi * r**4 / 4
                return pi * r**2, I, I, 2 * I
            if st == SectionType.PIPE:
                r, ri = d / 2, d / 2 - t
                ri = max(ri, 0)
                I = pi * (r**4 - ri**4) / 4
                return pi * (r**2 - ri**2), I, I, 2 * I
        except Exception:
            pass
        return 0.0, 0.0, 0.0, 0.0

    # -----------------------------------------------------------------
    # YARDIMCI: CONTAINER BULMA
    # -----------------------------------------------------------------
    def _find_container_by_type(self, cls, project) -> dict | None:
        if project is None:
            return None
        for d in DEFINITIONS:
            if d[0] is cls:
                return getattr(project, d[1], None)
        return None

    # -----------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------
    def _create_new(self):
        _, _, _, factory, _ = DEFINITIONS[self._current_idx]
        project = self.app.current_project
        try:
            obj = factory(project)
        except Exception:
            logger.exception(f"[DefinitionPanel] {DEFINITIONS[self._current_idx][0].__name__} oluşturulamadı")
            return
        self._draft = obj
        self._is_new = True
        self._selected_name = None

    def _duplicate(self, container):
        _, _, _, _, clone = DEFINITIONS[self._current_idx]
        src = container.get(self._selected_name)
        if not src:
            return
        dup = clone(src)
        key = _name_attr(dup)
        base = getattr(src, key, "KOPYA")
        new_name = _unique_name(container, f"{base}_copy")
        setattr(dup, key, new_name)
        self._draft = dup
        self._is_new = True
        self._selected_name = None

    def _select_existing(self, obj):
        _, _, _, _, clone = DEFINITIONS[self._current_idx]
        self._draft = clone(obj)
        self._selected_name = getattr(obj, _name_attr(obj), None)
        self._is_new = False

    def _apply(self, container, project, name_key):
        if self._draft is None:
            return
        new_name = getattr(self._draft, name_key, "")
        old_name = self._selected_name

        if old_name and old_name != new_name and old_name in container:
            del container[old_name]

        # Kaydetmeden önce: eski nesneyi al
        old_obj = container.get(new_name)

        container[new_name] = self._draft
        self._selected_name = new_name
        self._is_new = False

        # --- YENİ: Scene referanslarını güncelle ---
        if old_obj is not None and old_obj is not self._draft:
            self._relink_scene_refs(type(self._draft), new_name, self._draft, old_obj)

        if project.scene:
            project.scene.mark_dirty()

        if callable(self.on_changed):
            try:
                self.on_changed(DEFINITIONS[self._current_idx][1])
            except Exception:
                logger.exception("on_changed callback hata")

        logger.info(f"[DefinitionPanel] Kaydedildi: "
                    f"{DEFINITIONS[self._current_idx][1]}/{new_name}")

    def _draw_delete_confirm(self, container, project):
        if not self._confirm_delete_name:
            return
        imgui.open_popup("Silme Onayı")
        if imgui.begin_popup_modal("Silme Onayı", True)[0]:
            imgui.text(f"'{self._confirm_delete_name}' silinsin mi?")
            imgui.separator()
            if imgui.button("Evet", imgui.ImVec2(120, 0)):
                container.pop(self._confirm_delete_name, None)
                self._confirm_delete_name = None
                self._clear_draft()
                if project.scene:
                    project.scene.mark_dirty()
                if callable(self.on_changed):
                    try:
                        self.on_changed(DEFINITIONS[self._current_idx][1])
                    except Exception:
                        logger.exception("on_changed callback hata")
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Vazgeç", imgui.ImVec2(120, 0)):
                self._confirm_delete_name = None
                imgui.close_current_popup()
            imgui.end_popup()

    # -----------------------------------------------------------------
    # TANILAMA
    # -----------------------------------------------------------------
    def _draw_diagnostics(self):
        total = len(self._render_errors) + len(self._unsupported_fields)
        if total == 0:
            return
        imgui.separator()
        label = f"⚠ Desteklenmeyen / hatalı alanlar ({total})"
        if imgui.collapsing_header(label):
            if self._render_errors:
                imgui.text_colored(imgui.ImVec4(1, 0.5, 0.3, 1.0), 'Hatalar:')
                for msg in sorted(self._render_errors):
                    imgui.bullet_text(msg)
            if self._unsupported_fields:
                imgui.text_colored(imgui.ImVec4(1, 0.7, 0.3, 1.0), 'Desteklenmeyen tipler:')
                for msg in sorted(self._unsupported_fields):
                    imgui.bullet_text(msg)

    def _draw_material_name_with_catalog(self, material) -> bool:
        from data.materials_catalog import CATALOG_BY_MATTYPE, apply_catalog_to_material

        changed = False
        imgui.set_next_item_width(240)
        c, new_name = imgui.input_text("name", material.name)
        if c:
            material.name = new_name
            changed = True

        catalog = CATALOG_BY_MATTYPE.get(material.mat_type)
        if not catalog:
            return changed

        imgui.same_line()
        popup_id = f"##catalog_popup_{id(material)}"
        if imgui.button(f"Katalog ▾##catalog_btn_{id(material)}"):
            imgui.open_popup(popup_id)

        if imgui.begin_popup(popup_id):
            imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), catalog['label'])
            imgui.separator()
            for item in catalog["items"]:
                is_current = (material.name == item)
                clicked, _ = imgui.selectable(item, is_current)
                if clicked:
                    try:
                        apply_catalog_to_material(material, item, thickness_mm=16.0)
                        material.name = item
                        changed = True
                    except Exception:
                        logger.exception(f"Katalog hatası: {item}")
                    imgui.close_current_popup()
                    break
            imgui.end_popup()

        return changed

    def _draw_section_catalog_popup(self, section) -> bool:
        """Kesit kataloğu popup — arama + aile filtresi."""
        popup_id = f"##sec_cat_popup_{id(section)}"
        if not imgui.begin_popup(popup_id):
            return False

        catalog = getattr(self.app, "section_catalog", {})
        if not catalog:
            imgui.text_colored(imgui.ImVec4(1, 0.6, 0.3, 1.0), 'Kesit kataloğu boş.')
            imgui.end_popup()
            return False

        changed = False

        # Arama state
        cur_q = self._catalog_search.get(id(section), "")
        imgui.set_next_item_width(280)
        _, new_q = imgui.input_text(f"Ara##sec_cat_search_{id(section)}", cur_q)
        if new_q != cur_q:
            self._catalog_search[id(section)] = new_q
            cur_q = new_q

        # Aile filtresi
        family_filter = self._catalog_search.get(f"fam_{id(section)}", "Tümü")
        imgui.same_line()
        imgui.set_next_item_width(100)
        if imgui.begin_combo(f"Aile##fam_{id(section)}", family_filter):
            for fam in ("Tümü", "W", "C", "L", "P"):
                c, _ = imgui.selectable(fam, fam == family_filter)
                if c:
                    self._catalog_search[f"fam_{id(section)}"] = fam
                    family_filter = fam
            imgui.end_combo()

        imgui.separator()

        # Listele
        q_lower = cur_q.lower()
        displayed = 0
        for name, cat_sec in sorted(catalog.items()):
            if q_lower and q_lower not in name.lower():
                continue
            # Aile filtresi: catalog_source sonunda family var
            fam = cat_sec.catalog_source.split("-")[-1].strip()
            if family_filter != "Tümü" and fam != family_filter:
                continue

            # Özet
            p = cat_sec.profile_params
            if cat_sec.profile_type == SectionType.PIPE:
                summary = f"{name}  (Ø{p.get('d', 0):.0f}×{p.get('t', 0):.1f})"
            else:
                summary = (f"{name}  ({p.get('h', 0):.0f}×{p.get('b', 0):.0f}"
                        f"×{p.get('tf', 0):.1f}×{p.get('tw', 0):.1f})")

            is_current = (section.name == name)
            clicked, _ = imgui.selectable(summary, is_current)
            if clicked:
                # Projeye kopyala — referans değil!
                section.name = cat_sec.name
                section.profile_type = cat_sec.profile_type
                section.profile_params = dict(cat_sec.profile_params)
                section.catalog_props = dict(cat_sec.catalog_props)
                section.catalog_source = cat_sec.catalog_source
                changed = True
                imgui.close_current_popup()
            displayed += 1
            if displayed >= 200:
                imgui.text_disabled("... (arama daraltın)")
                break

        if displayed == 0:
            imgui.text_disabled("Eşleşen kesit yok")

        imgui.end_popup()
        return changed

    # -----------------------------------------------------------------
    # ÖZEL: LINK PROPERTY
    # -----------------------------------------------------------------
    def _draw_linkprop_type_editor(self, prop) -> bool:
        """prop_type combo — Linear, Gap, Hook vb."""
        values = list(LinkPropType)
        labels = [pt.name for pt in values]
        try:
            cur_idx = values.index(prop.prop_type)
        except (ValueError, TypeError):
            cur_idx = 0

        changed = False
        if imgui.begin_combo("prop_type", labels[cur_idx]):
            for i, lbl in enumerate(labels):
                c, _ = imgui.selectable(lbl, i == cur_idx)
                if c and i != cur_idx:
                    prop.prop_type = values[i]
                    changed = True
            imgui.end_combo()
        return changed


    def _draw_linkprop_dict(self, prop, name: str) -> bool:
        """
        DOF: {'U1': bool, ...}    → checkbox grid
        Ke / Ce: {'U1': float, ...} → input_float grid
        Fixed: {dof: bool}          → checkbox grid
        """
        cur = getattr(prop, name, None)
        if not isinstance(cur, dict):
            imgui.text_disabled(f"{name}: <dict değil>")
            return False

        dofs = ["U1", "U2", "U3", "R1", "R2", "R3"]
        changed = False

        imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), name)

        if name in ("DOF", "Fixed"):
            # 6 DOF checkbox yan yana
            for i, dof in enumerate(dofs):
                if i > 0:
                    imgui.same_line()
                val = bool(cur.get(dof, False))
                c, v = imgui.checkbox(f"{dof}##{name}_{dof}", val)
                if c:
                    cur[dof] = v
                    changed = True

        elif name in ("Ke", "Ce"):
            # 3 satır × 2 sütun grid
            for row_start in (0, 2, 4):
                for col in range(2):
                    dof = dofs[row_start + col]
                    val = float(cur.get(dof, 0.0))
                    imgui.set_next_item_width(120)
                    c, v = imgui.input_float(f"{dof}##{name}_{dof}", val, 1.0, 100.0)
                    if c:
                        cur[dof] = v
                        changed = True
                    if col == 0:
                        imgui.same_line()

        return changed

    def _select_by_section(self, section_name: str, target: str = "frames"):
        """
        Belirli bir Section'ı kullanan Frame veya Area'ları seç.
        
        Args:
            section_name: Seçilecek kesitin adı
            target: "frames" | "areas"
        """
        project = getattr(self.app, "current_project", None)
        if project is None or project.scene is None:
            return
        scn = project.scene
        scn.clear_selections()

        count = 0

        if target == "frames":
            for frame in scn.frames.values():
                sec = getattr(frame, "section", None)
                if sec is not None and getattr(sec, "name", None) == section_name:
                    frame.is_selected = True
                    count += 1
        elif target == "areas":
            for area in scn.areas.values():
                if getattr(area, "section_name", "") == section_name:
                    area.is_selected = True
                    count += 1

        self._notify_selection_changed(scn)
        logger.info(
            f"[Filter] Section '{section_name}' → "
            f"{count} {target} seçildi"
        )


    def _select_by_definition(self, cls, name: str, container_attr: str):
        """Bir tanımı kullanan tüm sahne elemanlarını seç."""
        project = getattr(self.app, "current_project", None)
        if project is None or project.scene is None:
            return
        
        scn = project.scene
        scn.clear_selections()
        
        n_frames = n_areas = n_links = n_nodes = 0
        
        if cls is Section:
            for f in scn.frames.values():
                if f.section and getattr(f.section, "name", None) == name:
                    f.is_selected = True
                    n_frames += 1
            for a in scn.areas.values():
                if getattr(a, "section_name", "") == name:
                    a.is_selected = True
                    n_areas += 1
        
        elif cls is Material:
            for f in scn.frames.values():
                sec = f.section
                mat = getattr(sec, "material", None) if sec else None
                if mat and getattr(mat, "name", None) == name:
                    f.is_selected = True
                    n_frames += 1
            for a in scn.areas.values():
                mat = getattr(a, "material", None)
                if mat and getattr(mat, "name", None) == name:
                    a.is_selected = True
                    n_areas += 1
            for a in scn.areas.values():
                sec = getattr(a, "area_section", None)
                mat = getattr(sec, "material", None) if sec else None
                if mat and getattr(mat, "name", None) == name:
                    a.is_selected = True
                    n_areas += 1
        
        elif cls is AreaSection:
            for a in scn.areas.values():
                if getattr(a, "area_section", None) and a.area_section.name == name:
                    a.is_selected = True
                    n_areas += 1
                elif getattr(a, "section_name", "") == name:
                    a.is_selected = True
                    n_areas += 1
        
        elif cls is LinkProp:
            for l in scn.links.values():
                if getattr(l, "propname", "") == name:
                    l.is_selected = True
                    n_links += 1
        
        elif cls is LoadPattern:
            # Yük pattern'lı frame'ler + area'lar + node'lar
            for f in scn.frames.values():
                if any(getattr(load, "pattern_name", "") == name
                    for load in f.dist_loads):
                    f.is_selected = True
                    n_frames += 1
            for a in scn.areas.values():
                for attr in ("uniform_loads", "uniform_to_frame_loads"):
                    if any(getattr(load, "pattern_name", "") == name
                        for load in getattr(a, attr, [])):
                        a.is_selected = True
                        n_areas += 1
                        break
            for n in scn.nodes.values():
                if any(getattr(load, "pattern_name", "") == name
                    for load in n.loads):
                    n.is_selected = True
                    n_nodes += 1
        
        # ConstraintDefinition → node'lar
        elif cls is ConstraintDefinition:
            for n in scn.nodes.values():
                if getattr(n, "constraint_name", None) == name:
                    n.is_selected = True
                    n_nodes += 1
        
        self._notify_selection_changed(scn)
        logger.info(
            "[Filter] %s '%s' → %d frame, %d area, %d link, %d node",
            cls.__name__, name, n_frames, n_areas, n_links, n_nodes,
        )


    def _notify_selection_changed(self, scn):
        """Seçim değişikliğini CadApp'e bildir (renderer + inspector güncellensin)."""
        if not self.app or not hasattr(self.app, "_on_selection_changed"):
            return
        try:
            self.app._on_selection_changed(scn.get_selected())
        except Exception:
            logger.exception("on_selection_changed çağrısı hatası")

    def _on_section_color_changed(self, section):
        app = getattr(self, "app", None)
        eng = getattr(app, "engine", None) if app else None
        scn = getattr(eng, "scene", None) if eng else None
        if not scn or not eng.renderer:
            return

        target_name = getattr(section, "name", None)
        if not target_name:
            return

        n_dirty = 0
        for f in scn.frames.values():
            sec = getattr(f, "section", None)
            if sec is None:
                continue
            # isim eşleşmesi (kopya olsa bile çalışır)
            if sec is section or sec.name == target_name:
                f.needs_update = True
                n_dirty += 1

        if n_dirty:
            eng.renderer.update_dirty()

        logger.info("[DefPanel] '%s' → %d frame güncellendi", target_name, n_dirty)

    def _relink_scene_refs(self, cls, name, new_obj, old_obj):
        """Kaydedilen nesneyi scene'deki elementlere yeniden bağla."""
        app = getattr(self, "app", None)
        eng = getattr(app, "engine", None) if app else None
        scn = getattr(eng, "scene", None) if eng else None
        if not scn:
            return

        n_frames = n_areas = 0
        if cls is Section:
            for f in scn.frames.values():
                if getattr(f, "section", None) is old_obj:
                    f.section = new_obj
                    f.needs_update = True
                    n_frames += 1
            for a in scn.areas.values():
                if getattr(a, "section", None) is old_obj:
                    a.section = new_obj
                    a.needs_update = True
                    n_areas += 1
        elif cls is Material:
            # Material → section.material ilişkisi
            project = getattr(app, "current_project", None)
            if project:
                for sec in project.sections.values():
                    if getattr(sec, "material", None) is old_obj:
                        sec.material = new_obj

        if eng.renderer and (n_frames or n_areas):
            eng.renderer.update_dirty()

        logger.info("[DefPanel] Referanslar güncellendi: %d frame, %d area",
                    n_frames, n_areas)

    # ---------------------------------------------------------------------------
    # SD SECTION ÖZETİ (salt okunur)
    # ---------------------------------------------------------------------------
    def _draw_sd_section_summary(self, section) -> bool:
        sd = getattr(section, "sd_section", None)
        if sd is None:
            imgui.text_disabled("SD Section tanımı yok")
            return False

        n_shapes = len(sd.shapes or [])
        n_pts = sum(len(sh.points) for sh in (sd.shapes or []))
        imgui.text_colored(
            imgui.ImVec4(0.65, 0.8, 1.0, 1.0),
            f"SD: {n_shapes} shape, {n_pts} pt — {sd.design_type}",
        )
        if imgui.is_item_hovered():
            lines = [
                f"Design: {sd.design_type}",
                f"nPolygon: {sd.n_polygon}",
                f"AxisAngle: {sd.axis_angle:g}°",
                f"Mesh: abs={sd.mesh_sz_abs:g} rel={sd.mesh_sz_rel:g}",
            ]
            for i, sh in enumerate(sd.shapes or []):
                lines.append(f"Shape[{i}]: {sh.name} ({len(sh.points)} pt)")
            imgui.set_tooltip("\n".join(lines))
        return False


    # ---------------------------------------------------------------------------
    # REBAR DICT (rebar_column / rebar_beam)
    # ---------------------------------------------------------------------------
    def _draw_rebar_dict(self, section, name: str) -> bool:
        d = getattr(section, name, None)
        if not isinstance(d, dict):
            imgui.text_disabled(f"{name}: <dict değil>")
            return False

        if not d:
            imgui.text_disabled(f"{name}: <boş>")
            if imgui.button(f"Yeni {name}"):
                setattr(section, name, {})
                return True
            return False

        changed = False
        imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), name)
        imgui.indent(12)

        for k in sorted(d.keys()):
            v = d[k]
            imgui.set_next_item_width(200)
            if isinstance(v, bool):
                c, nv = imgui.checkbox(k, v)
            elif isinstance(v, int):
                c, nv = imgui.input_int(k, v)
            elif isinstance(v, float):
                c, nv = imgui.input_float(k, v)
            elif isinstance(v, str):
                c, nv = imgui.input_text(k, v)
            else:
                imgui.text_disabled(f"{k}: {v!r}")
                continue
            if c:
                d[k] = nv
                changed = True

        imgui.unindent(12)
        return changed


    # ---------------------------------------------------------------------------
    # TIME DEPENDENT
    # ---------------------------------------------------------------------------
    def _draw_time_dependent(self, section) -> bool:
        d = getattr(section, "time_dependent", None)
        if not isinstance(d, dict):
            imgui.text_disabled("time_dependent: <dict değil>")
            return False

        if not d:
            imgui.text_disabled("time_dependent: <boş>")
            if imgui.button("Yeni time_dependent"):
                setattr(section, "time_dependent", {"type_size": "Auto", "auto_sf_size": 1.0})
                return True
            return False

        changed = False
        imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), "time_dependent")
        imgui.indent(12)
        for k in sorted(d.keys()):
            v = d[k]
            imgui.set_next_item_width(200)
            if isinstance(v, str):
                c, nv = imgui.input_text(k, v)
            elif isinstance(v, (int, float)):
                c, nv = imgui.input_float(k, float(v))
                nv = type(v)(nv)
            else:
                imgui.text_disabled(f"{k}: {v!r}")
                continue
            if c:
                d[k] = nv
                changed = True
        imgui.unindent(12)
        return changed


    # ---------------------------------------------------------------------------
    # AREA SECTION PROP TYPE
    # ---------------------------------------------------------------------------
    def _draw_areasec_prop_type(self, sec) -> bool:
        from data.enums import PropAreaType
        values = list(PropAreaType)
        labels = [getattr(pt, "name", str(pt)) for pt in values]
        try:
            cur_idx = values.index(sec.prop_type)
        except (ValueError, TypeError):
            cur_idx = 0
        changed = False
        if imgui.begin_combo("prop_type", labels[cur_idx]):
            for i, lbl in enumerate(labels):
                c, _ = imgui.selectable(lbl, i == cur_idx)
                if c and i != cur_idx:
                    sec.prop_type = values[i]
                    changed = True
            imgui.end_combo()
        return changed


    # ---------------------------------------------------------------------------
    # CONSTRAINT TYPE
    # ---------------------------------------------------------------------------
    def _draw_constraint_type_editor(self, cd) -> bool:
        values = list(ConstraintType)
        labels = [getattr(ct, "name", str(ct)) for ct in values]
        try:
            cur_idx = values.index(cd.constraint_type) if cd.constraint_type else 0
        except (ValueError, TypeError):
            cur_idx = 0
        changed = False
        if imgui.begin_combo("constraint_type", labels[cur_idx]):
            for i, lbl in enumerate(labels):
                c, _ = imgui.selectable(lbl, i == cur_idx)
                if c and i != cur_idx:
                    cd.constraint_type = values[i]
                    changed = True
            imgui.end_combo()
        return changed


    # ---------------------------------------------------------------------------
    # BASİT YARDIMCILAR
    # ---------------------------------------------------------------------------
    def _draw_float_named(self, obj, name: str, label: str, step: float = 1.0) -> bool:
        cur = float(getattr(obj, name, 0.0) or 0.0)
        imgui.set_next_item_width(200)
        c, v = imgui.input_float(label, cur, step, 10.0)
        if c:
            setattr(obj, name, float(v))
            return True
        return False


    def _draw_bool_named(self, obj, name: str, label: str) -> bool:
        cur = bool(getattr(obj, name, False))
        imgui.set_next_item_width(200)
        c, v = imgui.checkbox(label, cur)
        if c:
            setattr(obj, name, bool(v))
            return True
        return False

    def _draw_combination_items(self, combo) -> bool:
        """LoadCombination.items — ComboItem listesi editörü."""
        items = getattr(combo, "items", None)
        if not isinstance(items, list):
            imgui.text_disabled("items: <liste değil>")
            return False

        changed = False
        imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), "Items")
        imgui.indent(12)

        # Mevcut item'lar
        to_delete = None
        for i, it in enumerate(items):
            imgui.push_id(f"combo_item_{i}")
            try:
                imgui.text(f"[{i}]")
                imgui.same_line()
                imgui.set_next_item_width(200)
                c1, case_name = imgui.input_text(
                    "Case/Pat", getattr(it, "case_or_pattern_name", ""))
                if c1:
                    it.case_or_pattern_name = case_name
                    changed = True
                imgui.same_line()
                imgui.set_next_item_width(100)
                c2, sf = imgui.input_float(
                    "SF", float(getattr(it, "scale_factor", 1.0)), 0.1, 0.01)
                if c2:
                    it.scale_factor = sf
                    changed = True
                imgui.same_line()
                if imgui.small_button("X"):
                    to_delete = i
            finally:
                imgui.pop_id()

        if to_delete is not None:
            del items[to_delete]
            changed = True

        # Yeni ekle
        if imgui.button("+ Add Item"):
            from domain.definition import ComboItem
            items.append(ComboItem(case_or_pattern_name="", scale_factor=1.0))
            changed = True

        imgui.unindent(12)
        return changed

    # ---------------------------------------------------------------------------
    # SD SECTION ÖNİZLEME (imgui draw list, earcut ile üçgenleme)
    # ---------------------------------------------------------------------------
    def _draw_sd_preview(self, sd, avail_w: float = 280, avail_h: float = 200):
        """SD polygon'ı earcut ile üçgenleyip imgui draw list ile çiz."""
        import numpy as np
        import mapbox_earcut as earcut

        if not sd or not sd.shapes:
            imgui.text_disabled("SD Section (no shapes)")
            return

        all_pts = [(float(p.x), float(p.y)) for sh in sd.shapes for p in sh.points]
        if len(all_pts) < 3:
            imgui.text_disabled("SD Section (no points)")
            return

        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max(max_x - min_x, 1e-6)
        h = max(max_y - min_y, 1e-6)
        scale = min(avail_w / w, avail_h / h) * 0.85

        draw_list = imgui.get_window_draw_list()
        origin = imgui.get_cursor_screen_pos()
        cx = origin.x + (avail_w - w * scale) / 2
        cy = origin.y + (avail_h - h * scale) / 2

        def to_screen(x, y):
            return imgui.ImVec2(
                cx + (x - min_x) * scale,
                cy + (max_y - y) * scale,
            )

        for sh in sd.shapes:
            pts = [(float(p.x), float(p.y)) for p in sh.points]
            n = len(pts)
            if n < 3:
                continue

            tri_idx = []
            try:
                coords = np.array(pts, dtype=np.float32)
                rings = np.array([n], dtype=np.uint32)
                tri_idx = earcut.triangulate_float32(coords, rings).tolist()
            except Exception as e:
                logger.warning("[SD preview] earcut hatası: %s", e)

            r, g, b = sh.fill_color[:3] if sh.fill_color else (0.7, 0.7, 0.7)
            fill_col = imgui.get_color_u32(imgui.ImVec4(r, g, b, 0.35))

            for i in range(0, len(tri_idx) - 2, 3):
                p0 = to_screen(*pts[tri_idx[i]])
                p1 = to_screen(*pts[tri_idx[i + 1]])
                p2 = to_screen(*pts[tri_idx[i + 2]])
                draw_list.add_triangle_filled(p0, p1, p2, fill_col)

            edge_col = imgui.get_color_u32(imgui.ImVec4(r, g, b, 0.95))
            for i in range(n):
                draw_list.add_line(
                    to_screen(*pts[i]),
                    to_screen(*pts[(i + 1) % n]),
                    edge_col, 2.0,
                )

        imgui.dummy(imgui.ImVec2(avail_w, avail_h))