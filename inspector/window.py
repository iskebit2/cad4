# inspector/window.py

"""
InspectorWindow — UI katmanı.

Sol panel:  element ağacı (Node / Frame / Area / Polygon)
Sağ panel:  seçili element(ler)in schema formu
Alt:        [ Cancel ]  [ Apply ]

CadApp sadece `draw()` ve `set_selection(...)` çağırır.
"""

from collections.abc import Mapping
from enum import Enum
from typing import Any

from imgui_bundle import imgui

from inspector.controller import InspectorController
from inspector.widgets.base import DrawContext
from inspector.widgets.group import GroupDrawer
from logging_config import CadLogger

logger = CadLogger.get(__name__)

# ----------------------------------------------------------------------
# Scene keşif yardımcıları
# ----------------------------------------------------------------------
_TYPES = ("Node", "Frame", "Area", "Polygon", "Link")


def _scene_groups(scene):
    out = []
    for t in _TYPES:
        elements = _collect(scene, t)
        out.append((t, list(elements)))
    return out


def _collect(scene, type_name):
    attr_map = {
        "Node": "nodes", "Frame": "frames",
        "Area": "areas", "Polygon": "polygons",
    }
    attr = attr_map.get(type_name)
    if attr and hasattr(scene, attr):
        seq = getattr(scene, attr) or []
        if isinstance(seq, dict):
            return list(seq.values())
        if isinstance(seq, (list, tuple, set)):
            return list(seq)
        try:
            return list(seq)
        except TypeError:
            pass

    if hasattr(scene, "iter_elements"):
        try:
            return list(scene.iter_elements(type=type_name))
        except (TypeError, AttributeError):
            pass

    if hasattr(scene, "all_elements"):
        elems = scene.all_elements
        if isinstance(elems, dict):
            elems = elems.values()
        return [e for e in elems
                if getattr(e, "element_type", type(e).__name__) == type_name]

    return []


def _element_label(el) -> str:
    if el is None:
        return "?"
    v = getattr(el, "label", None)
    if v not in (None, ""):
        return str(v)
    v = getattr(el, "name", None)
    if v not in (None, ""):
        return str(v)
    uid = _unique_id(el)
    t = getattr(el, "element_type", type(el).__name__)
    if uid is not None:
        return f"{t}_{uid}"
    return f"{t}@{hex(id(el) & 0xFFFF)}"


def _parse_filter(flt: str):
    type_hint = None
    id_hint = None
    text = flt

    if ":" in text:
        head, tail = text.split(":", 1)
        if head in ("node", "frame", "area", "polygon"):
            type_hint = head
            text = tail.strip()

    if text.startswith("#"):
        try:
            id_hint = int(text[1:])
            text = ""
        except ValueError:
            pass

    return type_hint, id_hint, text.strip()


def _matches(el, type_name: str, text_hint: str, id_hint) -> bool:
    if id_hint is not None:
        return _unique_id(el) == id_hint
    if not text_hint:
        return True
    label = _element_label(el).lower()
    if text_hint in label:
        return True
    return text_hint in str(_unique_id(el)).lower()


def _unique_id(el):
    if el is None:
        return None
    v = getattr(el, "unique_id", None)
    if v is not None:
        return v
    for attr in ("uid", "eid"):
        v = getattr(el, attr, None)
        if v is not None:
            return v
    return None


def _copy_to_clipboard(text: str):
    try:
        imgui.set_clipboard_text(text)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Yardımcı: ImVec4 / renkli metin
# ----------------------------------------------------------------------
def _col(r, g, b, a=1.0) -> imgui.ImVec4:
    return imgui.ImVec4(float(r), float(g), float(b), float(a))


def _domain_field_items(element) -> list[tuple[str, Any]]:
    """Return all stored domain fields, including fields added by future models."""
    try:
        return list(vars(element).items())
    except TypeError:
        return []


class InspectorWindow:

    LEFT_PANEL_MIN = 140.0
    LEFT_PANEL_MAX = 260.0

    def __init__(self, scene=None, catalog=None, standalone=False):
        self.scene = scene
        self.catalog = catalog
        self.controller = InspectorController(scene=scene, catalog=catalog)

        self.visible = False
        self.standalone = standalone
        self._first_open = True

        self._left_width = 180.0
        self._left_open = True
        self._tree_open_groups: set = set()
        self._form_open_groups: set = set()
        self._tree_filter = ""

        self._scroll_to_id = None
        self._group_drawer = GroupDrawer(self._form_open_groups)

    # ==================================================================
    # Dış API
    # ==================================================================
    def set_context(self, ctx: dict):
        for k, v in ctx.items():
            setattr(self, k, v)

    def open(self):
        self.visible = True
        self._first_open = True

    def close(self):
        self.visible = False

    def toggle(self):
        if self.visible:
            self.close()
        else:
            self.open()

    def set_scene(self, scene):
        self.scene = scene
        if self.controller is not None:
            if hasattr(self.controller, "scene"):
                self.controller.scene = scene
            cset = getattr(self.controller, "set_scene", None)
            if callable(cset):
                cset(scene)

        self._tree_filter = ""
        self._tree_open_groups.clear()
        self._form_open_groups.clear()
        self._scroll_to_id = None

        if hasattr(self, "set_selection"):
            self.set_selection([])

        self.refresh()

    def set_catalog(self, catalog):
        self.catalog = catalog
        self.controller.catalog = catalog

    def set_selection(self, elements: list[Any]):
        self.controller.set_filter_type(None)
        self.controller.set_selection(elements)
        self._form_open_groups.clear()
        for el in (elements or []):
            t = getattr(el, "element_type", type(el).__name__)
            self._tree_open_groups.add(t)
        self._scroll_to_id = _unique_id(elements[0]) if elements else None
        self._sync_scene_selection(elements)

    def _sync_scene_selection(self, elements):
        app = getattr(self, "app", None)
        if app is None or not getattr(app, "engine", None):
            return
        sel_mgr = getattr(app.engine, "sel_mgr", None)
        if sel_mgr is None:
            return

        current_ids = set(getattr(sel_mgr, "selected", set()) or set())
        target_ids = {_unique_id(e) for e in (elements or [])}
        if current_ids == target_ids:
            return

        try:
            if not elements:
                sel_mgr.clear()
            elif len(elements) == 1:
                sel_mgr.select(elements[0], additive=False)
            else:
                from core.selection_policy import SelectionMode
                sel_mgr.select_multiple(elements, mode=SelectionMode.REPLACE)
        except Exception:
            logger.exception("sel_mgr senkron hatası")

    def refresh(self):
        if self.controller is not None:
            self.controller.refresh_from_scene()

    # ==================================================================
    # Draw
    # ==================================================================
    def draw(self):
        if not self.visible:
            return

        if self._first_open and not self.standalone:
            imgui.set_next_window_pos(
                imgui.ImVec2(850, 100), imgui.Cond_.first_use_ever
            )
            imgui.set_next_window_size(
                imgui.ImVec2(620, 620), imgui.Cond_.first_use_ever
            )
            self._first_open = False

        expanded, opened = imgui.begin("Inspector", True)
        try:
            if not opened:
                self.close()
                return
            self._handle_shortcuts()
            self._draw_body()
        except Exception:
            logger.exception("Inspector draw hatası")
        finally:
            imgui.end()

    def _handle_shortcuts(self):
        io = imgui.get_io()
        if io.want_text_input:
            return

        if imgui.is_key_pressed(imgui.Key.enter):
            self.controller.apply()
        elif imgui.is_key_pressed(imgui.Key.escape):
            self.controller.cancel()
        elif io.key_ctrl and imgui.is_key_pressed(imgui.Key.a):
            pass

    # ==================================================================
    # Gövde
    # ==================================================================
    def _draw_body(self):
        avail = imgui.get_content_region_avail().x
        btn_h = imgui.get_frame_height_with_spacing() + 12

        imgui.begin_child("insp_body", imgui.ImVec2(0, -float(btn_h)))
        try:
            # --- Toggle butonu HER ZAMAN görünür ---
            if imgui.button("◀" if self._left_open else "▶"):
                self._left_open = not self._left_open
            imgui.same_line()

            if self._left_open:
                # Butonun yanına paneli koy
                imgui.begin_child("insp_left", imgui.ImVec2(self._left_width, 0))
                try:
                    self._draw_tree()
                finally:
                    imgui.end_child()
                imgui.same_line()

            # Sağ panel her durumda çizilir
            imgui.begin_child("insp_right", imgui.ImVec2(0, 0))
            try:
                self._draw_form()
            finally:
                imgui.end_child()
        finally:
            imgui.end_child()

        imgui.separator()
        self._draw_buttons(avail, btn_h)

    # ------------------------------------------------------------------
    def _draw_tree(self):
        # if imgui.button("◀" if self._left_open else "▶"):
        #     self._left_open = not self._left_open
        imgui.same_line()
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
                "Filtre ipuçları:\n"
                "  n123        → 'n123' içeren label\n"
                "  node:n12    → Node türünde 'n12' içeren\n"
                "  #123        → id=123\n"
                "  frame:      → tüm frame'ler\n"
            )

        if imgui.is_window_focused() and imgui.get_io().key_ctrl and imgui.is_key_pressed(imgui.Key.f):
            imgui.set_keyboard_focus_here()

        flt = (self._tree_filter or "").strip().lower()

        if imgui.is_item_focused() and imgui.is_key_pressed(imgui.Key.enter):
            self._select_first_match(flt)

        force_open = bool(flt)
        self._draw_filtered_groups(flt, force_open)

    def _select_first_match(self, flt: str):
        type_hint, id_hint, text_hint = _parse_filter(flt)
        for type_name, elements in _scene_groups(self.scene):
            if type_hint and type_name.lower() != type_hint:
                continue
            for el in elements:
                if _matches(el, type_name, text_hint, id_hint):
                    self.set_selection([el])
                    return

    def _draw_filtered_groups(self, flt: str, force_open: bool):
        type_hint, id_hint, text_hint = _parse_filter(flt)
        groups = _scene_groups(self.scene)

        for type_name, elements in groups:
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
            opened = imgui.collapsing_header(header)
            if not opened:
                continue

            imgui.indent(12)
            MAX = 200
            for el in filtered[:MAX]:
                label = _element_label(el)
                is_selected = el in self.controller.selection.elements

                clicked = imgui.selectable(
                    f"{label}##tree_{id(el)}", is_selected
                )[0]

                # Sağ tık menüsü
                if imgui.begin_popup_context_item(f"ctx_{id(el)}"):
                    if imgui.menu_item("Sahneye odakla", "", False)[0]:
                        self._focus_in_scene(el)
                    if imgui.menu_item("ID kopyala", "", False)[0]:
                        _copy_to_clipboard(str(_unique_id(el)))
                    imgui.separator()
                    if imgui.menu_item("Sadece bunu seç", "", False)[0]:
                        self._select_via_scene(el)
                    imgui.end_popup()

                if getattr(self, "_scroll_to_id", None) == _unique_id(el):
                    imgui.set_scroll_here_y(0.3)
                    self._scroll_to_id = None

                if clicked:
                    self._select_via_scene(el)
                    continue

            if len(filtered) > MAX:
                imgui.text_colored(
                    _col(0.6, 0.6, 0.6),
                    f"...ve {len(filtered) - MAX} tane daha",
                )
            imgui.unindent(12)

    def _select_via_scene(self, el):
        if el is None or not hasattr(el, "unique_id"):
            logger.warning("_select_via_scene: geçersiz element: %r", el)
            return
        app = getattr(self, "app", None)
        if app and getattr(app, "engine", None):
            sel_mgr = getattr(app.engine, "sel_mgr", None)
            if sel_mgr and hasattr(sel_mgr, "select_only"):
                try:
                    sel_mgr.select_only(el)
                    return
                except Exception:
                    logger.exception("select_only hatası")
        self.set_selection([el])

    def _draw_form(self):
        c = self.controller

        if c.selection.is_empty:
            imgui.spacing()
            imgui.text_colored(_col(0.5, 0.5, 0.5), "Eleman seçilmedi")
            return

        self._draw_assoc_filter_bar()
        imgui.separator()

        if c.filter_assoc_only is not None:
            imgui.text_colored(
                _col(0.85, 0.75, 0.35),
                f"! Plane assoc filtresi: {c.filter_assoc_only.name}",
            )
            imgui.same_line()
            if imgui.small_button("✕"):
                c.set_filter_assoc_only(None)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Assoc filtresini kaldır")
            imgui.separator()

        counts = c.selection_counts_by_type()
        total = len(c.selection.elements)
        filtered_total = len(c.filtered_elements)
        if total != filtered_total:
            imgui.text(f"{filtered_total}/{total} eleman gösteriliyor")
        else:
            imgui.text(f"{total} eleman")

        is_multi_type = len(counts) > 1

        if is_multi_type:
            current_label = "Hepsi" if c.filter_type is None else c.filter_type
            items = [f"Hepsi ({total})"]
            type_order = ["Node", "Frame", "Area", "Link", "Polygon"]
            label_to_type = {"Hepsi": None}
            for t in type_order:
                if t in counts:
                    items.append(f"{t} ({counts[t]})")
                    label_to_type[t] = t

            try:
                cur_idx = items.index(
                    f"Hepsi ({total})" if c.filter_type is None
                    else f"{c.filter_type} ({counts[c.filter_type]})"
                )
            except (ValueError, KeyError):
                cur_idx = 0

            imgui.align_text_to_frame_padding()
            imgui.text(f"{total} eleman seçili")
            imgui.same_line(200)
            imgui.set_next_item_width(-1)
            changed, new_idx = imgui.combo("##type_filter", cur_idx, items)
            if changed and 0 <= new_idx < len(items):
                label = items[new_idx].split(" (")[0]
                c.set_filter_type(label_to_type.get(label))
        else:
            el_type = list(counts.keys())[0] if counts else "?"
            imgui.text_colored(_col(0.8, 0.8, 0.4), f"{el_type}")
            imgui.same_line()
            imgui.text_disabled(f"{total} eleman")

        imgui.separator()

        if c.selection.is_single:
            el = c.selection.primary
            el_type = type(el).__name__
            el_label = _element_label(el)
        else:
            el_type = "Çoklu seçim"
            el_label = f"{c.selection.count} eleman"

        dirty = self._is_dirty()

        imgui.text_colored(_col(0.8, 0.8, 0.4), el_type)
        imgui.same_line()
        imgui.text_disabled(el_label)

        if dirty:
            imgui.same_line()
            imgui.text_colored(_col(0.95, 0.75, 0.30), "●")
            if imgui.is_item_hovered():
                imgui.set_tooltip("Kaydedilmemiş değişiklikler var")

        imgui.same_line(
            imgui.get_cursor_pos_x() + imgui.get_content_region_avail().x - 30
        )
        if imgui.button("_##refresh"):
            self.refresh()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Sahneden güncel değerleri tekrar oku")

        imgui.separator()

        if not c.schema:
            imgui.text_colored(
                _col(0.7, 0.5, 0.5),
                "Bu element için schema tanımlı değil",
            )
            return

        if not hasattr(self, "_draw_ctx"):
            self._draw_ctx = DrawContext(values=c.selection.values)
        self._draw_ctx.values = c.selection.values
        self._draw_ctx.changed = False
        self._draw_ctx.catalog = self.catalog

        self._group_drawer.open_groups = self._form_open_groups
        for gi, group in enumerate(c.schema):
            self._group_drawer.draw(gi, group, self._draw_ctx)

        # elements = c.selection.elements
        # if elements:
        #     imgui.separator()
        #     imgui.set_next_item_open(True, imgui.Cond_.once)
        #     if imgui.tree_node(f"Domain alanları##domain_fields_{id(elements[0])}"):
        #         for index, element in enumerate(elements):
        #             if len(elements) > 1:
        #                 title = f"{_element_label(element)} ({type(element).__name__})##domain_element_{index}"
        #                 if not imgui.tree_node(title):
        #                     continue
        #                 self._draw_domain_fields(element)
        #                 imgui.tree_pop()
        #             else:
        #                 self._draw_domain_fields(element)
        #         imgui.tree_pop()

    # def _draw_domain_fields(self, element) -> None:
    #     for name, value in _domain_field_items(element):
    #         self._draw_domain_value(name, value, set())

    # def _draw_domain_value(self, label: str, value: Any, ancestors: set[int]) -> None:
    #     if isinstance(value, Enum):
    #         imgui.text(f"{label}: {value.name} ({value.value})")
    #         return
    #     if value is None or isinstance(value, (str, int, float, bool)):
    #         imgui.text_wrapped(f"{label}: {value!r}")
    #         return

    #     if isinstance(value, Mapping):
    #         entries = list(value.items())
    #         object_id = id(value)
    #         if object_id in ancestors:
    #             imgui.text(f"{label}: <circular reference>")
    #             return
    #         if not imgui.tree_node(f"{label} ({len(entries)})"):
    #             return
    #         ancestors.add(object_id)
    #         for key, child in entries:
    #             self._draw_domain_value(str(key), child, ancestors)
    #         ancestors.remove(object_id)
    #         imgui.tree_pop()
    #         return

    #     if isinstance(value, (list, tuple, set)):
    #         items = list(value)
    #         object_id = id(value)
    #         if object_id in ancestors:
    #             imgui.text(f"{label}: <circular reference>")
    #             return
    #         if not imgui.tree_node(f"{label} ({len(items)})"):
    #             return
    #         ancestors.add(object_id)
    #         for index, child in enumerate(items):
    #             self._draw_domain_value(f"[{index}]", child, ancestors)
    #         ancestors.remove(object_id)
    #         imgui.tree_pop()
    #         return

    #     unique_id = _unique_id(value)
    #     if unique_id is not None:
    #         ref_type = getattr(value, "element_type", type(value).__name__)
    #         ref_label = _element_label(value)
    #         imgui.text_wrapped(f"{label}: {ref_type} #{unique_id} ({ref_label})")
    #         return

    #     fields = _domain_field_items(value)
    #     if fields:
    #         object_id = id(value)
    #         if object_id in ancestors:
    #             imgui.text(f"{label}: <circular reference>")
    #             return
    #         if not imgui.tree_node(f"{label} ({type(value).__name__})"):
    #             return
    #         ancestors.add(object_id)
    #         for name, child in fields:
    #             self._draw_domain_value(name, child, ancestors)
    #         ancestors.remove(object_id)
    #         imgui.tree_pop()
    #         return

    #     imgui.text_wrapped(f"{label}: {value!r}")

    def _is_dirty(self) -> bool:
        return self.controller.selection.values != self.controller.selection.original

    def _draw_buttons(self, avail: float, btn_h: float):
        dirty = self._is_dirty()

        if dirty:
            imgui.text_colored(_col(0.95, 0.75, 0.30), "● değişiklikler kaydedilmedi")
            imgui.same_line()
            imgui.spacing()

        btn_w = (avail - 8) * 0.5

        # --- Cancel ---
        imgui.push_style_color(imgui.Col_.button, _col(0.45, 0.20, 0.20))
        imgui.push_style_color(imgui.Col_.button_hovered, _col(0.60, 0.28, 0.28))

        if imgui.button("Cancel", imgui.ImVec2(btn_w, 0)):
            if dirty:
                imgui.open_popup("confirm_cancel")
            else:
                self.controller.cancel()

        if imgui.begin_popup_modal("confirm_cancel", True)[0]:
            imgui.text("Değişiklikler silinsin mi?")
            imgui.spacing()
            if imgui.button("Evet", imgui.ImVec2(100, 0)):
                self.controller.cancel()
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Hayır", imgui.ImVec2(100, 0)):
                imgui.close_current_popup()
            imgui.end_popup()

        imgui.pop_style_color(2)

        imgui.same_line()

        # --- Apply ---
        imgui.push_style_color(imgui.Col_.button, _col(0.20, 0.55, 0.30))
        imgui.push_style_color(imgui.Col_.button_hovered, _col(0.28, 0.68, 0.40))
        imgui.push_style_color(imgui.Col_.button_active, _col(0.35, 0.78, 0.50))
        if imgui.button("Apply", imgui.ImVec2(btn_w, 0)):
            self.controller.apply()
        imgui.pop_style_color(3)

    def _focus_in_scene(self, el):
        app = getattr(self, "app", None)
        if app is None:
            return
        try:
            if hasattr(app, "focus_element"):
                app.focus_element(el)
            elif hasattr(app, "engine") and app.engine and hasattr(app.engine, "cam"):
                app.engine.sel_mgr.select_only(el)
        except Exception:
            pass

    def _draw_assoc_filter_bar(self):
        """Assoc filtresi: [! Plane: P1 ▾] veya [! Plane: (tümü) ▾]"""
        c = self.controller

        imgui.align_text_to_frame_padding()
        imgui.text_colored(_col(0.85, 0.75, 0.35), "! Plane assoc:")
        imgui.same_line()

        planes = c.list_planes()
        if not planes:
            imgui.text_disabled("(projede plane yok)")
            return

        labels = ["(tümü)"] + [
            f"{p.name}  [{sum(len(s) for s in p.associated.values())} assoc]"
            for p in planes
        ]

        cur = c.filter_assoc_only
        try:
            cur_idx = 0 if cur is None else (planes.index(cur) + 1)
        except ValueError:
            cur_idx = 0

        imgui.set_next_item_width(-140)
        changed, new_idx = imgui.combo("##assoc_plane", cur_idx, labels)
        if changed:
            if new_idx == 0:
                c.set_filter_assoc_only(None)
            else:
                c.set_filter_assoc_only(planes[new_idx - 1])

        imgui.same_line()
        if imgui.small_button("_##refresh_assoc"):
            if c.filter_assoc_only is not None and c.scene is not None:
                c.filter_assoc_only.refresh_assoc(c.scene)
                c.set_filter_assoc_only(c.filter_assoc_only)
                c._rebuild_from_filter()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Assoc'u yeniden hesapla")