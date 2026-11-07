# inspector/window.py
from typing import Any

from imgui_bundle import imgui

from core.selection_policy import SelectionMode
from inspector.controller import InspectorController
from inspector.fields import inspector_fields
from inspector.topbar import TopBar
from inspector.widgets import (
    _col, _copy_to_clipboard, _element_label, _matches,
    _parse_filter, _scene_groups, _unique_id, draw_field_row,
)
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class InspectorWindow:

    LEFT_PANEL_MIN = 140.0
    LEFT_PANEL_MAX = 260.0

    def __init__(self, scene=None, catalog=None, standalone=False):
        self.scene = scene
        self.math_model = scene
        self.catalog = catalog
        self.controller = InspectorController(scene=scene, catalog=catalog)

        self.visible = False
        self.standalone = standalone
        self._first_open = True

        self._left_width = 180.0
        self._left_open = True
        self._tree_open_groups: set = set()
        self._tree_filter = ""
        self._scroll_to_id = None

        self.app = None
        self.topbar = TopBar(self)

    # ------------------------------------------------------------------
    def set_context(self, ctx: dict):
        for k, v in ctx.items():
            setattr(self, k, v)
        self.controller.scene = getattr(self, "math_model", None)

    def open(self):
        self.visible = True
        self._first_open = True

    def close(self):
        self.visible = False

    def toggle(self):
        self.visible = not self.visible

    def set_scene(self, scene):
        self.scene = scene
        self.math_model = scene
        self.controller.scene = scene
        self._tree_filter = ""
        self._tree_open_groups.clear()
        self._scroll_to_id = None
        self.set_selection([])
        self.refresh()

    def set_project(self, project):
        self.scene = project.scene
        self.math_model = project.math_model
        self.controller.scene = project.math_model
        self._tree_filter = ""
        self._tree_open_groups.clear()
        self._scroll_to_id = None
        self.set_selection([])
        self.refresh()

    def set_catalog(self, catalog):
        self.catalog = catalog
        self.controller.catalog = catalog

    def set_selection(self, elements: list):
        elements = list(elements or [])
        self.controller.set_selection(elements)
        for el in elements:
            self._tree_open_groups.add(type(el).__name__)
        self._scroll_to_id = _unique_id(elements[0]) if elements else None
        self._sync_scene_selection(elements)

    def _sync_scene_selection(self, elements):
        app = getattr(self, "app", None)
        sel_mgr = getattr(getattr(app, "engine", None), "sel_mgr", None) if app else None
        if sel_mgr is None:
            return
        current = set(getattr(sel_mgr, "selected", set()) or set())
        target = {_unique_id(e) for e in (elements or [])}
        if current == target:
            return
        if not elements:
            sel_mgr.clear()
        elif len(elements) == 1:
            sel_mgr.select(elements[0], additive=False)
        else:
            sel_mgr.select_multiple(elements, mode=SelectionMode.REPLACE)

    def refresh(self):
        self.controller.refresh_from_scene()

    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return
        if self._first_open and not self.standalone:
            imgui.set_next_window_pos(imgui.ImVec2(850, 100),
                                       imgui.Cond_.first_use_ever)
            imgui.set_next_window_size(imgui.ImVec2(620, 620),
                                        imgui.Cond_.first_use_ever)
            self._first_open = False

        expanded, opened = imgui.begin("Inspector", True)
        try:
            if not opened:
                self.close()
                return
            self._draw_body()
        finally:
            imgui.end()

    def _draw_body(self):
        self.topbar.draw()
        imgui.separator()

        imgui.begin_child("insp_body", imgui.ImVec2(0, 0))
        try:
            if self._left_open:
                imgui.begin_child("insp_left",
                                   imgui.ImVec2(self._left_width, 0))
                try:
                    self._draw_tree()
                finally:
                    imgui.end_child()
                imgui.same_line()

            imgui.begin_child("insp_right", imgui.ImVec2(0, 0))
            try:
                self._draw_form()
            finally:
                imgui.end_child()
        finally:
            imgui.end_child()

    # ------------------------------------------------------------------
    def _draw_tree(self):
        imgui.text_disabled("Elements")
        imgui.separator()

        if self.scene is None:
            imgui.text_colored(_col(0.6, 0.4, 0.4), "scene yok")
            return

        imgui.set_next_item_width(-1)
        changed, new_filter = imgui.input_text("##filter", self._tree_filter)
        if changed:
            self._tree_filter = new_filter

        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "Filtre:\n"
                "  n123        → label içerir\n"
                "  node:n12    → Node türünde\n"
                "  #123        → id\n"
                "  frame:      → tüm frame"
            )

        if (imgui.is_window_focused()
                and imgui.get_io().key_ctrl
                and imgui.is_key_pressed(imgui.Key.f)):
            imgui.set_keyboard_focus_here()

        flt = (self._tree_filter or "").strip().lower()

        if imgui.is_item_focused() and imgui.is_key_pressed(imgui.Key.enter):
            self._select_first_match(flt)

        self._draw_filtered_groups(flt, bool(flt))

    def _select_first_match(self, flt: str):
        type_hint, id_hint, text_hint = _parse_filter(flt)
        for type_name, elements in _scene_groups(
            self.scene, self.math_model,
        ):
            if type_hint and type_name.lower() != type_hint:
                continue
            for el in elements:
                if _matches(el, type_name, text_hint, id_hint):
                    self.set_selection([el])
                    return

    def _draw_filtered_groups(self, flt: str, force_open: bool):
        type_hint, id_hint, text_hint = _parse_filter(flt)

        for type_name, elements in _scene_groups(
            self.scene, self.math_model,
        ):
            if type_hint and type_name.lower() != type_hint:
                continue
            if not elements:
                continue

            filtered = [e for e in elements
                        if _matches(e, type_name, text_hint, id_hint)]
            if not filtered:
                continue

            header = f"{type_name}  ({len(filtered)}/{len(elements)})##tree_{type_name}"
            if force_open:
                imgui.set_next_item_open(True, imgui.Cond_.once)
            if not imgui.collapsing_header(header):
                continue

            imgui.indent(12)
            for el in filtered[:200]:
                label = _element_label(el)
                is_selected = el in self.controller.objects
                clicked = imgui.selectable(
                    f"{label}##tree_{id(el)}", is_selected,
                )[0]

                if imgui.begin_popup_context_item(f"ctx_{id(el)}"):
                    if imgui.menu_item("Sahneye odakla")[0]:
                        self._focus_in_scene(el)
                    if imgui.menu_item("ID kopyala")[0]:
                        _copy_to_clipboard(str(_unique_id(el)))
                    imgui.separator()
                    if imgui.menu_item("Sadece bunu seç")[0]:
                        self._select_via_scene(el)
                    imgui.end_popup()

                if self._scroll_to_id == _unique_id(el):
                    imgui.set_scroll_here_y(0.3)
                    self._scroll_to_id = None

                if clicked:
                    self._select_via_scene(el)

            if len(filtered) > 200:
                imgui.text_colored(_col(0.6, 0.6, 0.6),
                                    f"...ve {len(filtered) - 200} tane daha")
            imgui.unindent(12)

    def _select_via_scene(self, el):
        if el is None or not hasattr(el, "unique_id"):
            return
        app = getattr(self, "app", None)
        sel_mgr = getattr(getattr(app, "engine", None), "sel_mgr", None) if app else None
        if sel_mgr and hasattr(sel_mgr, "select_only"):
            sel_mgr.select_only(el)
            return
        self.set_selection([el])

    def _focus_in_scene(self, el):
        app = getattr(self, "app", None)
        if app is None:
            return
        if hasattr(app, "focus_element"):
            app.focus_element(el)
        elif getattr(app, "engine", None) and app.engine.sel_mgr:
            app.engine.sel_mgr.select_only(el)

    # ------------------------------------------------------------------
    def _draw_form(self):
        c = self.controller

        if not c.objects:
            imgui.spacing()
            imgui.text_colored(_col(0.5, 0.5, 0.5), "Eleman seçilmedi")
            return

        if len(c.type_counts) > 1:
            self._draw_type_selector(c)

        act = c.active_objects
        if not act:
            imgui.text_colored(_col(0.7, 0.7, 0.5), "Tip seç")
            return

        t = c.common_type
        if t is None:
            imgui.text_colored(_col(0.85, 0.75, 0.35), "Farklı tipler")
            return

        if len(act) == 1:
            imgui.text_colored(_col(0.8, 0.8, 0.4), t)
            imgui.same_line()
            imgui.text_disabled(_element_label(act[0]))
        else:
            imgui.text_colored(_col(0.8, 0.8, 0.4), f"{t} × {len(act)}")

        imgui.separator()

        fields = inspector_fields(act[0])
        if not fields:
            imgui.text_disabled("(görünür alan yok)")
            return

        table_flags = (imgui.TableFlags_.sizing_stretch_prop
                       | imgui.TableFlags_.borders_inner_h
                       | imgui.TableFlags_.no_saved_settings)
        if imgui.begin_table("##props", 2, table_flags):
            imgui.table_setup_column("Key",
                                       imgui.TableColumnFlags_.width_fixed, 130.0)
            imgui.table_setup_column("Value",
                                       imgui.TableColumnFlags_.width_stretch)
            for key, _ in fields:
                draw_field_row(act, key, self.catalog)
            imgui.end_table()

    def _draw_type_selector(self, c):
        counts = c.type_counts
        types = sorted(counts.keys())

        imgui.text_colored(_col(0.7, 0.85, 1.0), "Tip")
        imgui.same_line(80)
        imgui.set_next_item_width(-1)

        labels = [f"{t}  ({counts[t]})" for t in types]
        cur_idx = types.index(c.filter_type) if c.filter_type in types else -1

        if cur_idx < 0:
            imgui.text_disabled("(seç)")
            if imgui.is_item_clicked():
                imgui.open_popup("##type_popup")
            if imgui.begin_popup("##type_popup"):
                for t in types:
                    if imgui.selectable(f"{t}  ({counts[t]})")[0]:
                        c.set_filter_type(t)
                        imgui.close_current_popup()
                imgui.end_popup()
        else:
            changed, new_idx = imgui.combo("##type_filter", cur_idx, labels)
            if changed and 0 <= new_idx < len(types):
                c.set_filter_type(types[new_idx])

        imgui.separator()