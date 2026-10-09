# gui/prop_panel.py
"""
PropertiesPanel — Tek ve çoklu eleman düzenlemesi.

Özellikler:
  - Tek eleman: tam düzenleme
  - Çoklu eleman: ortak alanlar + tipe göre filtre + tipe özel toplu edit
  - Yeni eleman formu (tek/tekrarlı)
  - Apply / Cancel
"""

import numpy as np
from collections import Counter

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import BooleanProperty

from logging_config import CadLogger
logger = CadLogger.get(__name__)


# ============================================================
# GROUP HEADER
# ============================================================

class GroupHeader(ButtonBehavior, Label):
    expanded = BooleanProperty(True)

    def __init__(self, **kwargs):
        kwargs.setdefault('markup', True)
        kwargs.setdefault('halign', 'left')
        kwargs.setdefault('valign', 'middle')
        kwargs.setdefault('font_size', dp(13))
        kwargs.setdefault('font_name', "DejaVuSans.ttf")
        kwargs.setdefault('color', (0.5, 0.8, 1.0, 1.0))
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(28))
        super().__init__(**kwargs)
        self.bind(size=self.setter('text_size'))


# ============================================================
# COLLAPSIBLE GROUP
# ============================================================

class CollapsibleGroup(BoxLayout):
    """Açılır/kapanır grup. Alanlar TextInput olarak eklenir."""

    def __init__(self, title, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('spacing', 0)
        super().__init__(**kwargs)

        self._title_text = title
        self._expanded = True
        self.fields = []

        self.header = GroupHeader(text=self._make_header_text())
        self.header.bind(on_release=self._on_header_click)
        self.add_widget(self.header)

        self.content = GridLayout(
            cols=2,
            size_hint_y=None,
            spacing=dp(2),
            padding=(dp(12), dp(4), dp(4), dp(4)),
        )
        self.content.bind(minimum_height=self.content.setter('height'))
        self.add_widget(self.content)

        self.bind(minimum_height=self.setter('height'))

    def _make_header_text(self):
        arrow = "▼" if self._expanded else "▶"
        return f"[b]{arrow}  {self._title_text}[/b]"

    def _on_header_click(self, *args):
        self.toggle()

    def toggle(self):
        self._expanded = not self._expanded
        self.header.text = self._make_header_text()
        if self._expanded:
            self.content.opacity = 1
            self.content.disabled = False
            self.content.height = self.content.minimum_height
        else:
            self.content.opacity = 0
            self.content.disabled = True
            self.content.height = 0

    def add_field(self, key, value, field_name=None, element=None,
                  editable=False, kind="str"):
        """Gruba label-value satırı ekle."""
        lbl = Label(
            text=str(key),
            size_hint_y=None, height=dp(22),
            halign='left', valign='middle',
            font_size=dp(11), font_name="DejaVuSans.ttf",
            color=(0.85, 0.85, 0.85, 1.0),
        )
        lbl.bind(size=lbl.setter('text_size'))

        val = TextInput(
            text=str(value),
            size_hint_y=None, height=dp(22),
            multiline=False,
            readonly=not editable,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0) if not editable
                             else (0.15, 0.18, 0.24, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
            padding=(dp(4), dp(2), dp(4), dp(2)),
        )
        val._field_name = field_name
        val._element = element
        val._kind = kind

        self.content.add_widget(lbl)
        self.content.add_widget(val)
        self.fields.append(val)


# ============================================================
# PROPERTIES PANEL
# ============================================================

class PropertiesPanel(BoxLayout):

    def __init__(self, controller=None, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('width', dp(320))
        kwargs.setdefault('height', dp(520))
        kwargs.setdefault('padding', dp(6))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)

        self.controller = controller

        # --- State ---
        self._current_element = None
        self._pending_new_type = None
        self._pending_new_repeat = False
        self._selection_elements = None      # çoklu seçim listesi
        self._type_filter = "Tümü"

        self._groups = []
        self._hidden = True

        # Arka plan
        with self.canvas.before:
            Color(0.13, 0.15, 0.20, 0.95)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()
        logger.info("PropertiesPanel oluşturuldu")
        self.hide()

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    # ========================================================
    # UI İNŞASI
    # ========================================================

    def _build_ui(self):
        # Başlık
        title_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(30),
        )
        self.title_label = Label(
            text="Özellikler",
            bold=True, font_size=dp(14),
            font_name="DejaVuSans.ttf",
            halign='left', valign='middle',
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))

        close_btn = Button(
            text="✕",
            size_hint_x=None, width=dp(30),
            font_size=dp(14), font_name="DejaVuSans.ttf",
            background_color=(0.6, 0.2, 0.2, 1.0),
            background_normal='',
        )
        close_btn.bind(on_release=lambda *_: self.hide())

        title_row.add_widget(self.title_label)
        title_row.add_widget(close_btn)
        self.add_widget(title_row)

        # Ayırıcı
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.4, 0.4, 0.4, 0.5)
            self.sep_rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda *_: setattr(self.sep_rect, 'pos', sep.pos),
                 size=lambda *_: setattr(self.sep_rect, 'size', sep.size))
        self.add_widget(sep)

        # Scrollable içerik
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.content_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(2),
        )
        self.content_box.bind(minimum_height=self.content_box.setter('height'))
        scroll.add_widget(self.content_box)
        self.add_widget(scroll)

        # Apply / Cancel
        btn_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(36),
            spacing=dp(4),
        )
        self.cancel_btn = Button(
            text="Cancel",
            background_normal='',
            background_color=(0.45, 0.20, 0.20, 1.0),
            font_size=dp(12), font_name="DejaVuSans.ttf",
        )
        self.cancel_btn.bind(on_release=self._on_cancel)

        self.apply_btn = Button(
            text="Apply",
            background_normal='',
            background_color=(0.20, 0.55, 0.30, 1.0),
            font_size=dp(12), font_name="DejaVuSans.ttf",
            bold=True,
        )
        self.apply_btn.bind(on_release=self._on_apply)

        btn_bar.add_widget(self.cancel_btn)
        btn_bar.add_widget(self.apply_btn)
        self.add_widget(btn_bar)

    # ========================================================
    # APPLY / CANCEL
    # ========================================================

    def _on_apply(self, *_):
        # ---- TOPLU DÜZENLEME ----
        if self._selection_elements:
            self._apply_bulk()
            return

        if self.controller is None:
            logger.warning("controller yok, Apply çalışmaz")
            self._flash("Controller yok", ok=False)
            return

        values = self._collect_field_values()

        # ---- YENİ ELEMAN ----
        if self._pending_new_type is not None:
            result = self.controller.create(self._pending_new_type, values)
            if not result.ok:
                self._flash(result.message, ok=False)
                return
            self._flash(result.message, ok=True)

            if self._pending_new_repeat:
                self._reset_form_after_create()
            else:
                self._current_element = result.element
                self._pending_new_type = None
                self.title_label.text = (
                    f"{getattr(result.element, 'element_type', '?')}: "
                    f"{getattr(result.element, 'label', '?')}"
                )
            return

        # ---- TEK ELEMAN GÜNCELLE ----
        if self._current_element is not None:
            result = self.controller.update(self._current_element, values)
            self._flash(result.message, ok=result.ok)
            return

        self._flash("Düzenlenecek eleman yok", ok=False)

    def _on_cancel(self, *_):
        if self._pending_new_type is not None:
            self._pending_new_type = None
            self._pending_new_repeat = False
            self.hide()
            return
        if self._selection_elements:
            self._selection_elements = None
            self.hide()
            return
        if self._current_element is not None:
            self._build_element_content(self._current_element)
            self._flash("İptal edildi", ok=True)
        else:
            self.hide()

    def _reset_form_after_create(self):
        for group in self._groups:
            for ti in group.fields:
                fname = ti._field_name
                if fname is None:
                    continue
                if fname == "label":
                    ti.text = ""
                elif ti._kind == "float":
                    ti.text = "0.0"
                elif ti._kind == "int":
                    ti.text = "0"
                elif ti._kind == "bool":
                    ti.text = "Serbest"
                else:
                    ti.text = ""
        self.title_label.text = f"YENİ: {self._pending_new_type} (çoklu)"

    def _collect_field_values(self):
        result = {}
        for group in self._groups:
            for ti in group.fields:
                if ti._field_name is None:
                    continue
                result[ti._field_name] = self._parse_value(ti.text, ti._kind)
        return result

    def _parse_value(self, text, kind):
        text = (text or "").strip()
        if kind == "float":
            try:
                return float(text.replace(",", "."))
            except ValueError:
                return 0.0
        if kind == "int":
            try:
                return int(float(text))
            except ValueError:
                return 0
        if kind == "bool":
            return text.lower() in ("1", "true", "evet", "yes", "sabit", "görünür")
        return text

    def _flash(self, msg, ok=True):
        color = (0.4, 0.9, 0.5, 1) if ok else (1.0, 0.5, 0.5, 1)
        old_text = self.title_label.text
        old_color = self.title_label.color
        self.title_label.text = msg
        self.title_label.color = color

        def _restore(dt):
            self.title_label.text = old_text
            self.title_label.color = old_color

        Clock.schedule_once(_restore, 1.5)

    # ========================================================
    # TEK ELEMAN İÇERİĞİ
    # ========================================================

    def _build_element_content(self, element):
        self._selection_elements = None
        self.content_box.clear_widgets()
        self._groups.clear()

        et = getattr(element, 'element_type', '?').lower()

        # Genel
        g = CollapsibleGroup("Genel")
        g.add_field("Tip", element.element_type)
        g.add_field("Label", getattr(element, 'label', '-'),
                    field_name="label", element=element,
                    editable=True, kind="str")
        g.add_field("ID", element.unique_id)

        color = getattr(element, 'color', [0.7, 0.7, 0.7])
        color_str = ",".join(f"{float(c):.2f}" for c in color[:3])
        g.add_field("color (R,G,B)", color_str,
                    field_name="color", element=element,
                    editable=True, kind="color")
        g.add_field("Visible", "Görünür" if element.is_visible else "Gizli",
                    field_name="is_visible", element=element,
                    editable=True, kind="bool")
        self._add_group(g)

        if et == 'node':
            self._build_node_content(element)
        elif et == 'frame':
            self._build_frame_content(element)
        elif et == 'link':
            self._build_link_content(element)
        elif et == 'area':
            self._build_area_content(element)
        elif et == 'polygon':
            self._build_polygon_content(element)

    def _add_group(self, group):
        self.content_box.add_widget(group)
        self._groups.append(group)

    # ---------- NODE ----------
    def _build_node_content(self, node):
        g = CollapsibleGroup("Konum")
        g.add_field("X", f"{node.x:.3f}", field_name="x",
                    element=node, editable=True, kind="float")
        g.add_field("Y", f"{node.y:.3f}", field_name="y",
                    element=node, editable=True, kind="float")
        g.add_field("Z", f"{node.z:.3f}", field_name="z",
                    element=node, editable=True, kind="float")
        self._add_group(g)

        g = CollapsibleGroup("Restraint")
        if node.restraint:
            for name in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
                current = getattr(node.restraint, name, False)
                g.add_field(name.upper(),
                            "Sabit" if current else "Serbest",
                            field_name=f"restraint.{name}",
                            element=node, editable=True, kind="bool")
        else:
            g.add_field("-", "Serbest")
        self._add_group(g)

        if hasattr(node, 'connected') and node.connected:
            g = CollapsibleGroup(f"Bağlı Elemanlar ({len(node.connected)})")
            for obj_type, elem_id in node.connected[:10]:
                g.add_field(obj_type.name, str(elem_id)[:8])
            if len(node.connected) > 10:
                g.add_field("...", f"+{len(node.connected) - 10} daha")
            self._add_group(g)
            g.toggle()

    # ---------- FRAME ----------
    def _build_frame_content(self, frame):
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", frame.node_i.label)
        g.add_field("Node J", frame.node_j.label)
        g.add_field("Uzunluk", f"{frame.get_length():.2f}")
        g.add_field("Rotation", f"{frame.rotation_deg:.1f}°",
                    field_name="rotation_deg", element=frame,
                    editable=True, kind="float")
        self._add_group(g)

        if frame.section:
            sec = frame.section
            g = CollapsibleGroup(f"Kesit: {sec.name}")
            g.add_field("Ad", sec.name)
            g.add_field("Tip", str(getattr(sec, 'profile_type', '-')))

            if getattr(sec, 'profile_params', None):
                important = ['h', 'b', 'tw', 'tf', 't', 'ro', 'ri', 'n']
                for key in important:
                    if key in sec.profile_params:
                        g.add_field(key, self._fmt(sec.profile_params[key]))
            self._add_group(g)
            g.toggle()

        if getattr(frame, 'release_i', None) or getattr(frame, 'release_j', None):
            g = CollapsibleGroup("Release")
            for end, rel in [("I", frame.release_i), ("J", frame.release_j)]:
                if rel:
                    active = [k for k, v in rel.items() if v]
                    if active:
                        g.add_field(f"Uç {end}", ", ".join(active))
            self._add_group(g)

    def _fmt(self, val):
        if isinstance(val, (int, float)):
            if val == 0:
                return "0"
            if abs(val) > 1e6 or abs(val) < 1e-3:
                return f"{val:.3e}"
            return f"{val:.4f}" if isinstance(val, float) else str(val)
        return str(val)

    # ---------- LINK ----------
    def _build_link_content(self, link):
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", link.node_i.label)
        g.add_field("Node J", link.node_j.label)
        self._add_group(g)

        g = CollapsibleGroup("Property")
        g.add_field("Prop", getattr(link, 'propname', '-'),
                    field_name="propname", element=link,
                    editable=True, kind="str")
        self._add_group(g)

    # ---------- AREA ----------
    def _build_area_content(self, area):
        g = CollapsibleGroup("Geometri")
        g.add_field("Kalınlık", f"{area.thickness:.2f}",
                    field_name="thickness", element=area,
                    editable=True, kind="float")
        g.add_field("Köşe sayısı", len(area.nodes))
        self._add_group(g)

        g = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(area.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label}  ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})")
        self._add_group(g)

    # ---------- POLYGON ----------
    def _build_polygon_content(self, polygon):
        g = CollapsibleGroup("Poligon Bilgileri")
        type_name = (polygon.poly_type.name
                     if hasattr(polygon.poly_type, 'name')
                     else str(polygon.poly_type))
        g.add_field("Poligon Tipi", type_name,
                    field_name="poly_type", element=polygon,
                    editable=True, kind="str")
        g.add_field("Köşe sayısı", len(polygon.nodes))
        self._add_group(g)

        if getattr(polygon, "windplane", None):
            wp = polygon.windplane
            g = CollapsibleGroup("Rüzgar Bölgesi")
            g.add_field("Zone Etiketi", wp.get("label", "-"))
            g.add_field("Yüzey", wp.get("surface", "-"))
            g.add_field("Tablo Tipi", wp.get("table_type", "-"))

            def fmt_cpe(val):
                if val is None:
                    return "-"
                if isinstance(val, (tuple, list, np.ndarray)):
                    return "[" + ", ".join(
                        f"{v:.3f}" if isinstance(v, (int, float)) else str(v)
                        for v in val) + "]"
                if isinstance(val, (int, float)):
                    return f"{val:.3f}"
                return str(val)

            if wp.get("cpe10") is not None:
                g.add_field("Cpe,10", fmt_cpe(wp["cpe10"]))
            if wp.get("cpe1") is not None:
                g.add_field("Cpe,1", fmt_cpe(wp["cpe1"]))
            if "pitch" in wp:
                g.add_field("Eğim (°)", f"{wp['pitch']:.1f}")
            self._add_group(g)

        g = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(polygon.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label} ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})")
        self._add_group(g)
        g.toggle()

    # ========================================================
    # ÇOKLU SEÇİM — MULTI EDIT
    # ========================================================

    def show_selection_summary(self, elements):
        """Seçili elemanlar için ortak + tip-bazlı edit alanları."""
        self._current_element = None
        self._pending_new_type = None
        self._selection_elements = list(elements)
        self._type_filter = "Tümü"

        self._rebuild_selection_ui()
        self.show()

    def _rebuild_selection_ui(self):
        elements = self._selection_elements or []
        self.content_box.clear_widgets()
        self._groups.clear()

        if not elements:
            return

        # Başlık + tip filtresi
        self._build_selection_header(elements)

        # Ortak alanlar
        self._build_common_fields(elements)

        # Tip dağılımı + tipe özel alanlar
        types = Counter(getattr(e, 'element_type', '?') for e in elements)
        filter_type = self._type_filter

        if filter_type != "Tümü":
            filtered = [e for e in elements
                        if getattr(e, 'element_type', None) == filter_type]
            self._build_type_specific_fields(filtered, filter_type)
        elif len(types) == 1:
            only = next(iter(types))
            self._build_type_specific_fields(elements, only)
        else:
            g = CollapsibleGroup("Tip Dağılımı")
            for et, count in sorted(types.items()):
                g.add_field(et, count)
            self._add_group(g)

        self.title_label.text = f"{len(elements)} eleman seçili"

    def _build_selection_header(self, elements):
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(30),
            spacing=dp(6),
        )

        total_lbl = Label(
            text=f"{len(elements)} eleman",
            size_hint_x=0.5, font_size=dp(12),
            halign='left', valign='middle',
        )
        total_lbl.bind(size=total_lbl.setter('text_size'))
        header.add_widget(total_lbl)

        types = sorted(set(getattr(e, 'element_type', '?') for e in elements))
        values = ["Tümü"] + types

        spinner = Spinner(
            text=self._type_filter,
            values=values,
            size_hint_x=0.5,
            font_size=dp(11),
        )
        spinner.bind(text=self._on_type_filter_changed)
        header.add_widget(spinner)

        self.content_box.add_widget(header)

    def _on_type_filter_changed(self, spinner, text):
        self._type_filter = text
        self._rebuild_selection_ui()

    def _build_common_fields(self, elements):
        g = CollapsibleGroup("Ortak Özellikler")

        # is_visible
        vis_values = [bool(getattr(e, 'is_visible', True)) for e in elements]
        vis_display = self._common_or_mixed(
            vis_values, formatter=lambda v: "Görünür" if v else "Gizli")
        g.add_field("is_visible", vis_display,
                    field_name="_bulk.is_visible",
                    element=None, editable=True, kind="bool")

        # label
        labels = [str(getattr(e, 'label', "")) for e in elements]
        g.add_field("label", self._common_or_mixed(labels),
                    field_name="_bulk.label",
                    element=None, editable=True, kind="str")

        # color
        color_strs = []
        for e in elements:
            c = getattr(e, 'color', [0.7, 0.7, 0.7])
            color_strs.append(",".join(f"{float(v):.2f}" for v in c[:3]))
        g.add_field("color (R,G,B)", self._common_or_mixed(color_strs),
                    field_name="_bulk.color",
                    element=None, editable=True, kind="color")

        self._add_group(g)

    def _build_type_specific_fields(self, elements, element_type):
        if element_type == "Node":
            self._build_bulk_node_fields(elements)
        elif element_type == "Frame":
            self._build_bulk_frame_fields(elements)
        elif element_type == "Area":
            self._build_bulk_area_fields(elements)
        elif element_type == "Polygon":
            self._build_bulk_polygon_fields(elements)
        elif element_type == "Link":
            self._build_bulk_link_fields(elements)

    def _build_bulk_node_fields(self, nodes):
        g = CollapsibleGroup(f"Node Alanları ({len(nodes)} adet)")
        for field in ('x', 'y', 'z'):
            values = [float(getattr(n, field, 0.0)) for n in nodes]
            display = self._common_or_mixed(values,
                                            formatter=lambda v: f"{v:.3f}")
            g.add_field(field, display,
                        field_name=f"_bulk.{field}",
                        element=None, editable=True, kind="float")
        self._add_group(g)

        g2 = CollapsibleGroup("Restraint")
        for dof in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
            values = []
            for n in nodes:
                if getattr(n, 'restraint', None) is not None:
                    values.append(bool(getattr(n.restraint, dof, False)))
                else:
                    values.append(False)
            display = self._common_or_mixed(
                values, formatter=lambda v: "Sabit" if v else "Serbest")
            g2.add_field(dof.upper(), display,
                         field_name=f"_bulk.restraint.{dof}",
                         element=None, editable=True, kind="bool")
        self._add_group(g2)

    def _build_bulk_frame_fields(self, frames):
        g = CollapsibleGroup(f"Frame Alanları ({len(frames)} adet)")

        sec_names = []
        for f in frames:
            if getattr(f, 'section', None) is not None:
                sec_names.append(getattr(f.section, 'name', ""))
            else:
                sec_names.append("")
        g.add_field("section_name", self._common_or_mixed(sec_names),
                    field_name="_bulk.section_name",
                    element=None, editable=True, kind="str")

        rots = [float(getattr(f, 'rotation_deg', 0.0)) for f in frames]
        g.add_field("rotation_deg",
                    self._common_or_mixed(rots, formatter=lambda v: f"{v:.2f}"),
                    field_name="_bulk.rotation_deg",
                    element=None, editable=True, kind="float")
        self._add_group(g)

    def _build_bulk_area_fields(self, areas):
        g = CollapsibleGroup(f"Area Alanları ({len(areas)} adet)")
        ths = [float(getattr(a, 'thickness', 0.0)) for a in areas]
        g.add_field("thickness",
                    self._common_or_mixed(ths, formatter=lambda v: f"{v:.3f}"),
                    field_name="_bulk.thickness",
                    element=None, editable=True, kind="float")
        self._add_group(g)

    def _build_bulk_link_fields(self, links):
        g = CollapsibleGroup(f"Link Alanları ({len(links)} adet)")
        props = [str(getattr(l, 'propname', "")) for l in links]
        g.add_field("propname", self._common_or_mixed(props),
                    field_name="_bulk.propname",
                    element=None, editable=True, kind="str")
        self._add_group(g)

    def _build_bulk_polygon_fields(self, polys):
        g = CollapsibleGroup(f"Polygon Alanları ({len(polys)} adet)")
        types_str = []
        for p in polys:
            t = getattr(p, 'poly_type', None)
            types_str.append(t.name if hasattr(t, 'name') else str(t))
        g.add_field("poly_type", self._common_or_mixed(types_str),
                    field_name="_bulk.poly_type",
                    element=None, editable=True, kind="str")
        self._add_group(g)

    def _common_or_mixed(self, values, formatter=None):
        """Hepsi aynı → o değer; farklı → [KARIŞIK]."""
        if not values:
            return "[BOŞ]"
        first = values[0]
        try:
            same = all(v == first for v in values[1:])
        except Exception:
            same = False
        if same:
            return formatter(first) if formatter else str(first)
        return "[KARIŞIK]"

    # ---------- BULK APPLY ----------
    def _apply_bulk(self):
        if self.controller is None:
            self._flash("Controller yok", ok=False)
            return

        elements = list(self._selection_elements or [])
        if self._type_filter != "Tümü":
            elements = [e for e in elements
                        if getattr(e, 'element_type', None) == self._type_filter]

        if not elements:
            self._flash("Filtreye uyan eleman yok", ok=False)
            return

        # Değişiklikleri topla
        changes = {}
        for group in self._groups:
            for ti in group.fields:
                fname = getattr(ti, '_field_name', None)
                if not fname or not fname.startswith("_bulk."):
                    continue
                text = (ti.text or "").strip()
                if text in ("", "[KARIŞIK]", "[BOŞ]"):
                    continue
                field = fname[len("_bulk."):]
                try:
                    changes[field] = self._parse_bulk_value(text, ti._kind, field)
                except Exception as e:
                    self._flash(f"Hatalı değer ({field}): {e}", ok=False)
                    return

        if not changes:
            self._flash("Değişiklik yok", ok=False)
            return

        result = self.controller.bulk_update(elements, changes)
        if result is None:
            self._flash("Bulk update başarısız", ok=False)
            return
        if hasattr(result, 'ok') and not result.ok:
            self._flash(result.message, ok=False)
            return
        self._flash(f"{len(elements)} eleman güncellendi", ok=True)

        # Yeniden çiz
        self._rebuild_selection_ui()

    def _parse_bulk_value(self, text, kind, field):
        text = text.strip()
        if field == "color":
            parts = [p.strip() for p in text.split(",")]
            if len(parts) != 3:
                raise ValueError("renk 'R,G,B' olmalı")
            return [float(p) for p in parts]
        if kind == "float":
            return float(text.replace(",", "."))
        if kind == "int":
            return int(float(text))
        if kind == "bool":
            return text.lower() in (
                "1", "true", "evet", "yes", "sabit", "görünür", "visible")
        return text

    # ========================================================
    # YENİ ELEMAN
    # ========================================================

    def show_new_element(self, element_type, defaults=None, repeat=False):
        self._current_element = None
        self._selection_elements = None
        self._pending_new_type = element_type
        self._pending_new_repeat = repeat
        self.title_label.text = (
            f"YENİ: {element_type}" + (" (çoklu)" if repeat else "")
        )

        self.content_box.clear_widgets()
        self._groups.clear()

        g = CollapsibleGroup(f"Yeni {element_type}")
        for k, v in (defaults or {}).items():
            kind = self._infer_kind(v)
            g.add_field(k, str(v), field_name=k, element=None,
                        editable=True, kind=kind)
        self._add_group(g)
        self.show()

    def _infer_kind(self, v):
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        return "str"

    # ========================================================
    # SHOW / HIDE
    # ========================================================

    def show_element(self, element):
        if element is None:
            return
        self._current_element = element
        self._selection_elements = None
        self._pending_new_type = None
        self.title_label.text = (
            f"{element.element_type}: {getattr(element, 'label', '?')}"
        )
        self._build_element_content(element)
        self.show()

    def hide(self):
        self.opacity = 0
        self.disabled = True
        self._current_element = None
        self._pending_new_type = None
        self._pending_new_repeat = False
        self._selection_elements = None
        self._hidden = True

    def show(self):
        self.opacity = 1.0
        self.disabled = False
        self._hidden = False

    def on_touch_down(self, touch):
        if self._hidden:
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._hidden:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._hidden:
            return False
        return super().on_touch_up(touch)