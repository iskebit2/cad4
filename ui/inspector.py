# ui/inspector.py
"""
InspectorPanel — ImGui detayları burada saklanır.

Dışarıya sadece:
    panel = InspectorPanel()
    panel.open(schema, values, title="...")
    panel.draw()
    if panel.has_result():
        res = panel.consume_result()   # {"action": "apply"/"cancel", "values": {...}}
"""
import json
from typing import Any, Callable, Dict, List, Optional

import imgui
from imgui import internal as imgui_internal
from ui.schema import FieldSpec, GroupSpec, get_path, set_path


def _unpack(result):
    """pyimgui sürüm farklılıklarını normalize et. (value, changed) döner."""
    if isinstance(result, tuple) and len(result) == 2:
        a, b = result
        if isinstance(a, bool):
            return b, a
        if isinstance(b, bool):
            return a, b
        return result, True
    if isinstance(result, bool):
        return None, result
    return result, True


class InspectorPanel:

    def __init__(self, width=360, height=560,
                 on_apply: Optional[Callable[[Dict], None]] = None):
        self.visible = False
        self.width = width
        self.height = height
        self.on_apply = on_apply

        self.schema: List[GroupSpec] = []
        self.original_values: Dict[str, Any] = {}
        self.current_values: Dict[str, Any] = {}
        self.title = "Özellikler"

        self._result: Optional[Dict[str, Any]] = None
        self._combo_idx: Dict[str, int] = {}
        self._first_open = True
        self._open_groups: set = set()
        self._mixed_buffer: Dict[str, str] = {}    # ← EKLE
        self._empty_message = "Eleman seçilmedi"

    # ---------------------------------------------------------
    def open(self, schema, values, title="Özellikler"):
        self.schema = schema
        self.original_values = json.loads(json.dumps(values, default=str))
        self.current_values = json.loads(json.dumps(values, default=str))
        self.title = title
        self.visible = True
        self._first_open = True

        # Grup aç/kapa durumunu sıfırla
        self._open_groups.clear()
        for gi, g in enumerate(schema):
            if getattr(g, "default_open", False):
                self._open_groups.add(f"grp_{gi}")

        # Enum index'lerini doldur
        self._combo_idx.clear()
        for g in schema:
            for f in g.fields:
                if f.kind == "enum" and f.choices:
                    cur = get_path(self.current_values, f.key)
                    try:
                        self._combo_idx[f.key] = f.choices.index(str(cur))
                    except (ValueError, TypeError):
                        self._combo_idx[f.key] = 0

    def close(self):
        self.visible = False

    def has_result(self) -> bool:
        return self._result is not None

    def consume_result(self):
        r = self._result
        self._result = None
        return r

    # ---------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            imgui.set_next_window_position(
                io.display_size[0] - self.width - 20, 40,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(self.width, self.height,
                                       condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        expanded, opened = imgui.begin(self.title, True)
        if not opened:
            self.visible = False
            imgui.end()
            return

        btn_h = imgui.get_frame_height_with_spacing() + 8

        imgui.begin_child("content", height=-float(btn_h), border=False)
        for gi, group in enumerate(self.schema):
            self._draw_group(gi, group)
        imgui.end_child()

        imgui.separator()

        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               *self._color_from_hex("b03333"))
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               *self._color_from_hex("cc4444"))
        if imgui.button("Cancel", width=btn_w):
            self._emit_cancel()
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               *self._color_from_hex("338a4d"))
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               *self._color_from_hex("43a562"))
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE,
                               *self._color_from_hex("52bd72"))
        if imgui.button("Apply", width=btn_w):
            self._emit_apply()
        imgui.pop_style_color(3)

        imgui.end()

    # ---------------------------------------------------------
    def _draw_group(self, gi, group):
        key = f"grp_{gi}"
        is_open = key in self._open_groups

        # --- Ok + başlık (selectable ile toggle) ---
        arrow = "V" if is_open else ">"
        header_label = f"{arrow}  {group.title}##hdr_{gi}"

        clicked = imgui.selectable(header_label, False)[0]
        if clicked:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)
            is_open = not is_open

        # --- İçerik ---
        if is_open:
            imgui.indent(20)
            for f in group.fields:
                self._draw_field(f)
            imgui.unindent(20)

    # ---------------------------------------------------------
    def _draw_field(self, f: FieldSpec):
        imgui.push_id(f.key)
        try:
            cur = get_path(self.current_values, f.key)
            label = f.label or f.key

            if f.kind == "bool":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                if not f.editable:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                res = imgui.checkbox("##chk", bool(cur))
                if not f.editable:
                    imgui.end_disabled()
                newv, changed = _unpack(res)
                if changed and newv is not None:
                    set_path(self.current_values, f.key, bool(newv))
                return

            if f.kind == "enum":
                choices = f.choices or []
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                if not f.editable:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                idx = self._combo_idx.get(f.key, 0)
                res = imgui.combo("##cmb", idx, choices)
                if not f.editable:
                    imgui.end_disabled()
                new_idx, changed = _unpack(res)
                if changed and new_idx is not None:
                    self._combo_idx[f.key] = new_idx
                    set_path(self.current_values, f.key, choices[new_idx])
                return

            if f.kind == "float":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                if not f.editable:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                res = imgui.input_float(
                    "##f", float(cur or 0.0),
                    step=f.step, format=f.format,
                )
                if not f.editable:
                    imgui.end_disabled()
                newv, changed = _unpack(res)
                if changed and newv is not None:
                    set_path(self.current_values, f.key, float(newv))
                return

            if f.kind == "int":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                if not f.editable:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                res = imgui.input_int("##i", int(cur or 0))
                if not f.editable:
                    imgui.end_disabled()
                newv, changed = _unpack(res)
                if changed and newv is not None:
                    set_path(self.current_values, f.key, int(newv))
                return

            if f.kind == "color":
                try:
                    rgb = [float(v) for v in (cur or [0.7, 0.7, 0.7])[:3]]
                except Exception:
                    rgb = [0.7, 0.7, 0.7]
                while len(rgb) < 3:
                    rgb.append(0.7)
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                if not f.editable:
                    imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
                res = imgui.color_edit3("##col", *rgb)
                if not f.editable:
                    imgui.end_disabled()
                newrgb, changed = _unpack(res)
                if changed and newrgb is not None:
                    try:
                        new_list = [float(v) for v in newrgb[:3]]
                        while len(new_list) < 3:
                            new_list.append(0.7)
                        set_path(self.current_values, f.key, new_list)
                    except Exception:
                        pass
                return

            # str
            imgui.align_text_to_frame_padding()
            imgui.text(label)
            imgui.same_line(position=140)
            imgui.set_next_item_width(-1)
            if not f.editable:
                imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
            res = imgui.input_text(
                "##s", str(cur or ""), 256,
                imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
            )
            if not f.editable:
                imgui.end_disabled()
            newv, changed = _unpack(res)
            if changed and newv is not None:
                set_path(self.current_values, f.key, str(newv))
        finally:
            imgui.pop_id()

    # ---------------------------------------------------------
    def _emit_apply(self):
        payload = json.loads(json.dumps(self.current_values, default=str))
        self._result = {"action": "apply", "values": payload}
        if self.on_apply:
            self.on_apply(payload)
        self.visible = False

    def _emit_cancel(self):
        self._result = {"action": "cancel", "values": {}}
        self.current_values = json.loads(
            json.dumps(self.original_values, default=str))
        self.visible = False

    @staticmethod
    def _color_from_hex(h, alpha=1.0):
        h = h.lstrip("#")
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, alpha)