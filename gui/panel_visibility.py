# gui/panel_visibility.py
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock

from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT
from domain.element import PolygonType

from debug_lines import debug_layout

class VisibilityPanelContent(BoxLayout):
    def __init__(self, scene, on_visibility_changed=None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(8), **kwargs)
        self.scene = scene
        self.on_visibility_changed = on_visibility_changed
        self._search_trigger = None

        # ==========================================
        # 1. ELEMAN VE POLİGON TİPİ BAZLI KONTROLLER
        # ==========================================
        group_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4))
        
        lbl_group = Label(
            text="[b]Grup ve Poligon Tipi Görünürlüğü[/b]",
            markup=True,
            font_size=dp(12),
            font_name=FONT_DEFAULT,
            size_hint_y=None,
            height=dp(22),
            color=(0.8, 0.85, 0.9, 1)
        )
        group_box.add_widget(lbl_group)

        # 3 sütunlu grid
        grid_groups = GridLayout(cols=3, spacing=dp(6), size_hint_y=None, height=dp(115))
        
        self.group_buttons = {}

        # Temel Eleman Tipleri
        base_types = [
            ("Node", "nodes"),
            ("Frame", "frames"),
            ("Area", "areas"),
            ("Link", "links"),
        ]

        for type_label, attr_name in base_types:
            elements = getattr(self.scene, attr_name, {}).values()
            all_visible = all(e.is_visible for e in elements) if elements else True
            
            btn = ToggleButton(
                text=f"{'✓' if all_visible else '✗'} {type_label}s",
                state="down" if all_visible else "normal",
                font_name=FONT_DEFAULT,
                font_size=dp(11),
                background_normal="",
                background_color=(0.20, 0.60, 0.35, 1) if all_visible else (0.35, 0.20, 0.20, 1)
            )
            btn.bind(on_release=lambda instance, attr=attr_name: self._toggle_group_visibility(instance, attr))
            self.group_buttons[attr_name] = btn
            grid_groups.add_widget(btn)

        # PolygonType Enum Bazlı Özel Butonlar
        poly_types = [
            ("Poly: Surface", PolygonType.SURFACE),
            ("Poly: Zone", PolygonType.ZONE),
            ("Poly: SecCut", PolygonType.SECTION_CUT),
            ("Poly: LoadArea", PolygonType.LOAD_AREA),
            ("Poly: Generic", PolygonType.GENERIC),
        ]

        for label_text, p_type in poly_types:
            matching_polys = [p for p in self.scene.polygons.values() if getattr(p, "poly_type", None) == p_type]
            all_visible = all(p.is_visible for p in matching_polys) if matching_polys else True

            btn = ToggleButton(
                text=f"{'✓' if all_visible else '✗'} {label_text}",
                state="down" if all_visible else "normal",
                font_name=FONT_DEFAULT,
                font_size=dp(11),
                background_normal="",
                background_color=(0.20, 0.60, 0.35, 1) if all_visible else (0.35, 0.20, 0.20, 1)
            )
            btn.bind(on_release=lambda instance, pt=p_type: self._toggle_poly_type_visibility(instance, pt))
            self.group_buttons[f"poly_{p_type.name}"] = btn
            grid_groups.add_widget(btn)

        # Tümünü Aç / Kapat
        btn_all = Button(
            text="Tümünü Aç/Kapat",
            font_name=FONT_DEFAULT,
            font_size=dp(11),
            background_color=(0.3, 0.4, 0.5, 1)
        )
        btn_all.bind(on_release=self._toggle_all)
        grid_groups.add_widget(btn_all)

        group_box.add_widget(grid_groups)
        self.add_widget(group_box)

        # ==========================================
        # 2. ARAMA VE FİLTRELEME
        # ==========================================
        search_box = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
        self.search_input = TextInput(
            hint_text="Label, ID veya Tip ile ara (örn: ZONE)...",
            font_name=FONT_DEFAULT,
            multiline=False,
            size_hint_x=1
        )
        self.search_input.bind(text=self._on_search_text_changed)
        search_box.add_widget(self.search_input)
        self.add_widget(search_box)

        # ==========================================
        # 3. ELEMAN BAZLI LİSTE (OPTIMIZED SCROLL)
        # ==========================================
        scroll = ScrollView(size_hint=(1, 1))
        self.list_layout = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        
        scroll.add_widget(self.list_layout)
        self.add_widget(scroll)

        # İlk dolum
        Clock.schedule_once(lambda dt: self._populate_element_list(), 0.05)

        debug_layout(self)

    def _update_btn_style(self, btn):
        if btn.state == "down":
            btn.background_color = (0.20, 0.60, 0.35, 1)
            btn.text = btn.text.replace("✗", "✓")
        else:
            btn.background_color = (0.35, 0.20, 0.20, 1)
            btn.text = btn.text.replace("✓", "✗")

    def _toggle_group_visibility(self, btn, attr_name):
        is_visible = (btn.state == "down")
        self._update_btn_style(btn)

        elements = getattr(self.scene, attr_name, {})
        for elem in elements.values():
            elem.is_visible = is_visible

        self._populate_element_list(self.search_input.text)
        self._notify_change()

    def _toggle_poly_type_visibility(self, btn, poly_type):
        is_visible = (btn.state == "down")
        self._update_btn_style(btn)

        for poly in self.scene.polygons.values():
            if getattr(poly, "poly_type", None) == poly_type:
                poly.is_visible = is_visible

        self._populate_element_list(self.search_input.text)
        self._notify_change()

    def _toggle_all(self, *_):
        all_elements = list(self.scene.all_elements.values())
        new_state = not all(e.is_visible for e in all_elements)

        for elem in all_elements:
            elem.is_visible = new_state

        for btn in self.group_buttons.values():
            btn.state = "down" if new_state else "normal"
            self._update_btn_style(btn)

        self._populate_element_list(self.search_input.text)
        self._notify_change()

    def _on_search_text_changed(self, instance, value):
        if self._search_trigger:
            self._search_trigger.cancel()
        self._search_trigger = Clock.schedule_once(
            lambda dt: self._populate_element_list(value), 0.2
        )

    def _populate_element_list(self, filter_text=""):
        self.list_layout.clear_widgets()
        filter_text = filter_text.lower().strip()

        count = 0
        MAX_DISPLAY = 100

        for elem in self.scene.all_elements.values():
            # Tip metni (Polygon ise PolygonType adını da ekle)
            if elem.element_type == "Polygon" and hasattr(elem, "poly_type"):
                type_str = f"Polygon:{elem.poly_type.name}"
            else:
                type_str = elem.element_type

            disp_name = f"[{type_str}] ID:{elem.unique_id} - {elem.label}"
            
            if filter_text and filter_text not in disp_name.lower():
                continue

            item_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
            
            lbl = Label(
                text=disp_name,
                font_name=FONT_DEFAULT,
                font_size=dp(11),
                halign="left",
                valign="middle",
                color=(0.85, 0.88, 0.92, 1)
            )
            lbl.bind(size=lbl.setter("text_size"))
            item_row.add_widget(lbl)

            btn_toggle = ToggleButton(
                text="✓" if elem.is_visible else "✗",
                state="down" if elem.is_visible else "normal",
                size_hint_x=None,
                width=dp(36),
                font_name=FONT_DEFAULT,
                background_color=(0.2, 0.6, 0.3, 1) if elem.is_visible else (0.5, 0.2, 0.2, 1)
            )
            
            def make_callback(e, b):
                def cb(*_):
                    e.is_visible = (b.state == "down")
                    b.text = "✓" if e.is_visible else "✗"
                    b.background_color = (0.2, 0.6, 0.3, 1) if e.is_visible else (0.5, 0.2, 0.2, 1)
                    self._notify_change()
                return cb

            btn_toggle.bind(on_release=make_callback(elem, btn_toggle))
            item_row.add_widget(btn_toggle)

            self.list_layout.add_widget(item_row)
            
            count += 1
            if count >= MAX_DISPLAY:
                info_lbl = Label(
                    text=f"...ve {len(self.scene.all_elements) - MAX_DISPLAY} eleman daha var.",
                    font_name=FONT_DEFAULT,
                    font_size=dp(10),
                    color=(0.6, 0.6, 0.6, 1),
                    size_hint_y=None,
                    height=dp(24)
                )
                self.list_layout.add_widget(info_lbl)
                break

    def _notify_change(self):
        if self.on_visibility_changed:
            self.on_visibility_changed()


class VisibilityPanel(BaseCustomPopup):
    def __init__(self, scene, on_visibility_changed=None, **kwargs):
        content = VisibilityPanelContent(scene=scene, on_visibility_changed=on_visibility_changed)
        super().__init__(
            title_text="GÖRÜNÜRLÜK VE ELEMAN FİLTRESİ",
            content_widget=content,
            size_hint=(0.80, 0.85),
            **kwargs
        )