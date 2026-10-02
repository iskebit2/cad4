#ui/prop_panel.py

import logging
logger = logging.getLogger(__name__)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import BooleanProperty, StringProperty


class GroupHeader(ButtonBehavior, Label):
    """Tıklanabilir grup başlığı."""
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


class CollapsibleGroup(BoxLayout):
    """
    Açılır/kapanır grup.
    
    Başlık tıklanır → içerik gösterilir/gizlenir.
    """
    
    def __init__(self, title, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('spacing', 0)
        super().__init__(**kwargs)
        
        self._title_text = title
        self._expanded = True
        
        # --- Başlık (tıklanabilir) ---
        self.header = GroupHeader(text=self._make_header_text())
        self.header.bind(on_release=self._on_header_click)
        self.add_widget(self.header)
        
        # --- İçerik (GridLayout cols=2) ---
        self.content = GridLayout(
            cols=2,
            size_hint_y=None,
            spacing=dp(2),
            padding=(dp(12), dp(4), dp(4), dp(4)),
        )
        self.content.bind(minimum_height=self.content.setter('height'))
        self.add_widget(self.content)
        
        # Yüksekliği hesapla
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
    
    def add_field(self, key, value):
        """Gruba label-value satırı ekle."""
        lbl = Label(
            text=str(key),
            size_hint_y=None,
            height=dp(22),
            halign='left',
            valign='middle',
            font_size=dp(11),
            font_name="DejaVuSans.ttf",
            color=(0.85, 0.85, 0.85, 1.0),
        )
        lbl.bind(size=lbl.setter('text_size'))
        
        val = TextInput(
            text=str(value),
            size_hint_y=None,
            height=dp(22),
            multiline=False,
            readonly=True,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
            padding=(dp(4), dp(2), dp(4), dp(2)),
        )
        
        self.content.add_widget(lbl)
        self.content.add_widget(val)

class PropertiesPanel(BoxLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('width', dp(300))
        kwargs.setdefault('height', dp(500))
        kwargs.setdefault('padding', dp(6))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)
        
        # Koyu arka plan
        with self.canvas.before:
            Color(0.13, 0.15, 0.20, 0.95)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        self._current_element = None
        self._groups = []
        
        self._build_ui()
        self.hide()
    
    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def _build_ui(self):
        # --- Başlık satırı ---
        title_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(30),
        )
        
        self.title_label = Label(
            text="Özellikler",
            bold=True,
            font_size=dp(14),
            font_name="DejaVuSans.ttf",
            halign='left',
            valign='middle',
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        
        close_btn = Button(
            text="✕",
            size_hint_x=None,
            width=dp(30),
            font_size=dp(14),
            font_name="DejaVuSans.ttf",
            background_color=(0.6, 0.2, 0.2, 1.0),
            background_normal='',
        )
        close_btn.bind(on_release=lambda *_: self.hide())
        
        title_row.add_widget(self.title_label)
        title_row.add_widget(close_btn)
        self.add_widget(title_row)
        
        # --- Ayırıcı ---
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.4, 0.4, 0.4, 0.5)
            self.sep_rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda *_: setattr(self.sep_rect, 'pos', sep.pos),
                 size=lambda *_: setattr(self.sep_rect, 'size', sep.size))
        self.add_widget(sep)
        
        # --- Scrollable içerik ---
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        
        self.content_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(2),
        )
        self.content_box.bind(minimum_height=self.content_box.setter('height'))
        
        scroll.add_widget(self.content_box)
        self.add_widget(scroll)

    def _build_element_content(self, element):
        self.content_box.clear_widgets()
        self._groups.clear()
        
        et = getattr(element, 'element_type', '?').lower()
        
        # ---- Genel ----
        g = CollapsibleGroup("Genel")
        g.add_field("Tip", element.element_type)
        g.add_field("Label", getattr(element, 'label', '-'))
        g.add_field("ID", element.unique_id)
        self._add_group(g)
        
        # ---- Tip bazlı ----
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
        """Grubu panel'e ekle ve listeye kaydet."""
        self.content_box.add_widget(group)
        self._groups.append(group)

    def _build_frame_content(self, frame):
        # ---- Geometri ----
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", frame.node_i.label)
        g.add_field("Node J", frame.node_j.label)
        g.add_field("Uzunluk", f"{frame.get_length():.2f} mm")
        g.add_field("Rotation", f"{frame.rotation_deg:.1f}°")
        self._add_group(g)
        
        # ---- Kesit ----
        if frame.section:
            sec = frame.section
            g = CollapsibleGroup(f"Kesit: {sec.name}")
            g.add_field("Ad", sec.name)
            g.add_field("Tip", str(sec.profile_type))
            
            # Profil parametreleri
            if sec.profile_params:
                important = ['h', 'b', 'tw', 'tf', 't', 'ro', 'ri', 'n']
                for key in important:
                    if key in sec.profile_params:
                        g.add_field(key, self._fmt(sec.profile_params[key]))
                
                # Analiz parametreleri
                for key in ['Area', 'J', 'I33', 'I22']:
                    if key in sec.profile_params:
                        g.add_field(key, self._fmt(sec.profile_params[key]))
            
            # Varsayılan kapalı (uzun grup)
            self._add_group(g)
            g.toggle()   # ← kapat
        
        # ---- Materyal ----
        if frame.section and frame.section.material:
            mat = frame.section.material
            g = CollapsibleGroup(f"Materyal: {mat.name}")
            g.add_field("Ad", mat.name)
            g.add_field("Tip", mat.mat_type.name)
            g.add_field("E1", self._fmt(mat.E1))
            g.add_field("E2", self._fmt(mat.E2))
            g.add_field("G12", self._fmt(mat.G12))
            g.add_field("ν12", f"{mat.nu12:.3f}")
            g.add_field("Yoğunluk", f"{mat.density:.2f}")
            self._add_group(g)
            g.toggle()   # kapat
        
        # ---- Release ----
        if getattr(frame, 'release_i', None) or getattr(frame, 'release_j', None):
            g = CollapsibleGroup("Release")
            for end, rel in [("I", frame.release_i), ("J", frame.release_j)]:
                if rel:
                    active = [k for k, v in rel.items() if v]
                    if active:
                        g.add_field(f"Uç {end}", ", ".join(active))
            self._add_group(g)

    def _fmt(self, val):
        """Sayı formatla."""
        if isinstance(val, (int, float)):
            if val == 0:
                return "0"
            if abs(val) > 1e6 or abs(val) < 1e-3:
                return f"{val:.3e}"
            return f"{val:.4f}" if isinstance(val, float) else str(val)
        return str(val)

    def _build_node_content(self, node):
        g = CollapsibleGroup("Konum")
        g.add_field("X", f"{node.x:.3f}")
        g.add_field("Y", f"{node.y:.3f}")
        g.add_field("Z", f"{node.z:.3f}")
        self._add_group(g)
        
        g = CollapsibleGroup("Restraint")
        if node.restraint:
            fixed = [n for n in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')
                    if getattr(node.restraint, n, False)]
            if fixed:
                for name in fixed:
                    g.add_field(name.upper(), "Sabit")
            else:
                g.add_field("-", "Serbest")
        else:
            g.add_field("-", "Serbest")
        self._add_group(g)
        
        # Bağlı elemanlar
        if hasattr(node, 'connected') and node.connected:
            g = CollapsibleGroup(f"Bağlı Elemanlar ({len(node.connected)})")
            for obj_type, elem_id in node.connected[:10]:
                g.add_field(obj_type.name, elem_id[:8])
            if len(node.connected) > 10:
                g.add_field("...", f"+{len(node.connected) - 10} daha")
            self._add_group(g)
            g.toggle()


    def _build_link_content(self, link):
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", link.node_i.label)
        g.add_field("Node J", link.node_j.label)
        self._add_group(g)
        
        g = CollapsibleGroup("Property")
        g.add_field("Prop", getattr(link, 'propname', '-'))
        self._add_group(g)


    def _build_area_content(self, area):
        g = CollapsibleGroup("Geometri")
        g.add_field("Kalınlık", f"{area.thickness:.2f} mm")
        g.add_field("Köşe sayısı", len(area.nodes))
        self._add_group(g)
        
        g = CollapsibleGroup("Köşeler")
        for i, n in enumerate(area.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label}  ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})")
        self._add_group(g)


    def _build_polygon_content(self, polygon):
        g = CollapsibleGroup("Geometri")
        g.add_field("Köşe sayısı", len(polygon.nodes))
        self._add_group(g)
        
        g = CollapsibleGroup("Köşeler")
        for i, n in enumerate(polygon.nodes):
            g.add_field(f"Köşe {i+1}", n.label)
        self._add_group(g)
        
    def show_element(self, element):
        if element is None:
            return
        
        self._current_element = element
        self.title_label.text = f"{element.element_type}: {getattr(element, 'label', '?')}"
        
        self._build_element_content(element)
        self.show()


    def show_selection_summary(self, elements):
        """Çoklu seçim özeti."""
        self._current_element = None
        self.title_label.text = f"{len(elements)} eleman seçili"
        
        # İçeriği temizle
        self.content_box.clear_widgets()
        self._groups.clear()
        
        # ---- Özet grubu ----
        g = CollapsibleGroup("Özet")
        g.add_field("Toplam", len(elements))
        
        # Tip dağılımı
        from collections import Counter
        types = Counter(getattr(e, 'element_type', '?') for e in elements)
        for et, count in types.items():
            g.add_field(et, count)
        
        self._add_group(g)
        
        self.show()


    def hide(self):
        self.opacity = 0
        self.disabled = True
        self._current_element = None
        
    def _add_field_row(self, key, value):
        lbl = Label(
            text=str(key),
            size_hint_y=None,
            height=dp(24),
            halign='left',
            valign='middle',
            font_size=dp(12),
            font_name="DejaVuSans.ttf",
        )
        lbl.bind(size=lbl.setter('text_size'))
        
        val = TextInput(
            text=str(value),
            size_hint_y=None,
            height=dp(24),
            multiline=False,
            readonly=True,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
        )
        
        self.content.add_widget(lbl)
        self.content.add_widget(val)

    def show(self):
        """Panel'i görünür yap (içerik değişmez)."""
        self.opacity = 1
        self.disabled = False

    def hide(self):
        """Paneli gizle."""
        self.opacity = 0
        self.disabled = True
        self._current_element = None
    
    def _get_fields(self, element):
        """Element tipine göre (label, value) çiftleri üret."""
        et = getattr(element, 'element_type', '?').lower()
        fields = []
        
        # Ortak alanlar
        fields.append(("Tip", element.element_type))
        fields.append(("Label", getattr(element, 'label', '-')))
        fields.append(("ID", element.unique_id))
        
        if et == 'node':
            fields += [
                ("X", f"{element.x:.2f}"),
                ("Y", f"{element.y:.2f}"),
                ("Z", f"{element.z:.2f}"),
            ]
            if element.restraint:
                r = element.restraint
                restraints = [
                    n for n in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')
                    if getattr(r, n, False)
                ]
                fields.append(("Restraint", ",".join(restraints) if restraints else "Yok"))
            else:
                fields.append(("Restraint", "Yok"))
        
        elif et == 'frame':
            fields += [
                ("Section", element.section.name if element.section else "-"),
                ("Node I", element.node_i.label),
                ("Node J", element.node_j.label),
                ("Uzunluk", f"{element.get_length():.2f} mm"),
                ("Rotation", f"{element.rotation_deg:.1f}°"),
            ]
        
        elif et == 'link':
            fields += [
                ("Node I", element.node_i.label),
                ("Node J", element.node_j.label),
                ("Prop", getattr(element, 'propname', '-')),
            ]
        
        elif et == 'area':
            fields += [
                ("Kalınlık", f"{element.thickness:.2f} mm"),
                ("Köşe sayısı", len(element.nodes)),
            ]
            for i, n in enumerate(element.nodes):
                fields.append((f"Köşe {i+1}", n.label))
        
        elif et == 'polygon':
            fields.append(("Köşe sayısı", len(element.nodes)))
            for i, n in enumerate(element.nodes):
                fields.append((f"Köşe {i+1}", n.label))
        
        return fields

    