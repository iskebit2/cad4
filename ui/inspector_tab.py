# ui/inspector_tab.py
"""
InspectorTab — Tek eleman ve çoklu seçim düzenleyicisi.

InspectorPanel içinde bir sekme olarak çalışır. Kendi başına pencere çizmez.
"""
import json
from typing import Any, Callable, Dict, List, Optional

import imgui

from ui.schema import get_path, set_path


def _unpack(result):
    """pyimgui sürüm farklılıkları."""
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


class InspectorTab:

    def __init__(self, on_apply=None):
        self.on_apply = on_apply

        self.schema = []
        self.original_values: Dict[str, Any] = {}
        self.current_values: Dict[str, Any] = {}
        self.title = ""
        self._element = None
        self._elements = None

        self._result: Optional[Dict[str, Any]] = None
        self._combo_idx: Dict[str, int] = {}
        self._open_groups: set = set()

        self._empty_message = "Eleman seçilmedi"
        self._mixed_buffer: Dict[str, str] = {}   # "[KARIŞIK]" alanlar için

    # ------------------------------------------------------------------
    def open_element(self, element):
        self._element = element
        self._elements = None

        from ui.adapters import element_to_values
        from ui.schemas import schema_for

        self.schema = schema_for(getattr(element, "element_type", "Node"))
        vals = json.loads(json.dumps(element_to_values(element), default=str))
        self.original_values = vals
        self.current_values = json.loads(json.dumps(vals, default=str))

        self._mixed_buffer.clear()      # ← EKLE
        self._combo_idx.clear()         # ← EKLE
        self._open_groups.clear()       # ← EKLE

        # default_open grupları
        for gi, g in enumerate(self.schema):
            if getattr(g, "default_open", False):
                self._open_groups.add(f"grp_{gi}")

        # Enum index'lerini doldur
        for g in self.schema:
            for f in g.fields:
                if f.kind == "enum" and f.choices:
                    cur = get_path(self.current_values, f.key)
                    try:
                        self._combo_idx[f.key] = f.choices.index(str(cur))
                    except (ValueError, TypeError):
                        self._combo_idx[f.key] = 0

    def open_multi(self, elements):
        self._element = None
        self._elements = list(elements)

        from ui.adapters import elements_to_common_values
        from ui.schemas import multi_schema_for

        self.schema = multi_schema_for(elements)
        vals = json.loads(json.dumps(elements_to_common_values(elements), default=str))
        self.original_values = vals
        self.current_values = json.loads(json.dumps(vals, default=str))

        self._mixed_buffer.clear()      # ← EKLE
        self._combo_idx.clear()         # ← EKLE
        self._open_groups.clear()       # ← EKLE

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

    def clear(self):
        """İçeriği boşalt — panel açık kalır."""
        self.schema = []
        self.original_values = {}
        self.current_values = {}
        self._element = None
        self._elements = None
        self._open_groups.clear()
        self._combo_idx.clear()
        self._mixed_buffer.clear()

    # ------------------------------------------------------------------
    def _reset_open_groups(self):
        self._open_groups.clear()
        for gi, g in enumerate(self.schema):
            if getattr(g, "default_open", False):
                self._open_groups.add(f"grp_{gi}")

        # Enum combo index'lerini doldur
        self._combo_idx.clear()
        for g in self.schema:
            for f in g.fields:
                if f.kind == "enum" and f.choices:
                    cur = get_path(self.current_values, f.key)
                    try:
                        self._combo_idx[f.key] = f.choices.index(str(cur))
                    except (ValueError, TypeError):
                        self._combo_idx[f.key] = 0

    def has_result(self) -> bool:
        return self._result is not None

    def consume_result(self):
        r = self._result
        self._result = None
        return r

    # ------------------------------------------------------------------
    def draw_content(self):
        """Sekme içeriği — pencere değil, sadece içerik."""
        # Boş panel
        if not self.schema:
            imgui.spacing()
            imgui.spacing()
            imgui.text_colored(self._empty_message, 0.5, 0.5, 0.5, 1.0)
            imgui.spacing()
            imgui.text_colored(
                "Eleman seçmek için:", 0.7, 0.7, 0.7, 1.0)
            imgui.bullet_text("Sol tık → seçim")
            imgui.bullet_text("Sağ tık → panelde aç")
            imgui.bullet_text("Ctrl+P → aç/kapa")
            return

        # Alt buton çubuğu için yükseklik
        btn_h = imgui.get_frame_height_with_spacing() + 12

        # Scrollable içerik
        imgui.begin_child("inspector_content",
                          height=-float(btn_h), border=False)

        for gi, group in enumerate(self.schema):
            self._draw_group(gi, group)

        imgui.end_child()
        imgui.separator()

        # --- Alt butonlar ---
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               0.60, 0.28, 0.28, 1.0)
        if imgui.button("Cancel", width=btn_w):
            self._emit_cancel()
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON,
                               0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED,
                               0.28, 0.68, 0.40, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE,
                               0.35, 0.78, 0.50, 1.0)
        if imgui.button("Apply", width=btn_w):
            self._emit_apply()
        imgui.pop_style_color(3)

    # ------------------------------------------------------------------
    def _draw_group(self, gi, group):
        key = f"grp_{gi}"
        is_open = key in self._open_groups

        arrow = "v" if is_open else ">"
        header_label = f"{arrow}  {group.title}##hdr_{gi}"

        clicked = imgui.selectable(header_label, False)[0]
        if clicked:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)
            is_open = not is_open

        if is_open:
            imgui.indent(20)
            for f in group.fields:
                self._draw_field(f)
            imgui.unindent(20)

    # ------------------------------------------------------------------
    def _draw_field(self, f):
        imgui.push_id(f.key)
        try:
            cur = get_path(self.current_values, f.key)
            label = f.label or f.key

            # --- KARIŞIK durum: tip ne olursa olsun input_text ile göster ---
            if cur == "[KARIŞIK]":
                self._draw_mixed_field(f, label)
                return

            if f.kind == "bool":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                res = imgui.checkbox("##chk", bool(cur))
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
                idx = self._combo_idx.get(f.key, 0)
                res = imgui.combo("##cmb", idx, choices)
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
                res = imgui.input_float("##f", float(cur or 0.0),
                                        step=f.step, format=f.format)
                newv, changed = _unpack(res)
                if changed and newv is not None:
                    set_path(self.current_values, f.key, float(newv))
                return

            if f.kind == "int":
                imgui.align_text_to_frame_padding()
                imgui.text(label)
                imgui.same_line(position=140)
                imgui.set_next_item_width(-1)
                res = imgui.input_int("##i", int(cur or 0))
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
                res = imgui.color_edit3("##col", *rgb)
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
            res = imgui.input_text(
                "##s", str(cur or ""), 256,
                imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
            )
            newv, changed = _unpack(res)
            if changed and newv is not None:
                set_path(self.current_values, f.key, str(newv))
        finally:
            imgui.pop_id()

    def _draw_mixed_field(self, f, label):
        """[KARIŞIK] alanını sarı input olarak göster."""
        imgui.align_text_to_frame_padding()
        imgui.text(label)
        imgui.same_line(position=140)
        imgui.set_next_item_width(-1)

        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND,
                            0.30, 0.25, 0.10, 1.0)
        imgui.push_style_color(imgui.COLOR_TEXT,
                            0.95, 0.85, 0.45, 1.0)

        cur_buf = self._mixed_buffer.get(f.key, "")
        changed, new_val = imgui.input_text(
            "##mixed", cur_buf, 256,
            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
        )

        imgui.pop_style_color(2)

        if changed:
            self._mixed_buffer[f.key] = new_val
            if new_val.strip():
                parsed = self._parse_for_kind(new_val, f.kind)
                if parsed is not None:
                    set_path(self.current_values, f.key, parsed)

    def _parse_for_kind(self, text, kind):
        text = text.strip()
        if not text:
            return None
        try:
            if kind == "float":
                return float(text.replace(",", "."))
            if kind == "int":
                return int(float(text))
            if kind == "bool":
                return text.lower() in (
                    "1", "true", "evet", "yes", "on",
                    "sabit", "görünür", "visible")
            if kind == "color":
                parts = [p.strip() for p in text.split(",")]
                if len(parts) == 3:
                    return [float(p) for p in parts]
                return None
            return text
        except (ValueError, TypeError):
            return None
                    
    # ------------------------------------------------------------------
    def _emit_apply(self):
        payload = json.loads(json.dumps(self.current_values, default=str))

        if self._elements:
            # Çoklu seçim — "[KARIŞIK]" alanları atla
            cleaned = self._strip_mixed(payload)
            if cleaned and callable(self.on_apply):
                self.on_apply(self._elements, cleaned)
        elif self._element is not None:
            if callable(self.on_apply):
                self.on_apply(self._element, payload)

    def _emit_cancel(self):
        self.current_values = json.loads(
            json.dumps(self.original_values, default=str))

    def _strip_mixed(self, values):
        if not isinstance(values, dict):
            return values
        out = {}
        for k, v in values.items():
            if v == "[KARIŞIK]":
                continue
            if isinstance(v, dict):
                sub = self._strip_mixed(v)
                if sub:
                    out[k] = sub
            else:
                out[k] = v
        return out