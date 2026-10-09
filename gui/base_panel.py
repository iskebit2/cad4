# gui/base_panel.py
"""
BasePanel — Tüm panellerin ortak atası.
PropertiesPanel'in "sorunsuz" çalışma özelliklerini standart hale getirir:

1. Widget tabanlı (Popup/ModalView değil)
2. Kendi arka planını canvas.before ile çizer (alfa ~0.95)
3. opacity + disabled ile hide/show (widget ağacından çıkarmaz)
4. on_touch_* override: gizliyken event yutma
5. Sabit boyut (size_hint = (None, None))

Kullanım:

    class MyPanel(BasePanel):
        def __init__(self, **kwargs):
            super().__init__(
                title="My Panel",
                width=dp(360), height=dp(500),
                **kwargs
            )
            # kendi içeriğini self.body'e ekle
            self.body.add_widget(Label(text="İçerik"))
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock


class BasePanel(BoxLayout):
    """
    Ortak panel iskeleti:
      [ Başlık | Kapat ]
      -------------------
      [ scrollable body ]
      -------------------
      [ (opsiyonel) alt buton çubuğu ]

    Alt sınıflar:
      - self.body   : içerik eklemek için BoxLayout
      - self.header : başlık Label
      - self.footer : alt buton kutusu (kullanmak istersen)
    """

    def __init__(self,
                 title: str = "Panel",
                 width: int = 320,
                 height: int = 500,
                 bg_color=(0.13, 0.15, 0.20, 0.95),
                 show_close: bool = True,
                 show_footer: bool = False,
                 **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)
        kwargs.setdefault('padding', dp(6))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)

        self._hidden = True
        self._bg_color = bg_color

        # --- Arka plan (canvas.before ile) ---
        with self.canvas.before:
            Color(*bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Başlık ---
        self._title_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(30),
        )

        self.header = Label(
            text=title,
            bold=True,
            font_size=dp(14),
            font_name="DejaVuSans.ttf",
            halign='left',
            valign='middle',
        )
        self.header.bind(size=self.header.setter('text_size'))
        self._title_row.add_widget(self.header)

        if show_close:
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
            self._title_row.add_widget(close_btn)

        self.add_widget(self._title_row)

        # --- Ayırıcı ---
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.4, 0.4, 0.4, 0.5)
            self._sep_rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(
            pos=lambda *_: setattr(self._sep_rect, 'pos', sep.pos),
            size=lambda *_: setattr(self._sep_rect, 'size', sep.size),
        )
        self.add_widget(sep)

        # --- Scrollable body ---
        self._scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.body = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(2),
        )
        self.body.bind(minimum_height=self.body.setter('height'))
        self._scroll.add_widget(self.body)
        self.add_widget(self._scroll)

        # --- Footer (opsiyonel) ---
        self.footer = None
        if show_footer:
            self.footer = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(36),
                spacing=dp(4),
            )
            self.add_widget(self.footer)

        # Başlangıç: gizli
        self.hide()

    # ------------------------------------------------------------------
    # Arka plan güncelleme
    # ------------------------------------------------------------------
    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    # ------------------------------------------------------------------
    # Show / Hide
    # ------------------------------------------------------------------
    def hide(self):
        self.opacity = 0
        self.disabled = True
        self._hidden = True

    def show(self):
        self.opacity = 1.0
        self.disabled = False
        self._hidden = False

    def is_hidden(self):
        return self._hidden

    # ------------------------------------------------------------------
    # Touch yutma (gizliyken event geçirmesin)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Yardımcı: başlık metnini değiştir
    # ------------------------------------------------------------------
    def set_title(self, text: str):
        self.header.text = text

    # ------------------------------------------------------------------
    # Yardımcı: geçici mesaj (başlıkta)
    # ------------------------------------------------------------------
    def flash(self, msg: str, ok: bool = True, duration: float = 1.5):
        color = (0.4, 0.9, 0.5, 1) if ok else (1.0, 0.5, 0.5, 1)
        old_text = self.header.text
        old_color = self.header.color

        self.header.text = msg
        self.header.color = color

        def _restore(dt):
            self.header.text = old_text
            self.header.color = old_color

        Clock.schedule_once(_restore, duration)