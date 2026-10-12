# ui/visibility_panel.py
"""
VisibilityPanel — sahne elemanlarını tip bazlı gruplarla listeler.

Yapı:
    ☑ Node (219)              ← grup checkbox (tümünü aç/kapa)
       ☑ #1 N1                ← expand edilince
       ☐ #2 N2
    ☑ Frame (360)
    ☑ Area (0)
    ...

- Default: tüm gruplar COLLAPSED.
- Grup checkbox'ı: gruptaki tüm elemanları aynı duruma getirir.
- Ok (▶) tıklanınca grup expand olur, tekil elemanlar görünür.
"""
from typing import Any, Dict, List, Optional

import imgui
from imgui import internal as imgui_internal


class VisibilityPanel:

    GROUPS = [
        ("Node",    "nodes"),
        ("Frame",   "frames"),
        ("Area",    "areas"),
        ("Link",    "links"),
        ("Polygon", "polygons"),
    ]

    def __init__(self, on_apply=None):
        self.visible = False
        self.scene = None
        self.on_apply = on_apply

        # Geçici değişiklikler (Apply'a kadar burada)
        self._pending: Dict[int, bool] = {}

        # Açık grupların isim kümesi (default: hepsi kapalı)
        self._open_groups: set = set()

        self._first_open = True
        self._filter = ""

    # ------------------------------------------------------------------
    def open(self, scene):
        self.scene = scene
        self.visible = True
        self._first_open = True
        self._pending.clear()
        self._open_groups.clear()
        self._filter = ""

    def close(self):
        self.visible = False
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

    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            w, h = 360, 560
            imgui.set_next_window_position(
                io.display_size[0] - w - 400, 40,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(w, h, condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        expanded, opened = imgui.begin("Görünürlük", True)
        if not opened:
            self.visible = False
            imgui.end()
            return

        # --- Filtre ---
        imgui.push_item_width(-1)
        self._filter = imgui.input_text(
            "##filter", self._filter, 128,
            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
        )[1]
        imgui.pop_item_width()

        imgui.separator()

        # --- Global butonlar ---
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        if imgui.button("Tümünü Aç", width=btn_w):
            self._set_all(True)
        imgui.same_line()
        if imgui.button("Tümünü Kapa", width=btn_w):
            self._set_all(False)

        imgui.separator()

        # --- Liste ---
        btn_h = imgui.get_frame_height_with_spacing() + 12
        imgui.begin_child("list", height=-float(btn_h), border=False)

        if self.scene is None:
            imgui.text_colored("Sahne yok", 0.7, 0.4, 0.4, 1.0)
        else:
            self._draw_groups()

        imgui.end_child()
        imgui.separator()

        # --- Alt butonlar ---
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.60, 0.28, 0.28, 1.0)
        if imgui.button("İptal", width=btn_w):
            self._pending.clear()
            self.visible = False
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.68, 0.40, 1.0)
        if imgui.button("Apply", width=btn_w):
            self.apply_changes()
            self.visible = False
        imgui.pop_style_color(2)

        imgui.end()

    # ------------------------------------------------------------------
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
                # Filtre aktifken aç
                if items:
                    self._open_groups.add(f"grp_{coll_name}")

            if not items and not self._filter:
                # Boş gruplar yine de gri gösterilsin
                self._draw_group_header(
                    display_name, coll_name, [], force_open=False, disabled=True
                )
                continue

            if not items:
                # Filtre var ve eşleşme yok — grubu atla
                continue

            self._draw_group_header(
                display_name, coll_name, items,
                force_open=False, disabled=False,
            )

    # ------------------------------------------------------------------
    def _draw_group_header(self, display_name, coll_name, items,
                        force_open=False, disabled=False):
        # Grup durumu
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

        # --- 1) Grup checkbox'ı ---
        imgui.push_id(f"chk_{coll_name}")
        if disabled:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        if mixed:
            imgui.push_style_color(imgui.COLOR_CHECK_MARK, 0.7, 0.7, 0.4, 1.0)
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

        # --- 2) Ok + başlık (selectable ile manuel toggle) ---
        imgui.same_line()
        arrow = "V" if is_open else ">"
        header_label = f"{arrow}  {display_name} ({len(items)})##hdr_{coll_name}"

        if disabled:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        clicked = imgui.selectable(header_label, False)[0]
        if disabled:
            imgui.pop_style_var(1)

        if clicked and not disabled:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)
            is_open = not is_open

        # --- 3) Açıksa elemanlar ---
        if is_open and not disabled:
            imgui.indent(24)
            for el in items:
                self._draw_element_row(el)
            imgui.unindent(24)

    # ------------------------------------------------------------------
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
            imgui.text_colored(short, 0.5, 0.5, 0.5, 1.0)

        imgui.pop_id()

        if changed:
            self._pending[uid] = bool(new_val)

    # ------------------------------------------------------------------
    def _current_visibility(self, el) -> bool:
        """Pending'de varsa onu, yoksa element'in kendi durumunu döner."""
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