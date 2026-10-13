# gui/prop_panel.py
"""
PropertiesPanel — Tek ve çoklu eleman düzenlemesi (tip duyarlı).
"""
import numpy as np
from collections import Counter
from enum import Enum

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
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

from gui.widgets.field_row import FieldRow
from logging_config import CadLogger

# Enum tipleri (combobox için)
from domain.definition import (
    MatType, SectionType, LinkPropType, PropAreaType, SymType,
    LoadPatternType, LoadCaseType, ComboType, SpectrumSourceType,
    SAP_FRAME_LOAD_DIRECTION, LoadDirection,
)
from domain.element import PolygonType

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
    """Açılır/kapanır grup. Alanlar tip duyarlı FieldRow olarak eklenir."""

    def __init__(self, title, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('spacing', 0)
        super().__init__(**kwargs)

        self._title_text = title
        self._expanded = True
        self.fields = []  # FieldRow listesi

        self.header = GroupHeader(text=self._make_header_text())
        self.header.bind(on_release=self._on_header_click)
        self.add_widget(self.header)

        self.content = GridLayout(
            cols=1,                     # FieldRow tek satır olduğu için 1 kolon
            size_hint_y=None,
            spacing=dp(2),
            padding=(dp(8), dp(4), dp(4), dp(4)),
        )
        self.content.bind(minimum_height=self.content.setter('height'))
        self.add_widget(self.content)

        self.bind(minimum_height=self.setter('height'))

    def _make_header_text(self):
        # "   Oklar:      ►  ◄  ▲  ▼"

        arrow = "V" if self._expanded else "▶"
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

    def add_field(self, key, value, *, kind=None, choices=None,
                  field_name=None, element=None, editable=False):
        if kind is None:
            kind = self._infer_kind(value)

        row = FieldRow(
            key=key,
            value=value,
            kind=kind,
            choices=choices,
            field_name=field_name,
            element=element,
            editable=editable,
        )
        self.content.add_widget(row)
        self.fields.append(row)
        return row

    @staticmethod
    def _infer_kind(value):
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, Enum):
            return "enum"
        if isinstance(value, float):
            return "float"
        if isinstance(value, int):
            return "int"
        if isinstance(value, (list, tuple)) and len(value) == 3 \
                and all(isinstance(v, (int, float)) for v in value):
            return "color"
        return "str"


# ============================================================
# PROPERTIES PANEL
# ============================================================

class PropertiesPanel(BoxLayout):

    def __init__(self, controller=None, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('width', dp(340))
        kwargs.setdefault('height', dp(560))
        kwargs.setdefault('padding', dp(6))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)

        self.controller = controller
        self._current_element = None
        self._pending_new_type = None
        self._pending_new_repeat = False
        self._selection_elements = None
        self._type_filter = "Tümü"
        self._groups = []
        self._hidden = True

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
        title_row = BoxLayout(orientation='horizontal',
                              size_hint_y=None, height=dp(30))
        self.title_label = Label(
            text="Özellikler", bold=True, font_size=dp(14),
            font_name="DejaVuSans.ttf", halign='left', valign='middle',
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))

        close_btn = Button(
            text="✕", size_hint_x=None, width=dp(30),
            font_size=dp(14), font_name="DejaVuSans.ttf",
            background_color=(0.6, 0.2, 0.2, 1.0), background_normal='',
        )
        close_btn.bind(on_release=lambda *_: self.hide())

        title_row.add_widget(self.title_label)
        title_row.add_widget(close_btn)
        self.add_widget(title_row)

        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.4, 0.4, 0.4, 0.5)
            self.sep_rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda *_: setattr(self.sep_rect, 'pos', sep.pos),
                 size=lambda *_: setattr(self.sep_rect, 'size', sep.size))
        self.add_widget(sep)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.content_box = BoxLayout(orientation='vertical',
                                     size_hint_y=None, spacing=dp(2))
        self.content_box.bind(minimum_height=self.content_box.setter('height'))
        scroll.add_widget(self.content_box)
        self.add_widget(scroll)

        btn_bar = BoxLayout(orientation='horizontal',
                            size_hint_y=None, height=dp(36), spacing=dp(4))
        self.cancel_btn = Button(
            text="Cancel", background_normal='',
            background_color=(0.45, 0.20, 0.20, 1.0),
            font_size=dp(12), font_name="DejaVuSans.ttf",
        )
        self.cancel_btn.bind(on_release=self._on_cancel)

        self.apply_btn = Button(
            text="Apply", background_normal='',
            background_color=(0.20, 0.55, 0.30, 1.0),
            font_size=dp(12), font_name="DejaVuSans.ttf", bold=True,
        )
        self.apply_btn.bind(on_release=self._on_apply)

        btn_bar.add_widget(self.cancel_btn)
        btn_bar.add_widget(self.apply_btn)
        self.add_widget(btn_bar)

    # ========================================================
    # APPLY / CANCEL
    # ========================================================

    def _on_apply(self, *_):
        if self._selection_elements:
            self._apply_bulk()
            return

        if self.controller is None:
            self._flash("Controller yok", ok=False)
            return

        try:
            values = self._collect_field_values()
        except ValueError as e:
            self._flash(str(e), ok=False)
            return

        logger.info("Apply değerleri: %s", values)

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

        if self._current_element is not None:
            result = self.controller.update(self._current_element, values)
            if result is None:
                self._flash("update None döndü", ok=False)
                return
            self._flash(getattr(result, 'message', 'Tamam'),
                        ok=getattr(result, 'ok', True))
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
            for row in group.fields:
                fn = row._field_name
                if fn is None:
                    continue
                if fn == "label":
                    row.set_value("")
                elif row._kind == "float":
                    row.set_value(0.0)
                elif row._kind == "int":
                    row.set_value(0)
                elif row._kind == "bool":
                    row.set_value(False)
                elif row._kind == "enum" and row._choices:
                    row.set_value(str(row._choices[0]))
                else:
                    row.set_value("")
        self.title_label.text = f"YENİ: {self._pending_new_type} (çoklu)"

    def _collect_field_values(self):
        """FieldRow'lardan değerleri toplar. Noktalı anahtarları düz tutar
        (controller nested set yapabilsin diye)."""
        result = {}
        for group in self._groups:
            for row in group.fields:
                fn = row._field_name
                if fn is None:
                    continue
                result[fn] = row.get_value()
        return result

    def _flash(self, msg, ok=True):
        color = (0.4, 0.9, 0.5, 1) if ok else (1.0, 0.5, 0.5, 1)
        old_text, old_color = self.title_label.text, self.title_label.color
        self.title_label.text = msg
        self.title_label.color = color

        def _restore(dt):
            self.title_label.text = old_text
            self.title_label.color = old_color

        Clock.schedule_once(_restore, 1.5)

    # ========================================================
    # TEK ELEMAN İÇERİĞİ — TİP DUYARLI OTOMATİK ÜRETİM
    # ========================================================

    def _build_element_content(self, element):
        self._selection_elements = None
        self.content_box.clear_widgets()
        self._groups.clear()

        et = getattr(element, 'element_type', '?').lower()

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
        else:
            self._build_generic_content(element)

    def _add_group(self, group):
        self.content_box.add_widget(group)
        self._groups.append(group)

    # ---------- ORTAK ALANLAR ----------
    def _add_common_fields(self, g, element):
        g.add_field("Tip", element.element_type, kind="str")
        g.add_field("Label", getattr(element, 'label', '-'),
                    field_name="label", element=element,
                    editable=True, kind="str")
        g.add_field("ID", element.unique_id, kind="int")

        color = getattr(element, 'color', [0.7, 0.7, 0.7])
        g.add_field("color (R,G,B)", list(color[:3]),
                    field_name="color", element=element,
                    editable=True, kind="color")
        g.add_field("is_visible", bool(getattr(element, 'is_visible', True)),
                    field_name="is_visible", element=element,
                    editable=True, kind="bool")

    # ---------- NODE ----------
    def _build_node_content(self, node):
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, node)
        self._add_group(g)

        g = CollapsibleGroup("Konum")
        g.add_field("X", float(node.x), field_name="x",
                    element=node, editable=True, kind="float")
        g.add_field("Y", float(node.y), field_name="y",
                    element=node, editable=True, kind="float")
        g.add_field("Z", float(node.z), field_name="z",
                    element=node, editable=True, kind="float")
        self._add_group(g)

        # Mass (6 dof)
        g = CollapsibleGroup("Kütle (Mass)")
        for i, name in enumerate(("Mx", "My", "Mz", "Mrx", "Mry", "Mrz")):
            val = float(node.mass[i]) if i < len(node.mass) else 0.0
            g.add_field(name, val, field_name=f"mass.{i}",
                        element=node, editable=True, kind="float")
        self._add_group(g)
        g.toggle()

        # Restraint
        g = CollapsibleGroup("Restraint")
        if node.restraint is not None:
            for name in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
                cur = bool(getattr(node.restraint, name, False))
                g.add_field(name.upper(), cur,
                            field_name=f"restraint.{name}",
                            element=node, editable=True, kind="bool")
        else:
            for name in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
                g.add_field(name.upper(), False,
                            field_name=f"restraint.{name}",
                            element=node, editable=True, kind="bool")
        self._add_group(g)

        # Bağlı elemanlar
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
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, frame)
        self._add_group(g)

        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", frame.node_i.label, kind="str")
        g.add_field("Node J", frame.node_j.label, kind="str")
        g.add_field("Uzunluk", float(frame.get_length()), kind="float")
        g.add_field("Rotation (deg)", float(getattr(frame, 'rotation_deg', 0.0)),
                    field_name="rotation_deg", element=frame,
                    editable=True, kind="float")
        self._add_group(g)

        if getattr(frame, 'section', None) is not None:
            sec = frame.section
            g = CollapsibleGroup(f"Kesit: {sec.name}")

            # SectionType enum → combobox
            g.add_field("profile_type", sec.profile_type,
                        choices=list(SectionType),
                        field_name="section.profile_type",
                        element=frame, editable=True, kind="enum")
            g.add_field("Kesit Adı", sec.name, kind="str")

            if getattr(sec, 'material', None) is not None:
                g.add_field("Malzeme", sec.material.name, kind="str")

            if getattr(sec, 'profile_params', None):
                for key, val in sec.profile_params.items():
                    g.add_field(key, self._as_float_or_str(val),
                                field_name=f"section.profile_params.{key}",
                                element=frame, editable=True,
                                kind="float" if isinstance(val, (int, float))
                                else "str")
            self._add_group(g)

        if getattr(frame, 'release_i', None) or getattr(frame, 'release_j', None):
            g = CollapsibleGroup("Release")
            for end, rel in [("I", frame.release_i), ("J", frame.release_j)]:
                if rel:
                    for k, v in rel.items():
                        g.add_field(f"{end}.{k}", bool(v),
                                    field_name=f"release_{end.lower()}.{k}",
                                    element=frame, editable=True, kind="bool")
            self._add_group(g)

    # ---------- LINK ----------
    def _build_link_content(self, link):
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, link)
        self._add_group(g)

        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", link.node_i.label, kind="str")
        g.add_field("Node J", link.node_j.label, kind="str")
        self._add_group(g)

        g = CollapsibleGroup("Link Property")
        g.add_field("propname", getattr(link, 'propname', '-'),
                    field_name="propname", element=link,
                    editable=True, kind="str")
        # prop_type spinner (varsa)
        prop_type = getattr(link, 'prop_type', None)
        if prop_type is not None:
            g.add_field("prop_type", prop_type,
                        choices=list(LinkPropType),
                        field_name="prop_type", element=link,
                        editable=True, kind="enum")
        self._add_group(g)

    # ---------- AREA ----------
    def _build_area_content(self, area):
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, area)
        self._add_group(g)

        g = CollapsibleGroup("Geometri")
        g.add_field("Kalınlık", float(area.thickness),
                    field_name="thickness", element=area,
                    editable=True, kind="float")
        g.add_field("Köşe sayısı", len(area.nodes), kind="int")
        self._add_group(g)

        g = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(area.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label}  ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})",
                        kind="str")
        self._add_group(g)
        g.toggle()

    # ---------- POLYGON ----------
    def _build_polygon_content(self, polygon):
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, polygon)
        self._add_group(g)

        g = CollapsibleGroup("Poligon Bilgileri")
        g.add_field("poly_type", polygon.poly_type,
                    choices=list(PolygonType),
                    field_name="poly_type", element=polygon,
                    editable=True, kind="enum")
        g.add_field("Köşe sayısı", len(polygon.nodes), kind="int")
        self._add_group(g)

        if getattr(polygon, "windplane", None):
            wp = polygon.windplane
            g = CollapsibleGroup("Rüzgar Bölgesi")
            for key, val in wp.items():
                kind, choices = self._guess_kind_from_windplane(key, val)
                g.add_field(key, val,
                            choices=choices,
                            field_name=f"windplane.{key}",
                            element=polygon, editable=True, kind=kind)
            self._add_group(g)

        g = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(polygon.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label} ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})",
                        kind="str")
        self._add_group(g)
        g.toggle()

    def _guess_kind_from_windplane(self, key, val):
        """windplane sözlüğündeki alanlar için tahmini tip."""
        if key in ("surface",):
            return "enum", ["windward", "leeward", "side", "roof", "top", "bottom"]
        if key in ("table_type",):
            return "enum", ["Walls", "Flat Roofs", "Monopitch", "Duopitch",
                            "Hipped", "Troughed", "Arched"]
        if key in ("label", "table"):
            return "str", None
        if key == "pitch":
            return "float", None
        if key.startswith("cpe"):
            return "str", None
        if isinstance(val, bool):
            return "bool", None
        if isinstance(val, float):
            return "float", None
        if isinstance(val, int):
            return "int", None
        return "str", None

    # ---------- GENERIC ----------
    def _build_generic_content(self, element):
        g = CollapsibleGroup("Genel")
        self._add_common_fields(g, element)
        self._add_group(g)

        g = CollapsibleGroup("Tüm Alanlar (salt okunur)")
        for key, val in vars(element).items():
            if key.startswith('_') or key in (
                'unique_id', 'element_id', 'is_selected', 'is_visible',
                'needs_update', 'pick_id', 'element_type', 'label', 'color',
            ):
                continue
            if callable(val):
                continue
            kind = CollapsibleGroup._infer_kind(val)
            if kind == "enum":
                g.add_field(key, val, choices=list(type(val)),
                            kind="enum")
            else:
                g.add_field(key, val, kind=kind)
        self._add_group(g)
        g.toggle()

    @staticmethod
    def _as_float_or_str(val):
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return float(val)
        return str(val)

    # ========================================================
    # ÇOKLU SEÇİM — MULTI EDIT
    # ========================================================

    def show_selection_summary(self, elements):
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

        self._build_selection_header(elements)
        self._build_common_fields(elements)

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
                g.add_field(et, count, kind="int")
            self._add_group(g)

        self.title_label.text = f"{len(elements)} eleman seçili"

    def _build_selection_header(self, elements):
        header = BoxLayout(orientation='horizontal',
                           size_hint_y=None, height=dp(30), spacing=dp(6))
        total_lbl = Label(text=f"{len(elements)} eleman",
                          size_hint_x=0.5, font_size=dp(12),
                          halign='left', valign='middle')
        total_lbl.bind(size=total_lbl.setter('text_size'))
        header.add_widget(total_lbl)

        types = sorted(set(getattr(e, 'element_type', '?') for e in elements))
        spinner = Spinner(text=self._type_filter, values=["Tümü"] + types,
                          size_hint_x=0.5, font_size=dp(11))
        spinner.bind(text=self._on_type_filter_changed)
        header.add_widget(spinner)
        self.content_box.add_widget(header)

    def _on_type_filter_changed(self, spinner, text):
        self._type_filter = text
        self._rebuild_selection_ui()

    def _build_common_fields(self, elements):
        g = CollapsibleGroup("Ortak Özellikler")

        vis_vals = [bool(getattr(e, 'is_visible', True)) for e in elements]
        vis_disp = self._common_or_mixed(vis_vals)
        if vis_disp == "[KARIŞIK]":
            g.add_field("is_visible", vis_disp,
                        field_name="_bulk.is_visible",
                        editable=True, kind="bool")
        else:
            g.add_field("is_visible", bool(vis_vals[0]),
                        field_name="_bulk.is_visible",
                        editable=True, kind="bool")

        labels = [str(getattr(e, 'label', "")) for e in elements]
        disp = self._common_or_mixed(labels)
        if disp == "[KARIŞIK]":
            g.add_field("label", disp, field_name="_bulk.label",
                        editable=True, kind="str")
        else:
            g.add_field("label", labels[0], field_name="_bulk.label",
                        editable=True, kind="str")

        colors = []
        for e in elements:
            c = getattr(e, 'color', [0.7, 0.7, 0.7])
            colors.append([float(v) for v in c[:3]])
        disp = self._common_or_mixed(colors)
        if disp == "[KARIŞIK]":
            g.add_field("color (R,G,B)", "[KARIŞIK]",
                        field_name="_bulk.color",
                        editable=True, kind="color")
        else:
            g.add_field("color (R,G,B)", colors[0],
                        field_name="_bulk.color",
                        editable=True, kind="color")

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
            vals = [float(getattr(n, field, 0.0)) for n in nodes]
            disp = self._common_or_mixed(vals)
            if disp == "[KARIŞIK]":
                g.add_field(field, disp, field_name=f"_bulk.{field}",
                            editable=True, kind="float")
            else:
                g.add_field(field, vals[0], field_name=f"_bulk.{field}",
                            editable=True, kind="float")
        self._add_group(g)

        g2 = CollapsibleGroup("Restraint")
        for dof in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
            vals = []
            for n in nodes:
                r = getattr(n, 'restraint', None)
                vals.append(bool(getattr(r, dof, False)) if r else False)
            disp = self._common_or_mixed(vals)
            if disp == "[KARIŞIK]":
                g2.add_field(dof.upper(), False,
                             field_name=f"_bulk.restraint.{dof}",
                             editable=True, kind="bool")
            else:
                g2.add_field(dof.upper(), vals[0],
                             field_name=f"_bulk.restraint.{dof}",
                             editable=True, kind="bool")
        self._add_group(g2)

    def _build_bulk_frame_fields(self, frames):
        g = CollapsibleGroup(f"Frame Alanları ({len(frames)} adet)")
        sec_names = [getattr(f.section, 'name', '') if getattr(f, 'section', None) else ''
                     for f in frames]
        disp = self._common_or_mixed(sec_names)
        g.add_field("section_name", disp if disp != "[KARIŞIK]" else "",
                    field_name="_bulk.section_name",
                    editable=True, kind="str")

        rots = [float(getattr(f, 'rotation_deg', 0.0)) for f in frames]
        disp = self._common_or_mixed(rots)
        if disp == "[KARIŞIK]":
            g.add_field("rotation_deg", "[KARIŞIK]",
                        field_name="_bulk.rotation_deg",
                        editable=True, kind="float")
        else:
            g.add_field("rotation_deg", rots[0],
                        field_name="_bulk.rotation_deg",
                        editable=True, kind="float")
        self._add_group(g)

    def _build_bulk_area_fields(self, areas):
        g = CollapsibleGroup(f"Area Alanları ({len(areas)} adet)")
        ths = [float(getattr(a, 'thickness', 0.0)) for a in areas]
        disp = self._common_or_mixed(ths)
        if disp == "[KARIŞIK]":
            g.add_field("thickness", "[KARIŞIK]",
                        field_name="_bulk.thickness",
                        editable=True, kind="float")
        else:
            g.add_field("thickness", ths[0],
                        field_name="_bulk.thickness",
                        editable=True, kind="float")
        self._add_group(g)

    def _build_bulk_link_fields(self, links):
        g = CollapsibleGroup(f"Link Alanları ({len(links)} adet)")
        props = [str(getattr(l, 'propname', "")) for l in links]
        disp = self._common_or_mixed(props)
        g.add_field("propname", disp if disp != "[KARIŞIK]" else "",
                    field_name="_bulk.propname",
                    editable=True, kind="str")
        self._add_group(g)

    def _build_bulk_polygon_fields(self, polys):
        g = CollapsibleGroup(f"Polygon Alanları ({len(polys)} adet)")
        types_str = []
        for p in polys:
            t = getattr(p, 'poly_type', None)
            types_str.append(t.name if hasattr(t, 'name') else str(t))
        disp = self._common_or_mixed(types_str)
        g.add_field("poly_type", disp if disp != "[KARIŞIK]" else "",
                    choices=[e.name for e in PolygonType],
                    field_name="_bulk.poly_type",
                    editable=True, kind="enum")
        self._add_group(g)

    def _common_or_mixed(self, values):
        if not values:
            return "[BOŞ]"
        first = values[0]
        try:
            same = all(v == first for v in values[1:])
        except Exception:
            same = False
        if same:
            return first
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

        changes = {}
        for group in self._groups:
            for row in group.fields:
                fname = getattr(row, '_field_name', None)
                if not fname or not fname.startswith("_bulk."):
                    continue
                try:
                    val = row.get_value()
                except ValueError as e:
                    self._flash(str(e), ok=False)
                    return
                # "KARIŞIK" işareti varsa atla
                if isinstance(val, str) and val in ("[KARIŞIK]", "[BOŞ]", ""):
                    continue
                field = fname[len("_bulk."):]
                changes[field] = val

        if not changes:
            self._flash("Değişiklik yok", ok=False)
            return

        result = self.controller.bulk_update(elements, changes)
        if result is None or (hasattr(result, 'ok') and not result.ok):
            msg = getattr(result, 'message', 'Bulk update başarısız')
            self._flash(msg, ok=False)
            return
        self._flash(f"{len(elements)} eleman güncellendi", ok=True)
        self._rebuild_selection_ui()

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
            kind = CollapsibleGroup._infer_kind(v)
            g.add_field(k, v, field_name=k, editable=True, kind=kind)
        self._add_group(g)
        self.show()

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
        return False if self._hidden else super().on_touch_down(touch)

    def on_touch_move(self, touch):
        return False if self._hidden else super().on_touch_move(touch)

    def on_touch_up(self, touch):
        return False if self._hidden else super().on_touch_up(touch)