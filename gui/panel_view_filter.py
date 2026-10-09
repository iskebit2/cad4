# gui/panel_view_filter.py
"""
View & Plan Filter Paneli — BasePanel üzerine kurulu.

Kullanım (KivyCADWidget içinde):

    from gui.panel_view_filter import ViewFilterPanel

    # __init__ içinde:
    self.view_panel = ViewFilterPanel(
        camera=None,   # engine hazır olunca set edilecek
        on_apply=self._on_view_filter_apply,
        pos_hint={"right": 0.98, "top": 0.98},
    )
    self.add_widget(self.view_panel)

    # Engine hazır olunca:
    self.view_panel.camera = self.engine.cam

    # Açmak için:
    self.view_panel.show()

    # Kapatmak için (BasePanel'den gelir):
    self.view_panel.hide()
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.metrics import dp

from gui.base_panel import BasePanel


class ViewFilterPanel(BasePanel):
    """
    View preset + Plan filter kontrolü.

    - Kamera'ya doğrudan yazmaz; Apply'a basılınca yazar.
    - Apply sonrası on_apply(camera) çağrılır → ana kod renderer'ı günceller.
    """

    # ------------------------------------------------------------------
    # Sabitler
    # ------------------------------------------------------------------
    VIEW_PRESETS = [
        ("Front", "front"), ("Back", "back"),
        ("Top", "top"), ("Bottom", "bottom"),
        ("Left", "left"), ("Right", "right"),
        ("Iso", "iso"),
    ]

    PLANES = [("Off", None), ("XY", "XY"), ("XZ", "XZ"), ("YZ", "YZ")]

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(self, camera=None, on_apply=None, **kwargs):
        super().__init__(
            title="View & Plan Filter",
            width=dp(340),
            height=dp(520),
            show_close=True,
            show_footer=True,
            **kwargs,
        )

        self.camera = camera
        self._on_apply_cb = on_apply

        # Yerel seçim durumu
        self._sel_preset = None
        self._sel_plane = None
        self._sel_direction = "positive"
        self._sel_offset = 0.0

        # Paneli kamera durumuna göre senkronize et
        if self.camera is not None:
            self._sync_from_camera()

        self._build_content()
        self._build_footer()

    # ------------------------------------------------------------------
    # Kamera durumundan senkron
    # ------------------------------------------------------------------
    def _sync_from_camera(self):
        if self.camera is None:
            return
        self._sel_preset = self.camera.view_preset
        self._sel_plane = self.camera.active_plane
        self._sel_direction = self.camera.plane_direction
        self._sel_offset = self.camera.plane_offset

    # ------------------------------------------------------------------
    # İçerik inşası
    # ------------------------------------------------------------------
    def _build_content(self):
        # --- VIEW PRESET ---
        self.body.add_widget(self._section_label("VIEW"))

        preset_grid = GridLayout(
            cols=4, size_hint_y=None, height=dp(80), spacing=dp(4)
        )
        self._preset_buttons = {}
        for label, key in self.VIEW_PRESETS:
            btn = ToggleButton(
                text=label,
                group="preset",
                font_size=dp(12),
            )
            if key == self._sel_preset:
                btn.state = "down"
            btn.bind(on_release=lambda inst, k=key: self._select_preset(k))
            self._preset_buttons[key] = btn
            preset_grid.add_widget(btn)

        # Boş hücre (grid 4 sütun, 7 preset → 1 boş)
        preset_grid.add_widget(Label(text=""))

        self.body.add_widget(preset_grid)

        # --- PLAN FILTER ---
        self.body.add_widget(self._section_label("PLAN"))

        plane_grid = GridLayout(
            cols=4, size_hint_y=None, height=dp(40), spacing=dp(4)
        )
        self._plane_buttons = {}
        for label, key in self.PLANES:
            btn = ToggleButton(
                text=label,
                group="plane",
                font_size=dp(12),
            )
            if key == self._sel_plane:
                btn.state = "down"
            btn.bind(on_release=lambda inst, k=key: self._select_plane(k))
            self._plane_buttons[key] = btn
            plane_grid.add_widget(btn)

        self.body.add_widget(plane_grid)

        # --- DIRECTION ---
        dir_grid = GridLayout(
            cols=2, size_hint_y=None, height=dp(40), spacing=dp(4)
        )
        self._dir_pos = ToggleButton(
            text="Positive (+)", group="dir", font_size=dp(12)
        )
        self._dir_neg = ToggleButton(
            text="Negative (-)", group="dir", font_size=dp(12)
        )
        if self._sel_direction == "positive":
            self._dir_pos.state = "down"
        else:
            self._dir_neg.state = "down"

        self._dir_pos.bind(
            on_release=lambda *_: self._select_direction("positive")
        )
        self._dir_neg.bind(
            on_release=lambda *_: self._select_direction("negative")
        )

        dir_grid.add_widget(self._dir_pos)
        dir_grid.add_widget(self._dir_neg)
        self.body.add_widget(dir_grid)

        # --- OFFSET ---
        offset_box = BoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(80)
        )
        self._offset_label = Label(
            text=f"Offset: {self._sel_offset:.2f}",
            size_hint_y=None,
            height=dp(24),
            font_size=dp(12),
        )
        self._offset_slider = Slider(
            min=-100, max=100, value=self._sel_offset, step=0.1
        )
        self._offset_slider.bind(value=self._on_offset_change)

        offset_box.add_widget(self._offset_label)
        offset_box.add_widget(self._offset_slider)
        self.body.add_widget(offset_box)

        # Plan off ise direction ve offset disabled olsun
        self._update_controls_enabled()

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    def _build_footer(self):
        from kivy.uix.button import Button

        cancel_btn = Button(
            text="Kapat",
            font_size=dp(13),
            background_normal='',
            background_color=(0.4, 0.4, 0.45, 1.0),
        )
        cancel_btn.bind(on_release=lambda *_: self.hide())

        apply_btn = Button(
            text="Uygula",
            font_size=dp(13),
            bold=True,
            background_normal='',
            background_color=(0.20, 0.55, 0.30, 1.0),
        )
        apply_btn.bind(on_release=self._do_apply)

        self.footer.add_widget(cancel_btn)
        self.footer.add_widget(apply_btn)

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    def _section_label(self, text):
        return Label(
            text=f"[b]{text}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(24),
            font_size=dp(13),
            halign='left',
            valign='middle',
        )

    def _update_controls_enabled(self):
        enabled = self._sel_plane is not None
        self._dir_pos.disabled = not enabled
        self._dir_neg.disabled = not enabled
        self._offset_slider.disabled = not enabled

    # ------------------------------------------------------------------
    # Seçim callback'leri
    # ------------------------------------------------------------------
    def _select_preset(self, key):
        # Toggle davranışı: aynı butona tekrar basınca seçim iptal
        if self._sel_preset == key:
            self._sel_preset = None
            self._preset_buttons[key].state = "normal"
        else:
            self._sel_preset = key

    def _select_plane(self, key):
        self._sel_plane = key
        self._update_controls_enabled()

    def _select_direction(self, direction):
        self._sel_direction = direction

    def _on_offset_change(self, slider, value):
        self._sel_offset = value
        self._offset_label.text = f"Offset: {value:.2f}"

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _do_apply(self, *_):
        if self.camera is None:
            self.flash("Kamera yok", ok=False)
            return

        # 1. View preset
        if self._sel_preset:
            self.camera.set_view_preset(self._sel_preset)
        else:
            self.camera.clear_view_preset()

        # 2. Plan filter
        if self._sel_plane:
            self.camera.set_plane_filter(
                self._sel_plane,
                offset=self._sel_offset,
                direction=self._sel_direction,
            )
        else:
            self.camera.clear_plane_filter()

        # 3. Ana koda haber ver
        if self._on_apply_cb:
            try:
                self._on_apply_cb(self.camera)
                self.flash("Uygulandı", ok=True)
            except Exception as e:
                import traceback
                print(f"[ViewFilterPanel] on_apply hatası: {e}")
                traceback.print_exc()
                self.flash("Hata", ok=False)
        else:
            self.flash("Uygulandı", ok=True)

    # ------------------------------------------------------------------
    # Kamera değişince yeniden senkron
    # ------------------------------------------------------------------
    def set_camera(self, camera):
        """
        Kamera hazır olduğunda çağır (engine init'ten sonra).
        Butonları kameranın mevcut durumuna göre ayarlar.
        """
        self.camera = camera
        self._sync_from_camera()

        # Buton state'lerini güncelle
        for key, btn in self._preset_buttons.items():
            btn.state = "down" if key == self._sel_preset else "normal"

        for key, btn in self._plane_buttons.items():
            btn.state = "down" if key == self._sel_plane else "normal"

        if self._sel_direction == "positive":
            self._dir_pos.state = "down"
            self._dir_neg.state = "normal"
        else:
            self._dir_pos.state = "normal"
            self._dir_neg.state = "down"

        self._offset_slider.value = self._sel_offset
        self._offset_label.text = f"Offset: {self._sel_offset:.2f}"
        self._update_controls_enabled()