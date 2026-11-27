# inspector/window.py
from __future__ import annotations

from typing import Any

from imgui_bundle import imgui

from core.selection_policy import SelectionMode
from inspector.controller import InspectorController
from inspector.schemas import CatalogAdapter
from inspector.topbar import TopBar
from inspector.widgets import (
    _col, _copy_to_clipboard, _element_label, _matches,
    _parse_filter, _scene_groups, _unique_id, draw_schema_field,
)
from ui.base.panel_base import Category
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class InspectorWindow:

    __abstract__ = False
    panel_name = "inspector_panel"
    title = "Inspector"
    category = Category.MANAGEMENT
    quick = True
    menu_label = "Inspector"
    icon = "log-in"
    shortcut = "F10"
    context = ()

    LEFT_PANEL_MIN = 140.0
    LEFT_PANEL_MAX = 260.0

    # ------------------------------------------------------------------
    # Kurulum
    # ------------------------------------------------------------------
    def __init__(self, app=None, *, standalone: bool = False):
        self.app = app
        self.standalone = standalone
        self.visible = False
        self._first_open = True
        self._syncing = False

        # UI state
        self._left_width = 180.0
        self._left_open = True
        self._tree_open_groups: set = set()
        self._tree_filter = ""
        self._scroll_to_id = None

        # Tüm bağımlılıklar app üzerinden
        self.controller = InspectorController(on_applied=self._on_applied)
        self._bind_app()

        self.topbar = TopBar(self)

    # ------------------------------------------------------------------
    # app binding
    # ------------------------------------------------------------------
    def _bind_app(self) -> None:
        """app'ten scene/catalog/selection'ı çek ve controller'a bağla."""
        app = self.app
        if app is None:
            return
        self.controller.scene = self._resolve_math_model()
        self.controller.catalog = self._resolve_catalog()

    def _resolve_project(self):
        ps = getattr(self.app, "project_service", None) if self.app else None
        return getattr(ps, "project", None) if ps else None

    def _resolve_math_model(self):
        project = self._resolve_project()
        if project is None:
            return None
        return getattr(project, "math_model", None) or getattr(project, "scene", None)

    def _resolve_scene(self):
        project = self._resolve_project()
        return getattr(project, "scene", None) if project else None

    def _resolve_catalog(self):
        """app.section_catalog dict → Catalog protokolü (adapter)."""
        app = self.app
        if app is None:
            return None
        # 1) app zaten protokol implement eden bir catalog sunuyorsa onu kullan
        cat = getattr(app, "catalog", None)
        if cat is not None and hasattr(cat, "list_sections"):
            return cat
        # 2) ui_host tarafından atanmış adapter varsa onu koru
        existing = getattr(self.controller, "catalog", None)
        if existing is not None and hasattr(existing, "list_sections"):
            return existing
        # 3) section_catalog dict → adapter
        raw = getattr(app, "section_catalog", None)
        if raw is None:
            return None
        if hasattr(raw, "list_sections"):
            return raw
        return CatalogAdapter(app)

    def _resolve_selection(self) -> list:
        engine = getattr(self.app, "engine", None) if self.app else None
        sel_mgr = getattr(engine, "sel_mgr", None) if engine else None
        if sel_mgr is None:
            return []
        getter = getattr(sel_mgr, "get_selected", None)
        if callable(getter):
            try:
                return list(getter())
            except Exception:
                return []
        return list(getattr(sel_mgr, "selected", set()) or set())

    # ------------------------------------------------------------------
    # Panel API (registry & command layer uyumu)
    # ------------------------------------------------------------------
    def set_context(self, ctx: dict) -> None:
        """Registry panel örneği olarak açılırken app context'ini alır."""
        if "app" in ctx and ctx["app"] is not None:
            self.app = ctx["app"]
            self._bind_app()
        self.controller.scene = self._resolve_math_model()

    def open(self) -> None:
        self.visible = True
        self._first_open = True
        self._bind_app()
        # Seçimi sel_mgr'den tazele
        self.set_selection(self._resolve_selection())

    def close(self) -> None:
        self.visible = False

    def toggle(self) -> None:
        if self.visible:
            self.close()
        else:
            self.open()

    # ------------------------------------------------------------------
    # Dış bildirimler
    # ------------------------------------------------------------------
    def set_catalog(self, catalog) -> None:
        self.controller.catalog = catalog

    def set_project(self, project) -> None:
        """UIHost.on_project_changed → proje değişti."""
        self._bind_app()
        # controller.load_values() yeni seçim üzerinden çağrılır
        # (set_selection zaten _sync_scene_selection guard'lı)
        self.set_selection([])

    def on_selection_changed(self, selected: list) -> None:
        """UIHost.on_selection_changed → engine'den gelen seçim."""
        if getattr(self, "_syncing", False):
            return
        self._apply_selection_locally(list(selected or []))

    def set_selection(self, elements: list) -> None:
        """Programatik seçim (registry/command'dan)."""
        elements = list(elements or [])
        self._apply_selection_locally(elements)
        self._sync_scene_selection(elements)

    # ------------------------------------------------------------------
    # İç seçim yönetimi
    # ------------------------------------------------------------------
    def _apply_selection_locally(self, elements: list) -> None:
        self.controller.set_selection(elements)
        for el in elements:
            self._tree_open_groups.add(type(el).__name__)
        self._scroll_to_id = _unique_id(elements[0]) if elements else None

    def _sync_scene_selection(self, elements: list) -> None:
        sel_mgr = self._sel_mgr()
        if sel_mgr is None or self._syncing:
            return
        current = {_unique_id(e) for e in self._resolve_selection()}
        target = {_unique_id(e) for e in elements}
        if current == target:
            return
        self._syncing = True
        try:
            if not elements:
                sel_mgr.clear()
            elif len(elements) == 1:
                sel_mgr.select(elements[0], additive=False)
            else:
                sel_mgr.select_multiple(elements, mode=SelectionMode.REPLACE)
        finally:
            self._syncing = False

    def _sel_mgr(self):
        engine = getattr(self.app, "engine", None) if self.app else None
        return getattr(engine, "sel_mgr", None) if engine else None

    def refresh(self) -> None:
        self._bind_app()

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self) -> None:
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

    def _draw_body(self) -> None:
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
    # Ağaç
    # ------------------------------------------------------------------
    def _draw_tree(self) -> None:
        imgui.text_disabled("Elements")
        imgui.separator()

        scene = self._resolve_scene()
        math_model = self._resolve_math_model()
        if scene is None:
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
            self._select_first_match(flt, scene, math_model)

        self._draw_filtered_groups(flt, bool(flt), scene, math_model)

    def _select_first_match(self, flt: str, scene, math_model) -> None:
        type_hint, id_hint, text_hint = _parse_filter(flt)
        for type_name, elements in _scene_groups(scene, math_model):
            if type_hint and type_name.lower() != type_hint:
                continue
            for el in elements:
                if _matches(el, type_name, text_hint, id_hint):
                    self._select_via_scene(el)
                    return

    def _draw_filtered_groups(self, flt, force_open, scene, math_model) -> None:
        type_hint, id_hint, text_hint = _parse_filter(flt)

        for type_name, elements in _scene_groups(scene, math_model):
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
                clicked = imgui.selectable(f"{label}##tree_{id(el)}", is_selected)[0]

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

    def _select_via_scene(self, el) -> None:
        if el is None or not hasattr(el, "unique_id"):
            return
        sel_mgr = self._sel_mgr()
        if sel_mgr is not None and hasattr(sel_mgr, "select_only"):
            sel_mgr.select_only(el)
            return
        self.set_selection([el])

    def _focus_in_scene(self, el) -> None:
        app = self.app
        if app is None:
            return
        if hasattr(app, "focus_element"):
            app.focus_element(el)
        else:
            sel_mgr = self._sel_mgr()
            if sel_mgr is not None:
                sel_mgr.select_only(el)

    # ------------------------------------------------------------------
    # Form
    # ------------------------------------------------------------------
    def _draw_form(self) -> None:
        c = self.controller

        if not c.objects:
            imgui.spacing()
            imgui.text_colored(_col(0.5, 0.5, 0.5), "Eleman seçilmedi")
            return
        imgui.text_colored(_col(0.6, 0.4, 0.4), "element")
        
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
        if c.is_dirty():
            imgui.same_line()
            imgui.text_colored(_col(1.0, 0.75, 0.3), "●")
        imgui.separator()

        groups = c.schema()
        if not groups:
            imgui.text_disabled("(şema yok)")
            return

        table_flags = (imgui.TableFlags_.sizing_stretch_prop
                       | imgui.TableFlags_.borders_inner_h
                       | imgui.TableFlags_.no_saved_settings)
        for gi, grp in enumerate(groups):
            if grp.default_open:
                imgui.set_next_item_open(True, imgui.Cond_.once)
            if imgui.collapsing_header(f"{grp.title}##grp_{gi}"):
                if imgui.begin_table(f"##grp_{gi}", 2, table_flags):
                    imgui.table_setup_column(
                        "Key", imgui.TableColumnFlags_.width_fixed, 130.0)
                    imgui.table_setup_column(
                        "Value", imgui.TableColumnFlags_.width_stretch)
                    for f in grp.fields:
                        draw_schema_field(c, f, self.controller.catalog)
                    imgui.end_table()

    def _draw_type_selector(self, c) -> None:
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
                        c.load_values()
                        imgui.close_current_popup()
                imgui.end_popup()
        else:
            changed, new_idx = imgui.combo("##type_filter", cur_idx, labels)
            if changed and 0 <= new_idx < len(types):
                c.set_filter_type(types[new_idx])
                c.load_values()

        imgui.separator()

    def _on_applied(self, payload: dict) -> None:
        app = self.app
        if app is None:
            return
        import app.commands as cmd
        node_uids = payload.get("node_uids", [])
        if node_uids:
            app.put_command(cmd.PropagateGeometryChange(node_uids=node_uids))
        app.put_command(cmd.RefreshGeometry())