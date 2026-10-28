# ui/visibility_panel.py
"""
VisibilityPanel — BasePanel türevi. Sahne elemanlarını tip bazlı gruplarla listeler.
"""
from imgui_bundle import imgui

from ui.base_panel import BasePanel


class VisibilityPanel(BasePanel):

    GROUPS = [
        ("Node",    "nodes"),
        ("Frame",   "frames"),
        ("Area",    "areas"),
        ("Link",    "links"),
        ("Polygon", "polygons"),
    ]

    def __init__(self, on_apply=None):
        super().__init__(title="Görünürlük", width=360, height=560, pos_first_use=(800, 40))
        self.scene = None
        self.on_apply = on_apply

        self._pending: dict[int, bool] = {}
        self._open_groups: set = set()
        self._filter = ""

    def open(self, scene=None):
        super().open()
        if scene is not None:
            self.scene = scene
        self._pending.clear()
        self._open_groups.clear()
        self._filter = ""

    def close(self):
        super().close()
        self._pending.clear()
        self._open_groups.clear()

    def has_changes(self) -> bool:
        return bool(self._pending)

    def apply_changes(self):
        if not self.scene or not self._pending:
            return
        for _, coll_name in self.GROUPS:
            collection = getattr(self.scene, coll_name, None)
            if not collection:
                continue
            for el in collection.values():
                uid = getattr(el, "unique_id", None)
                if uid in self._pending:
                    el.is_visible = self._pending[uid]
                    el.mark_dirty()
        self._pending.clear()
        if callable(self.on_apply):
            self.on_apply()

    def draw_content(self):
        # --- Filtre ---
        imgui.push_item_width(-1)
        self._filter = imgui.input_text(
            "##filter", self._filter,
            imgui.InputTextFlags_.enter_returns_true,
        )[1]
        imgui.pop_item_width()

        imgui.separator()

        # --- Global butonlar ---
        avail = imgui.get_content_region_avail().x
        btn_w = (avail - 8) * 0.5

        if imgui.button("Tümünü Aç", imgui.ImVec2(btn_w, 0)):
            self._set_all(True)
        imgui.same_line()
        if imgui.button("Tümünü Kapa", imgui.ImVec2(btn_w, 0)):
            self._set_all(False)

        imgui.separator()

        # --- Liste ---
        btn_h = imgui.get_frame_height_with_spacing() + 12
        imgui.begin_child("list", imgui.ImVec2(0, -float(btn_h)))

        if self.scene is None:
            imgui.text_colored(imgui.ImVec4(0.7, 0.4, 0.4, 1.0), 'Sahne yok')
        else:
            self._draw_groups()

        imgui.end_child()
        imgui.separator()

        # --- Alt butonlar ---
        imgui.push_style_color(
            imgui.Col_.button, imgui.ImVec4(0.45, 0.20, 0.20, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_hovered, imgui.ImVec4(0.60, 0.28, 0.28, 1.0)
        )
        if imgui.button("İptal", imgui.ImVec2(btn_w, 0)):
            self._pending.clear()
            self.close()
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(
            imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.30, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0)
        )
        if imgui.button("Apply", imgui.ImVec2(btn_w, 0)):
            self.apply_changes()
            self.close()
        imgui.pop_style_color(2)

    def _draw_groups(self):
        for display_name, coll_name in self.GROUPS:
            collection = getattr(self.scene, coll_name, None)
            if collection is None:
                continue

            items = list(collection.values())

            if self._filter:
                f = self._filter.lower()
                items = [e for e in items
                         if f in str(getattr(e, "label", "")).lower()
                         or f in str(getattr(e, "unique_id", ""))]
                if items:
                    self._open_groups.add(f"grp_{coll_name}")

            if not items and not self._filter:
                self._draw_group_header(
                    display_name, coll_name, [], force_open=False, disabled=True
                )
                continue

            if not items:
                continue

            self._draw_group_header(
                display_name, coll_name, items,
                force_open=False, disabled=False,
            )

    def _draw_group_header(self, display_name, coll_name, items,
                           force_open=False, disabled=False):
        if disabled or not items:
            group_state = False
            mixed = False
        else:
            vis_states = [self._current_visibility(e) for e in items]
            visible_count = sum(1 for v in vis_states if v)
            if visible_count == 0:
                group_state, mixed = False, False
            elif visible_count == len(items):
                group_state, mixed = True, False
            else:
                group_state, mixed = False, True

        key = f"grp_{coll_name}"
        is_open = force_open or (key in self._open_groups)

        imgui.push_id(f"chk_{coll_name}")
        if disabled:
            imgui.push_style_var(imgui.StyleVar_.alpha, 0.5)
        if mixed:
            imgui.push_style_color(
                imgui.Col_.check_mark, imgui.ImVec4(0.7, 0.7, 0.4, 1.0)
            )
        changed, new_state = imgui.checkbox("##grp_chk", group_state)
        if mixed:
            imgui.pop_style_color(1)
        if disabled:
            imgui.pop_style_var(1)
        imgui.pop_id()

        if changed and not disabled:
            for el in items:
                uid = getattr(el, "unique_id", id(el))
                self._pending[uid] = bool(new_state)

        imgui.same_line()
        arrow = self.ascii_arrow(is_open)
        header_label = f"{arrow}  {display_name} ({len(items)})##hdr_{coll_name}"

        if disabled:
            imgui.push_style_var(imgui.StyleVar_.alpha, 0.5)
        clicked = imgui.selectable(header_label, False)[0]
        if disabled:
            imgui.pop_style_var(1)

        if clicked and not disabled:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)
            is_open = not is_open

        if is_open and not disabled:
            imgui.indent(24)
            for el in items:
                self._draw_element_row(el)
            imgui.unindent(24)

    def _draw_element_row(self, el):
        uid = getattr(el, "unique_id", id(el))
        label = getattr(el, "label", "") or "?"
        short = f"#{uid}  {label}"

        cur = self._current_visibility(el)

        imgui.push_id(f"el_{uid}")
        changed, new_val = imgui.checkbox("##v", bool(cur))
        imgui.same_line()

        if cur:
            imgui.text(short)
        else:
            imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), short)

        imgui.pop_id()

        if changed:
            self._pending[uid] = bool(new_val)

    def _current_visibility(self, el) -> bool:
        uid = getattr(el, "unique_id", id(el))
        if uid in self._pending:
            return self._pending[uid]
        return bool(getattr(el, "is_visible", True))

    def _set_all(self, state: bool):
        if self.scene is None:
            return
        for _, coll_name in self.GROUPS:
            collection = getattr(self.scene, coll_name, None)
            if not collection:
                continue
            items = list(collection.values())
            if self._filter:
                f = self._filter.lower()
                items = [e for e in items
                         if f in str(getattr(e, "label", "")).lower()
                         or f in str(getattr(e, "unique_id", ""))]
            for el in items:
                uid = getattr(el, "unique_id", id(el))
                self._pending[uid] = state