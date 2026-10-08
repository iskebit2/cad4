# ui/prop_panel.py
import numpy as np
from logging_config import CadLogger
logger = CadLogger.get(__name__)

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock

from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import BooleanProperty, StringProperty


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
    """
    Açılır/kapanır grup.
    Her alan TextInput olarak eklenir; düzenlenebilir olabilir.
    """

    def __init__(self, title, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('spacing', 0)
        super().__init__(**kwargs)

        self._title_text = title
        self._expanded = True
        self.fields = []        # <-- YENİ: TextInput'ları topla

        # Başlık
        self.header = GroupHeader(text=self._make_header_text())
        self.header.bind(on_release=self._on_header_click)
        self.add_widget(self.header)

        # İçerik
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
        """
        Gruba label-value satırı ekle.

        Parameters
        ----------
        key : str          — gösterilecek etiket
        value : any        — başlangıç değeri
        field_name : str   — Apply'da hangi alan (nokta yolu destekler)
        element : Element  — Apply'da hangi eleman (yeni eleman için None)
        editable : bool    — TextInput düzenlenebilir mi
        kind : str         — "str" | "float" | "int" | "bool"
        """
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
            readonly=not editable,
            font_size=dp(11),
            background_color=(0.10, 0.12, 0.16, 1.0) if not editable
                             else (0.15, 0.18, 0.24, 1.0),
            foreground_color=(0.9, 0.9, 0.9, 1.0),
            padding=(dp(4), dp(2), dp(4), dp(2)),
        )

        # Apply için metadata
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
        kwargs.setdefault('width', dp(300))
        kwargs.setdefault('height', dp(500))
        kwargs.setdefault('padding', dp(6))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)

        # --- Controller (EditController) ---
        self.controller = controller

        # --- State ---
        self._current_element = None
        self._pending_new_type = None      # YENİ: "node" | "frame" | ...
        self._pending_new_repeat = False

        self._groups = []
        self._hidden = True

        # Koyu arka plan
        with self.canvas.before:
            Color(0.13, 0.15, 0.20, 0.95)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()
        self.hide()

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    # ========================================================
    # UI İNŞASI
    # ========================================================

    def _build_ui(self):
        # --- Başlık ---
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

        # --- YENİ: Apply / Cancel bar ---
        btn_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(36),
            spacing=dp(4),
        )

        self.cancel_btn = Button(
            text="Cancel",
            background_normal='',
            background_color=(0.45, 0.20, 0.20, 1.0),
            font_size=dp(12),
            font_name="DejaVuSans.ttf",
        )
        self.cancel_btn.bind(on_release=self._on_cancel)

        self.apply_btn = Button(
            text="Apply",
            background_normal='',
            background_color=(0.20, 0.55, 0.30, 1.0),
            font_size=dp(12),
            font_name="DejaVuSans.ttf",
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
        if self.controller is None:
            logger.warning("controller yok, Apply çalışmaz")
            self._flash("Controller yok", ok=False)
            return

        values = self._collect_field_values()

        # --- YENİ ELEMAN ---
        if self._pending_new_type is not None:
            result = self.controller.create(self._pending_new_type, values)
            if not result.ok:
                self._flash(result.message, ok=False)
                return

            self._flash(result.message, ok=True)

            if self._pending_new_repeat:
                # Çoklu ekleme: formu koru, sadece değerleri resetle
                # (label boş bırak, konumları sıfırla vs.)
                self._reset_form_after_create()
                # _pending_new_type DOKUNULMAZ → sonraki Apply da create olur
            else:
                # Tek seferlik: mevcut elemanı düzenlemeye geç
                self._current_element = result.element
                self._pending_new_type = None
                self.title_label.text = (
                    f"{getattr(result.element, 'element_type', '?')}: "
                    f"{getattr(result.element, 'label', '?')}"
                )
            return

        # --- GÜNCELLE ---
        if self._current_element is not None:
            result = self.controller.update(self._current_element, values)
            self._flash(result.message, ok=result.ok)
            return

        self._flash("Düzenlenecek eleman yok", ok=False)

    def _on_cancel(self, *_):
        # Yeni eleman modundaysa kapat
        if self._pending_new_type is not None:
            self._pending_new_type = None
            self._pending_new_repeat = False
            self.hide()
            return

        # Mevcut elemanı yeniden oku
        if self._current_element is not None:
            self._build_element_content(self._current_element)
            self._flash("İptal edildi", ok=True)
        else:
            self.hide()

    def _reset_form_after_create(self):
        """
        Çoklu ekleme modunda formu sıfırla — label'ı temizle,
        sayısal alanları 0 yap. İsteğe göre özelleştirilebilir.
        """
        for group in self._groups:
            for ti in group.fields:
                if ti._field_name is None:
                    continue
                fname = ti._field_name
                kind = ti._kind

                # label boş kalsın, diğerleri default
                if fname == "label":
                    ti.text = ""
                elif kind == "float":
                    ti.text = "0.0"
                elif kind == "int":
                    ti.text = "0"
                elif kind == "bool":
                    ti.text = "Serbest"
                else:
                    ti.text = ""

        # Başlığı güncelle
        self.title_label.text = f"YENİ: {self._pending_new_type} (çoklu)"

    def _collect_field_values(self):
        """Tüm gruplardaki TextInput değerlerini {field_name: value} yap."""
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
                logger.warning(f"Geçersiz float: {text!r}")
                return 0.0
        if kind == "int":
            try:
                return int(float(text))
            except ValueError:
                return 0
        if kind == "bool":
            return text.lower() in ("1", "true", "evet", "yes", "sabit")
        return text

    def _flash(self, msg, ok=True):
        """Başlığı geçici olarak mesajla değiştir."""
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
    # ELEMAN İÇERİĞİ
    # ========================================================

    def _build_element_content(self, element):
        self.content_box.clear_widgets()
        self._groups.clear()

        et = getattr(element, 'element_type', '?').lower()

        # ---- Genel (readonly) ----
        g = CollapsibleGroup("Genel")
        g.add_field("Tip", element.element_type)
        g.add_field("Label", getattr(element, 'label', '-'),
                    field_name="label", element=element,
                    editable=True, kind="str")
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
        self.content_box.add_widget(group)
        self._groups.append(group)

    # --------------------------------------------------------
    # NODE
    # --------------------------------------------------------

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
                g.add_field(
                    name.upper(),
                    "Sabit" if current else "Serbest",
                    field_name=f"restraint.{name}",
                    element=node,
                    editable=True,
                    kind="bool",
                )
        else:
            g.add_field("-", "Serbest")
        self._add_group(g)

        # Bağlı elemanlar (readonly)
        if hasattr(node, 'connected') and node.connected:
            g = CollapsibleGroup(f"Bağlı Elemanlar ({len(node.connected)})")
            for obj_type, elem_id in node.connected[:10]:
                g.add_field(obj_type.name, str(elem_id)[:8])
            if len(node.connected) > 10:
                g.add_field("...", f"+{len(node.connected) - 10} daha")
            self._add_group(g)
            g.toggle()

    # --------------------------------------------------------
    # FRAME
    # --------------------------------------------------------

    def _build_frame_content(self, frame):
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", frame.node_i.label,
                    field_name="node_i_id", element=frame,
                    editable=True, kind="str")
        g.add_field("Node J", frame.node_j.label,
                    field_name="node_j_id", element=frame,
                    editable=True, kind="str")
        g.add_field("Uzunluk", f"{frame.get_length():.2f} mm")
        g.add_field("Rotation", f"{frame.rotation_deg:.1f}°")
        self._add_group(g)

        if frame.section:
            sec = frame.section
            g = CollapsibleGroup(f"Kesit: {sec.name}")
            g.add_field("Ad", sec.name, field_name="section_name",
                        element=frame, editable=True, kind="str")
            g.add_field("Tip", str(sec.profile_type))

            if sec.profile_params:
                important = ['h', 'b', 'tw', 'tf', 't', 'ro', 'ri', 'n']
                for key in important:
                    if key in sec.profile_params:
                        g.add_field(
                            key,
                            self._fmt(sec.profile_params[key]),
                            field_name=f"section.profile_params.{key}",
                            element=frame, editable=True, kind="float",
                        )
                for key in ['Area', 'J', 'I33', 'I22']:
                    if key in sec.profile_params:
                        g.add_field(
                            key,
                            self._fmt(sec.profile_params[key]),
                            field_name=f"section.profile_params.{key}",
                            element=frame, editable=True, kind="float",
                        )
            self._add_group(g)
            g.toggle()

        if frame.section and frame.section.material:
            mat = frame.section.material
            g = CollapsibleGroup(f"Materyal: {mat.name}")
            g.add_field("Ad", mat.name)
            g.add_field("Tip", mat.mat_type.name)
            g.add_field("E1", self._fmt(mat.E1),
                        field_name="section.material.E1",
                        element=frame, editable=True, kind="float")
            g.add_field("E2", self._fmt(mat.E2),
                        field_name="section.material.E2",
                        element=frame, editable=True, kind="float")
            g.add_field("G12", self._fmt(mat.G12),
                        field_name="section.material.G12",
                        element=frame, editable=True, kind="float")
            g.add_field("ν12", f"{mat.nu12:.3f}",
                        field_name="section.material.nu12",
                        element=frame, editable=True, kind="float")
            g.add_field("Yoğunluk", f"{mat.density:.2f}",
                        field_name="section.material.density",
                        element=frame, editable=True, kind="float")
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

    # --------------------------------------------------------
    # LINK
    # --------------------------------------------------------

    def _build_link_content(self, link):
        g = CollapsibleGroup("Geometri")
        g.add_field("Node I", link.node_i.label,
                    field_name="node_i_id", element=link,
                    editable=True, kind="str")
        g.add_field("Node J", link.node_j.label,
                    field_name="node_j_id", element=link,
                    editable=True, kind="str")
        self._add_group(g)

        g = CollapsibleGroup("Property")
        g.add_field("Prop", getattr(link, 'propname', '-'),
                    field_name="propname", element=link,
                    editable=True, kind="str")
        self._add_group(g)

    # --------------------------------------------------------
    # AREA
    # --------------------------------------------------------

    def _build_area_content(self, area):
        g = CollapsibleGroup("Geometri")
        g.add_field("Kalınlık", f"{area.thickness:.2f} mm",
                    field_name="thickness", element=area,
                    editable=True, kind="float")
        g.add_field("Köşe sayısı", len(area.nodes))
        self._add_group(g)

        g = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(area.nodes):
            g.add_field(f"Köşe {i+1}",
                        f"{n.label}  ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})")
        self._add_group(g)

    # --------------------------------------------------------
    # POLYGON
    # --------------------------------------------------------

    def _build_polygon_content(self, polygon):
        # 1. Genel / Tip Grubu
        g_gen = CollapsibleGroup("Poligon Bilgileri")
        
        # Poligon Tipini Göster ve Düzenlenebilir Yap
        current_type_name = polygon.poly_type.name if hasattr(polygon.poly_type, 'name') else str(polygon.poly_type)
        g_gen.add_field(
            "Poligon Tipi",
            current_type_name,
            field_name="poly_type",
            element=polygon,
            editable=True,
            kind="str"  # GENERIC, SURFACE, ZONE, SECTION_CUT, LOAD_AREA
        )
        
        g_gen.add_field("Köşe sayısı", len(polygon.nodes))
        self._add_group(g_gen)

        # 2. Rüzgar Alanı (windplane) Verileri Varsa Ekle
        if getattr(polygon, "windplane", None):
            wp = polygon.windplane
            g_wind = CollapsibleGroup("Rüzgar Bölgesi (TS EN 1991-1-4)")
            
            g_wind.add_field("Zone Etiketi", wp.get("label", "-"))
            g_wind.add_field("Yüzey", wp.get("surface", "-"))
            g_wind.add_field("Tablo Tipi", wp.get("table_type", "-"))
            
            def format_cpe(val):
                if val is None:
                    return "-"
                if isinstance(val, (tuple, list, np.ndarray)):
                    formatted = [f"{v:.3f}" if isinstance(v, (int, float)) else str(v) for v in val]
                    return f"[{', '.join(formatted)}]"
                if isinstance(val, (int, float)):
                    return f"{val:.3f}"
                return str(val)

            if "cpe10" in wp and wp["cpe10"] is not None:
                g_wind.add_field("Cpe,10", format_cpe(wp["cpe10"]))
            if "cpe1" in wp and wp["cpe1"] is not None:
                g_wind.add_field("Cpe,1", format_cpe(wp["cpe1"]))
            if "pitch" in wp:
                g_wind.add_field("Eğim (°)", f"{wp['pitch']:.1f}")
                
            self._add_group(g_wind)

        # 3. Köşe Listesi
        g_nodes = CollapsibleGroup("Köşeler (salt okunur)")
        for i, n in enumerate(polygon.nodes):
            g_nodes.add_field(f"Köşe {i+1}", f"{n.label} ({n.x:.1f}, {n.y:.1f}, {n.z:.1f})")
        self._add_group(g_nodes)
        g_nodes.toggle()  # Başlangıçta kapalı tut

    # ========================================================
    # SHOW / HIDE
    # ========================================================

    def show_element(self, element):
        if element is None:
            return
        self._current_element = element
        self._pending_new_type = None
        self.title_label.text = (
            f"{element.element_type}: {getattr(element, 'label', '?')}"
        )
        self._build_element_content(element)
        self.show()

    def show_new_element(self, element_type, defaults=None, repeat=False):
        """
        Boş bir form açar.
        repeat=True → Apply'dan sonra form açık kalır, sonraki Apply
                    yine create çağırır (ardışık ekleme).
        """
        self._current_element = None
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
        if isinstance(v, bool):  return "bool"
        if isinstance(v, int):   return "int"
        if isinstance(v, float): return "float"
        return "str"

    def show_selection_summary(self, elements):
        self._current_element = None
        self._pending_new_type = None
        self.title_label.text = f"{len(elements)} eleman seçili"

        self.content_box.clear_widgets()
        self._groups.clear()

        g = CollapsibleGroup("Özet")
        g.add_field("Toplam", len(elements))

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
        self._pending_new_type = None
        self._pending_new_repeat = False
        self._hidden = True

    def show(self):
        self.opacity = 1.0            # <-- 0.5 DEĞİL
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