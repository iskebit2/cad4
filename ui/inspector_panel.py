# ui/inspector_panel.py
"""
InspectorPanel — BasePanel türevi. Tek eleman ve çoklu seçim düzenleyicisi.
"""
import json
from typing import Any, Callable, Dict, List, Optional
import imgui

from ui.base_panel import BasePanel
from ui.schema import get_path, set_path
from ui.adapters import MIXED

def _unpack(result):
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


class InspectorPanel(BasePanel):

    def __init__(self, width: float = 380.0, height: float = 620.0, on_apply=None):
        super().__init__(title="Inspector", width=width, height=height, pos_first_use=(850, 100))
        self.on_apply = on_apply

        self.schema = []
        self.original_values: Dict[str, Any] = {}
        self.current_values: Dict[str, Any] = {}
        self._element = None
        self._elements = None

        self._combo_idx: Dict[str, int] = {}
        self._open_groups: set = set()
        self._empty_message = "Eleman seçilmedi"
        self._mixed_buffer: Dict[str, str] = {}

    def open_element(self, element):
        self.open()
        self._element = element
        self._elements = None

        from ui.adapters import element_to_values
        from ui.schemas import schema_for

        self.schema = schema_for(getattr(element, "element_type", "Node"))
        vals = json.loads(json.dumps(element_to_values(element), default=str))
        self.original_values = vals
        self.current_values = json.loads(json.dumps(vals, default=str))

        self._reset_state()

    def clear(self):
        self.schema = []
        self.original_values = {}
        self.current_values = {}
        self._element = None
        self._elements = None
        self._open_groups.clear()
        self._combo_idx.clear()
        self._mixed_buffer.clear()

    def _reset_state(self):
        self._mixed_buffer.clear()
        self._combo_idx.clear()
        self._open_groups.clear()

        for gi, g in enumerate(self.schema):
            if getattr(g, "default_open", False):
                self._open_groups.add(f"grp_{gi}")

        for g in self.schema:
            for f in g.fields:
                if f.kind == "enum" and f.choices:
                    cur = get_path(self.current_values, f.key)
                    try:
                        self._combo_idx[f.key] = f.choices.index(str(cur))
                    except (ValueError, TypeError):
                        self._combo_idx[f.key] = 0

    def draw_content(self):
        if not self.schema:
            imgui.spacing()
            imgui.spacing()
            imgui.text_colored(self._empty_message, 0.5, 0.5, 0.5, 1.0)
            imgui.spacing()
            imgui.text_colored("Eleman seçmek için:", 0.7, 0.7, 0.7, 1.0)
            imgui.bullet_text("Sol tık → seçim")
            imgui.bullet_text("Sağ tık → panelde aç")
            imgui.bullet_text("Ctrl+P → aç/kapa")
            return

        btn_h = imgui.get_frame_height_with_spacing() + 12
        imgui.begin_child("inspector_content", height=-float(btn_h), border=False)

        for gi, group in enumerate(self.schema):
            self._draw_group(gi, group)

        imgui.end_child()
        imgui.separator()

        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        imgui.push_style_color(imgui.COLOR_BUTTON, 0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.60, 0.28, 0.28, 1.0)
        if imgui.button("Cancel", width=btn_w):
            self._emit_cancel()
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.68, 0.40, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.35, 0.78, 0.50, 1.0)
        if imgui.button("Apply", width=btn_w):
            self._emit_apply()
        imgui.pop_style_color(3)

    def _draw_group(self, gi, group):
        key = f"grp_{gi}"
        is_open = key in self._open_groups

        arrow = self.ascii_arrow(is_open)
        header_label = f"{arrow}  {group.title}##hdr_{gi}"

        if imgui.selectable(header_label, False)[0]:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)

        if is_open in self._open_groups or is_open: # is_open durumu dikkate alınır
            imgui.indent(20)
            for f in group.fields:
                self._draw_field(f)
            imgui.unindent(20)

    def _draw_field(self, f):
        imgui.push_id(f.key)
        try:
            cur = get_path(self.current_values, f.key)
            label = f.label or f.key

            # Mixed kontrolü EN BAŞTA ve TİP'e göre
            if cur == MIXED:
                self._draw_mixed_field(f, label)
                return

            if f.kind == "bool":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                newv, changed = _unpack(imgui.checkbox("##chk", bool(cur)))
                if changed and newv is not None:
                    set_path(self.current_values, f.key, bool(newv))
                return
            if f.kind == "enum":
                choices = f.choices or []
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                idx = self._combo_idx.get(f.key, 0)
                new_idx, changed = _unpack(imgui.combo("##cmb", idx, choices))
                if changed and new_idx is not None:
                    self._combo_idx[f.key] = new_idx
                    set_path(self.current_values, f.key, choices[new_idx])
                return

            if f.kind == "float":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                newv, changed = _unpack(imgui.input_float("##f", float(cur or 0.0), step=f.step, format=f.format))
                if changed and newv is not None:
                    set_path(self.current_values, f.key, float(newv))
                return

            if f.kind == "int":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                newv, changed = _unpack(imgui.input_int("##i", int(cur or 0)))
                if changed and newv is not None:
                    set_path(self.current_values, f.key, int(newv))
                return

            imgui.align_text_to_frame_padding()
            imgui.text(label)
            imgui.same_line(position=140)
            imgui.set_next_item_width(-1)
            newv, changed = _unpack(imgui.input_text("##s", str(cur or ""), 256))
            if changed and newv is not None:
                set_path(self.current_values, f.key, str(newv))
        finally:
            imgui.pop_id()

    def _draw_mixed_field(self, f, label):
        imgui.align_text_to_frame_padding()
        imgui.text(label)
        imgui.same_line(position=140)
        imgui.set_next_item_width(-1)

        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, 0.30, 0.25, 0.10, 1.0)
        imgui.push_style_color(imgui.COLOR_TEXT, 0.95, 0.85, 0.45, 1.0)

        if f.kind == "bool":
            imgui.push_style_color(imgui.COLOR_CHECK_MARK, 0.7, 0.7, 0.4, 1.0)
            changed, new_val = imgui.checkbox("##mixed_bool", False)
            imgui.pop_style_color(1)
            imgui.same_line()
            imgui.text("(karışık)")
            imgui.pop_style_color(2)
            if changed:
                set_path(self.current_values, f.key, bool(new_val))
            return

        if f.kind == "float":
            changed, new_val = imgui.input_float("##mixed_f", 0.0, step=f.step, format=f.format)
            imgui.same_line(); imgui.text("(karışık)")
            imgui.pop_style_color(2)
            if changed:
                set_path(self.current_values, f.key, float(new_val))
            return

        if f.kind == "int":
            changed, new_val = imgui.input_int("##mixed_i", 0)
            imgui.same_line(); imgui.text("(karışık)")
            imgui.pop_style_color(2)
            if changed:
                set_path(self.current_values, f.key, int(new_val))
            return

        if f.kind == "enum":
            choices = f.choices or []
            changed, new_idx = _unpack(imgui.combo("##mixed_e", 0, choices))
            imgui.same_line(); imgui.text("(karışık)")
            imgui.pop_style_color(2)
            if changed and new_idx is not None:
                set_path(self.current_values, f.key, choices[new_idx])
            return

        if f.kind == "color":
            # Renk karışık → 3 float olarak göster
            changed, new_val = imgui.color_edit3("##mixed_c", 0.5, 0.5, 0.5)
            imgui.same_line(); imgui.text("(karışık)")
            imgui.pop_style_color(2)
            if changed:
                set_path(self.current_values, f.key, list(new_val))
            return

        # str ve diğerleri
        cur_buf = self._mixed_buffer.get(f.key, "")
        changed, new_val = imgui.input_text("##mixed", cur_buf, 256,
                                            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
        imgui.same_line(); imgui.text("(karışık)")
        imgui.pop_style_color(2)
        if changed:
            self._mixed_buffer[f.key] = new_val
            if new_val.strip():
                set_path(self.current_values, f.key, new_val)

    def open_multi(self, elements):
        self.open()
        self._element = None
        self._elements = list(elements)

        from ui.adapters import elements_to_common_values
        from ui.schemas import multi_schema_for

        self.schema = multi_schema_for(elements)
        vals = elements_to_common_values(elements)

        # JSON round-trip YAPMA, çünkü MIXED sentinel string olarak kalır ve
        # original_values ile current_values aynı olur; deepcopy yeterli
        import copy
        self.original_values = copy.deepcopy(vals)
        self.current_values = copy.deepcopy(vals)

        self._reset_state()

    def _emit_apply(self):
        payload = self._sanitize(self.current_values)
        if self._elements and callable(self.on_apply):
            self.on_apply(self._elements, payload)
        elif self._element is not None and callable(self.on_apply):
            self.on_apply(self._element, payload)

    def _sanitize(self, d):
        """MIXED sentinel'lerini payload'dan çıkar."""
        if isinstance(d, dict):
            return {k: self._sanitize(v) for k, v in d.items() if v != MIXED}
        if isinstance(d, list):
            return [self._sanitize(v) for v in d]
        return d
    
    def _emit_cancel(self):
        self.current_values = json.loads(json.dumps(self.original_values, default=str))