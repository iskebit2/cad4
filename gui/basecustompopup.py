import os
from kivy.app import App
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle, Line

# ============================================================
# UYGULAMA GENELİ MERKEZİ TEMA BİLGİSİ
# ============================================================
THEME = {
    "bg_popup": (0.055, 0.065, 0.080, 0.96),   # Arka plan hafif şeffaf koyu
    "header_bg": (0.075, 0.085, 0.105, 1),      # Başlık çubuğu
    "border": (0.18, 0.20, 0.24, 1),            # Panel kenarlığı
    "text_title": (0.92, 0.94, 0.98, 1),        # Başlık yazısı
    "btn_close_bg": (0.80, 0.22, 0.22, 1),      # Kapat [X] butonu arka planı
    "btn_close_text": (1, 1, 1, 1),             # Kapat [X] butonu yazısı
}

# Assets klasöründeki font yolunu kontrol et
FONT_PATH = os.path.join("assets", "Roboto-Regular.ttf")
FONT_DEFAULT = FONT_PATH if os.path.exists(FONT_PATH) else "Roboto"


class BaseCustomPopup(Popup):
    """
    Tüm projedeki Popup'lar için merkezi temel sınıf.
    Tema, fontlar, yuvarlatılmış kenarlar ve sorunsuz kapatma [X] butonu sağlar.
    """

    def __init__(self, title_text="PANEL", content_widget=None, **kwargs):
        # Kivy varsayılan çerçevesini sıfırla
        kwargs.setdefault('title', '')
        kwargs.setdefault('separator_height', 0)
        kwargs.setdefault('size_hint', (0.90, 0.88))
        kwargs.setdefault('background', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))  # Kivy'nin varsayılan gri popup resmini kapat
        kwargs.setdefault('auto_dismiss', True)               # Dışarıya basınca da kapanabilsin

        super().__init__(**kwargs)

        # --- ANA DIŞ KUTU ---
        main_box = BoxLayout(
            orientation='vertical',
            spacing=dp(6),
            padding=dp(8)
        )

        # Arka plan ve kenarlık çizimi
        with main_box.canvas.before:
            Color(*THEME["bg_popup"])
            self._bg = RoundedRectangle(pos=main_box.pos, size=main_box.size, radius=[dp(10)])
            Color(*THEME["border"])
            self._border = Line(rounded_rectangle=(main_box.x, main_box.y, main_box.width, main_box.height, dp(10)), width=1.2)

        main_box.bind(pos=self._update_canvas, size=self._update_canvas)

        # --- ŞIK BAŞLIK ÇUBUĞU (Title + Kapat Butonu) ---
        header = BoxLayout(
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
            padding=(dp(8), dp(2))
        )

        with header.canvas.before:
            Color(*THEME["header_bg"])
            self._header_bg = RoundedRectangle(pos=header.pos, size=header.size, radius=[dp(6)])

        header.bind(pos=self._update_header_bg, size=self._update_header_bg)

        # Panel Başlığı
        title_label = Label(
            text=f"[b]{title_text.upper()}[/b]",
            markup=True,
            font_size=dp(14),
            font_name=FONT_DEFAULT,
            halign='left',
            valign='middle',
            color=THEME["text_title"]
        )
        title_label.bind(size=title_label.setter('text_size'))
        header.add_widget(title_label)

        # Sağ Üst Kapat Butonu [X]
        btn_close = Button(
            text="X",
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            pos_hint={'center_y': 0.5},
            background_normal="",
            background_color=THEME["btn_close_bg"],
            color=THEME["btn_close_text"],
            font_name=FONT_DEFAULT,
            font_size=dp(14),
            bold=True
        )
        btn_close.bind(on_release=lambda *args: self.dismiss())
        header.add_widget(btn_close)

        main_box.add_widget(header)

        # --- İÇERİK ALANI ---
        self.content_holder = BoxLayout(orientation='vertical')
        if content_widget:
            self.content_holder.add_widget(content_widget)

        main_box.add_widget(self.content_holder)
        self.content = main_box

    def set_content(self, widget):
        self.content_holder.clear_widgets()
        self.content_holder.add_widget(widget)

    def _update_canvas(self, instance, value):
        self._bg.pos = instance.pos
        self._bg.size = instance.size
        self._border.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(10))

    def _update_header_bg(self, instance, value):
        self._header_bg.pos = instance.pos
        self._header_bg.size = instance.size


# ============================================================
# BAĞIMSIZ TEST UYGULAMASI (DOĞRUDAN ÇALIŞTIRMAK İÇİN)
# ============================================================
if __name__ == "__main__":
    class BasePopupTestApp(App):
        def build(self):
            # Ekranda testi başlatacak tek bir buton
            btn = Button(
                text="TEST PANELİNİ AÇ",
                size_hint=(None, None),
                size=(dp(200), dp(50)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            )
            btn.bind(on_release=self.show_popup)
            return btn

        def show_popup(self, *_):
            dummy_content = Label(
                text="Base Popup Test Ekrani\n\n- Tema Koyu & Temiz\n- [X] Butonu Sag Ustte\n- Kapatmak Icin X'e Basin!",
                halign="center",
                valign="middle"
            )
            popup = BaseCustomPopup(
                title_text="Ana Menü / Standart Panel",
                content_widget=dummy_content
            )
            popup.open()

    BasePopupTestApp().run()