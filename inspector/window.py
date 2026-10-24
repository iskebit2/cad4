"""
InspectorWindow — UI katmanı.

Sol panel:  element ağacı (Node / Frame / Area / Polygon)
Sağ panel:  seçili element(ler)in schema formu
Alt:        [ Cancel ]  [ Apply ]

CadApp sadece `draw()` ve `set_selection(...)` çağırır.
"""

from logging_config import CadLogger
from typing import Any, List, Optional

import imgui

from inspector.controller import InspectorController
from inspector.widgets.base import DrawContext
from inspector.widgets.group import GroupDrawer


logger = CadLogger.get(__name__)

# ----------------------------------------------------------------------
# Scene keşif yardımcıları — farklı scene API'lerine uyumlu
# ----------------------------------------------------------------------
_TYPES = ("Node", "Frame", "Area", "Polygon", "Link")


def _scene_groups(scene):
    """scene'den (type_name, [elements]) listesi döndür.

    Önce `scene.iter_elements(type=...)`, yoksa `scene.<attr>` listesi,
    yoksa `scene.get_elements(type)` dener.
    """
    out = []
    for t in _TYPES:
        elements = _collect(scene, t)
        out.append((t, list(elements)))
    return out


def _collect(scene, type_name):
    # 1) Önce scene.<attr> (dict) — en güvenilir
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

    # 2) iter_elements fallback
    if hasattr(scene, "iter_elements"):
        try:
            return list(scene.iter_elements(type=type_name))
        except (TypeError, AttributeError):
            pass

    # 3) all_elements fallback
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
    """Filtre string'ini (type, id, text) üçlüsüne ayırır."""
    type_hint = None
    id_hint = None
    text = flt

    # "node:xxx" veya "frame:"
    if ":" in text:
        head, tail = text.split(":", 1)
        if head in ("node", "frame", "area", "polygon"):
            type_hint = head
            text = tail.strip()

    # "#123"
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
    # id string'inde de ara
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
        import imgui
        imgui.set_clipboard_text(text)
    except Exception:
        pass




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

        # UI state
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

        # --- View state sıfırla ---
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

    def set_selection(self, elements: List[Any]):
        self.controller.set_filter_type(None)   # controller'ın filtresini sıfırla
        self.controller.set_selection(elements)
        self._form_open_groups.clear()
        for el in (elements or []):
            t = getattr(el, "element_type", type(el).__name__)
            self._tree_open_groups.add(t)
        self._scroll_to_id = _unique_id(elements[0]) if elements else None

        self._sync_scene_selection(elements)   # ← YENİ


    def _sync_scene_selection(self, elements):
        """Inspector seçimini sahne sel_mgr'ine yansıt (ağaçtan seçim için)."""
        app = getattr(self, "app", None)
        if app is None or not getattr(app, "engine", None):
            return
        sel_mgr = getattr(app.engine, "sel_mgr", None)
        if sel_mgr is None:
            return

        # Sonsuz döngü koruması: mevcut seçim zaten aynıysa atla
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
    # Draw — ana giriş
    # ==================================================================
    def draw(self):
        if not self.visible:
            return

        if self._first_open and not self.standalone:
            imgui.set_next_window_position(850, 100, condition=imgui.FIRST_USE_EVER)
            imgui.set_next_window_size(620, 620, condition=imgui.FIRST_USE_EVER)
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
            return    # metin kutusu odakta, karışma

        if imgui.is_key_pressed(imgui.get_key_index(imgui.KEY_ENTER)):
            self.controller.apply()
        elif imgui.is_key_pressed(imgui.get_key_index(imgui.KEY_ESCAPE)):
            self.controller.cancel()
        elif imgui.get_io().key_ctrl and imgui.is_key_pressed(imgui.get_key_index(imgui.KEY_A)):
            # tüm element'leri seç (isteğe bağlı)
            pass
        
    # ==================================================================
    # Gövde
    # ==================================================================
    def _draw_body(self):
        

        avail = imgui.get_content_region_available_width()
        btn_h = imgui.get_frame_height_with_spacing() + 12

        imgui.begin_child("insp_body", height=-float(btn_h), border=False)
        try:
            if self._left_open:
                imgui.begin_child("insp_left", width=self._left_width, border=True)
                try:
                    self._draw_tree()
                finally:
                    imgui.end_child()
                imgui.same_line()

            imgui.begin_child("insp_right", width=0, border=False)
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
        # ("<" if self._left_open else ">")
        if imgui.button("<" if self._left_open else ">"):
            self._left_open = not self._left_open
        imgui.same_line()
        imgui.text_disabled("Elements")
        imgui.separator()

        if self.scene is None:
            imgui.text_colored("scene yok", 0.6, 0.4, 0.4, 1.0)
            return

        # --- filtre ---
        imgui.set_next_item_width(-1)
        _, self._tree_filter = imgui.input_text("##filter", self._tree_filter, 128)
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                "Filtre ipuçları:\n"
                "  n123        → 'n123' içeren label\n"
                "  node:n12    → Node türünde 'n12' içeren\n"
                "  #123        → id=123\n"
                "  frame:      → tüm frame'ler\n"
            )

        # Ctrl+F ile filtre input'una odaklan
        if imgui.is_window_focused() and imgui.get_io().key_ctrl and imgui.is_key_pressed(imgui.get_key_index(imgui.KEY_F)):
            imgui.set_keyboard_focus_here()

        flt = self._tree_filter.strip().lower()

        # Enter ile ilk eşleşmeyi seç
        if imgui.is_item_focused() and imgui.is_key_pressed(imgui.get_key_index(imgui.KEY_ENTER)):
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
                imgui.set_next_item_open(True, imgui.ONCE)
            opened, _ = imgui.collapsing_header(header)
            if not opened:
                continue

            imgui.indent(12)
            MAX = 200
            for el in filtered[:MAX]:
                label = _element_label(el)
                is_selected = el in self.controller.selection.elements

                clicked, _ = imgui.selectable(f"{label}##tree_{id(el)}", is_selected)

                # sağ tık menüsü — BOOL kontrolü + elle end_popup
                ctx = imgui.begin_popup_context_item(f"ctx_{id(el)}")
                if ctx:
                    if imgui.menu_item("Sahneye odakla")[0]:
                        self._focus_in_scene(el)
                    if imgui.menu_item("ID kopyala")[0]:
                        _copy_to_clipboard(str(_unique_id(el)))
                    imgui.separator()
                    if imgui.menu_item("Sadece bunu seç")[0]:
                        self._select_via_scene(el)
                    imgui.end_popup()

                # scroll hedefi
                if getattr(self, "_scroll_to_id", None) == _unique_id(el):
                    imgui.set_scroll_here_y(0.3)
                    self._scroll_to_id = None

                if clicked:
                    self._select_via_scene(el)
                    continue

            if len(filtered) > MAX:
                imgui.text_colored(
                    f"...ve {len(filtered) - MAX} tane daha",
                    0.6, 0.6, 0.6, 1.0,
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

        # ------------------------------------------------------------------
        # 1. Boş seçim
        # ------------------------------------------------------------------
        if c.selection.is_empty:
            imgui.spacing()
            imgui.text_colored("Eleman seçilmedi", 0.5, 0.5, 0.5, 1.0)
            return

        # 2. Assoc filtresi badge (HER ZAMAN görünür — plane seçili değilse "(tümü)")
        self._draw_assoc_filter_bar()
        imgui.separator()
        
        # --- Assoc filtresi badge ---
        if c.filter_assoc_only is not None:
            imgui.text_colored(
                f"! Plane assoc filtresi: {c.filter_assoc_only.name}",
                0.85, 0.75, 0.35, 1.0,
            )
            imgui.same_line()
            if imgui.small_button("✕"):
                c.set_filter_assoc_only(None)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Assoc filtresini kaldır")
            imgui.separator()
            
        # --- Başlık + tip filtresi ---
        counts = c.selection_counts_by_type()
        total = len(c.selection.elements)        # filtresiz toplam
        filtered_total = len(c.filtered_elements)  # filtreli
        if total != filtered_total:
            imgui.text(f"{filtered_total}/{total} eleman gösteriliyor")
        else:
            imgui.text(f"{total} eleman")

        is_multi_type = len(counts) > 1

        if is_multi_type:
            # Filtre aktifse onu göster, yoksa "Hepsi"
            current_label = "Hepsi" if c.filter_type is None else c.filter_type
            # Dropdown item'ları: "Hepsi (N)" + "Node (k)" + "Frame (k)" ...
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
            imgui.same_line(position=200)
            imgui.set_next_item_width(-1)
            changed, new_idx = imgui.combo(
                "##type_filter", cur_idx, items
            )
            if changed and 0 <= new_idx < len(items):
                label = items[new_idx].split(" (")[0]
                c.set_filter_type(label_to_type.get(label))
        else:
            # Tek tip — normal başlık
            el_type = list(counts.keys())[0] if counts else "?"
            imgui.text_colored(f"{el_type}", 0.8, 0.8, 0.4, 1.0)
            imgui.same_line()
            imgui.text_disabled(f"{total} eleman")

        imgui.separator()
        # ------------------------------------------------------------------
        # 2. Başlık bilgisi — HER durumda tanımlı
        # ------------------------------------------------------------------
        if c.selection.is_single:
            el = c.selection.primary
            el_type = type(el).__name__
            el_label = _element_label(el)
        else:
            el_type = "Çoklu seçim"
            el_label = f"{c.selection.count} eleman"

        dirty = self._is_dirty()

        # Sol: tip + label
        imgui.text_colored(el_type, 0.8, 0.8, 0.4, 1.0)
        imgui.same_line()
        imgui.text_disabled(el_label)

        if dirty:
            imgui.same_line()
            imgui.text_colored("●", 0.95, 0.75, 0.30, 1.0)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Kaydedilmemiş değişiklikler var")

        # Sağ: yenile
        imgui.same_line(position=imgui.get_content_region_available_width() - 30)
        if imgui.button("_##refresh"):
            self.refresh()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Sahneden güncel değerleri tekrar oku")

        imgui.separator()

        # ------------------------------------------------------------------
        # 3. Schema yok -> uyar
        # ------------------------------------------------------------------
        if not c.schema:
            imgui.text_colored(
                "Bu element için schema tanımlı değil",
                0.7, 0.5, 0.5, 1.0,
            )
            return

        # ------------------------------------------------------------------
        # 4. Context'i hazırla (her frame yenilenir)
        # ------------------------------------------------------------------
        if not hasattr(self, "_draw_ctx"):
            self._draw_ctx = DrawContext(values=c.selection.values)
        self._draw_ctx.values = c.selection.values
        self._draw_ctx.changed = False


        self._draw_ctx.catalog = self.catalog
        

        # ------------------------------------------------------------------
        # 5. Grupları çiz
        # ------------------------------------------------------------------
        self._group_drawer.open_groups = self._form_open_groups
        for gi, group in enumerate(c.schema):
            self._group_drawer.draw(gi, group, self._draw_ctx)

    def _is_dirty(self) -> bool:
        return self.controller.selection.values != self.controller.selection.original

    def _draw_buttons(self, avail: float, btn_h: float):
        
        dirty = self._is_dirty()

        # Cancel butonuna basılınca onay iste
        if dirty:
            imgui.text_colored("● değişiklikler kaydedilmedi", 0.95, 0.75, 0.30, 1.0)
            imgui.same_line()
            imgui.spacing()
            
        btn_w = (avail - 8) * 0.5
        

        imgui.push_style_color(imgui.COLOR_BUTTON, 0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.60, 0.28, 0.28, 1.0)

        if imgui.button("Cancel", width=btn_w):
            if dirty:
                imgui.open_popup("confirm_cancel")
            else:
                self.controller.cancel()

        if imgui.begin_popup_modal("confirm_cancel", True)[0]:
            imgui.text("Değişiklikler silinsin mi?")
            imgui.spacing()
            if imgui.button("Evet", width=100):
                self.controller.cancel()
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Hayır", width=100):
                imgui.close_current_popup()
            imgui.end_popup()
        
        imgui.pop_style_color(2)

        imgui.same_line()

        imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.68, 0.40, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.35, 0.78, 0.50, 1.0)
        if imgui.button("Apply", width=btn_w):
            
            self.controller.apply()
        imgui.pop_style_color(3)

    def _focus_in_scene(self, el):
        app = getattr(self, "app", None)
        if app is None:
            return
        # CadApp'in engine'inde fit / focus varsa
        try:
            if hasattr(app, "focus_element"):
                app.focus_element(el)
            elif hasattr(app, "engine") and app.engine and hasattr(app.engine, "cam"):
                # en azından seçimi senkronla
                app.engine.sel_mgr.select_only(el)
        except Exception:
            pass

    def _draw_assoc_filter_bar(self):
        """Assoc filtresi: [! Plane: P1 ▾] veya [! Plane: (tümü) ▾]"""
        c = self.controller

        imgui.align_text_to_frame_padding()
        imgui.text_colored("! Plane assoc:", 0.85, 0.75, 0.35, 1.0)
        imgui.same_line()

        planes = c.list_planes()
        if not planes:
            imgui.text_disabled("(projede plane yok)")
            return

        # Item listesi: [(tümü)] + plane isimleri
        labels = ["(tümü)"] + [f"{p.name}  [{sum(len(s) for s in p.associated.values())} assoc]"
                                for p in planes]

        # Aktif index
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
            # Assoc'u yenile (sahne değişmişse)
            if c.filter_assoc_only is not None and c.scene is not None:
                c.filter_assoc_only.refresh_assoc(c.scene)
                c.set_filter_assoc_only(c.filter_assoc_only)  # filter'ı yeniden uygula
                c._rebuild_from_filter()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Assoc'u yeniden hesapla")