# gui/basecustompopup.py
"""
Ortak Popup iskeleti.
- Yüksek kontrastlı tema
- auto_dismiss = False  → iç tıklama popup'ı kapatmaz
- use_scroll=True/False → içerik boyutuna göre kaydırma opsiyonel
- set_content() ile içerik değiştirilebilir
"""
FONT_DEFAULT = "DejaVuSans"

from kivy.metrics import dp
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Line

# ============================================================
# TEMA
# ============================================================
THEME = {
    "bg_popup":     (0.08, 0.09, 0.11, 1.00),
    "border":       (0.28, 0.32, 0.38, 1.00),

    "header_bg":    (0.14, 0.16, 0.20, 1.00),
    "text_title":   (0.98, 0.98, 1.00, 1.00),

    "btn_close_bg": (0.85, 0.22, 0.22, 1.00),
    "btn_close_fg": (1.00, 1.00, 1.00, 1.00),

    "text_primary":   (0.95, 0.96, 0.98, 1.00),
    "text_secondary": (0.68, 0.72, 0.78, 1.00),
    "text_accent":    (0.30, 0.85, 0.55, 1.00),

    "input_bg":     (1, 0, 0, 1.00),
    "input_fg":     (1.00, 1.00, 1.00, 1.00),
    "input_hint":   (0.55, 0.60, 0.68, 1.00),
    "input_cursor": (0.30, 0.85, 0.55, 1.00),

    "btn_bg":       (0.22, 0.26, 0.32, 1.00),
    "btn_fg":       (0.98, 0.98, 1.00, 1.00),

    "btn_run_bg":   (0.18, 0.65, 0.40, 1.00),
    "btn_run_fg":   (1.00, 1.00, 1.00, 1.00),
}




# ============================================================
# YARDIMCILAR
# ============================================================
def make_text_input(text="", readonly=False, **kw):
    return TextInput(
        text=text,
        readonly=readonly,
        font_name=FONT_DEFAULT,
        font_size=dp(12),
        multiline=False,
        size_hint=(1, 1),
        background_color=THEME["input_bg"],
        foreground_color=THEME["input_fg"],
        cursor_color=THEME["input_cursor"],
        hint_text_color=THEME["input_hint"],
        selection_color=THEME["input_cursor"],
        padding=(dp(6), dp(6)),
        **kw,
    )


def make_spinner(values, text=None, **kw):
    return Spinner(
        text=text or (values[0] if values else ""),
        values=values,
        font_name=FONT_DEFAULT,
        font_size=dp(12),
        size_hint=(1, 1),
        background_normal="",
        background_color=THEME["input_bg"],
        color=THEME["input_fg"],
        **kw,
    )


def make_button(text, accent=False, **kw):
    bg = THEME["btn_run_bg"] if accent else THEME["btn_bg"]
    fg = THEME["btn_run_fg"] if accent else THEME["btn_fg"]
    return Button(
        text=text,
        font_name=FONT_DEFAULT,
        font_size=dp(12),
        bold=accent,
        background_normal="",
        background_color=bg,
        color=fg,
        **kw,
    )


# ============================================================
# POPUP
# ============================================================
class BaseCustomPopup(Popup):
    def __init__(self, title_text="PANEL", content_widget=None,
                 use_scroll=True, **kwargs):
        kwargs.setdefault("title", "")
        kwargs.setdefault("separator_height", 0)
        kwargs.setdefault("size_hint", (0.80, 0.85))
        kwargs.setdefault("background", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("auto_dismiss", False)

        super().__init__(**kwargs)

        # ---- KÖK ----
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        with root.canvas.before:
            Color(*THEME["bg_popup"])
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(10)])
            Color(*THEME["border"])
            self._border = Line(
                rounded_rectangle=(root.x, root.y, root.width, root.height, dp(10)),
                width=1.2,
            )
        root.bind(pos=self._update_bg, size=self._update_bg)

        # ---- BAŞLIK ----
        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(42), spacing=dp(8), padding=(dp(10), dp(4)))
        with header.canvas.before:
            Color(*THEME["header_bg"])
            self._hbg = RoundedRectangle(pos=header.pos, size=header.size, radius=[dp(8)])
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)

        title = Label(
            text=f"[b]{title_text.upper()}[/b]", markup=True,
            font_name=FONT_DEFAULT, font_size=dp(14),
            color=THEME["text_title"], halign="left", valign="middle",
        )
        title.bind(size=title.setter("text_size"))
        header.add_widget(title)

        close_btn = Button(
            text="✕", size_hint=(None, 1), width=dp(38),
            font_name=FONT_DEFAULT, font_size=dp(16), bold=True,
            background_normal="", background_color=THEME["btn_close_bg"],
            color=THEME["btn_close_fg"],
        )
        close_btn.bind(on_release=lambda *_: self.dismiss())
        header.add_widget(close_btn)
        root.add_widget(header)

        # ---- İÇERİK ----
        self._use_scroll = use_scroll
        self._holder = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp(4),
            padding=(0, dp(4)),
        )

        if use_scroll:
            scroll = ScrollView(
                size_hint=(1, 1), bar_width=dp(6),
                do_scroll_x=False, do_scroll_y=True,
            )
            scroll.add_widget(self._holder)
            root.add_widget(scroll)
        else:
            root.add_widget(self._holder)

        if content_widget is not None:
            self._holder.add_widget(content_widget)

        self.content = root

        

    # ---- API ----
    def set_content(self, widget):
        self._holder.clear_widgets()
        if widget is not None:
            self._holder.add_widget(widget)

    # ---- CANVAS ----
    def _update_bg(self, instance, _):
        self._bg.pos = instance.pos
        self._bg.size = instance.size
        self._border.rounded_rectangle = (
            instance.x, instance.y, instance.width, instance.height, dp(10)
        )

    def _update_header_bg(self, instance, _):
        self._hbg.pos = instance.pos
        self._hbg.size = instance.size


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    from kivy.app import App
    from kivy.uix.gridlayout import GridLayout

    class TestApp(App):
        def build(self):
            root = BoxLayout(padding=dp(20))
            btn = Button(text="PANELİ AÇ", size_hint=(None, None),
                         size=(dp(200), dp(50)),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
            btn.bind(on_release=self._open)
            root.add_widget(btn)
            return root

        def _open(self, *_):
            inner = BoxLayout(orientation="vertical", spacing=dp(10),
                              padding=dp(10), size_hint_y=None)
            inner.bind(minimum_height=inner.setter("height"))

            for i in range(3):
                b = make_button(f"Buton {i}", size_hint_y=None, height=dp(46))
                b.bind(on_release=lambda w, n=i: print(f">>> Buton {n} <<<"))
                inner.add_widget(b)

            grid = GridLayout(cols=2, spacing=dp(6),
                              size_hint_y=None, height=dp(80))
            grid.add_widget(Label(text="Değer:", font_name=FONT_DEFAULT,
                                  color=THEME["text_primary"], font_size=dp(12)))
            grid.add_widget(make_text_input("28.0"))
            grid.add_widget(Label(text="Kategori:", font_name=FONT_DEFAULT,
                                  color=THEME["text_primary"], font_size=dp(12)))
            grid.add_widget(make_spinner(["I", "II", "III", "IV"], text="III"))
            inner.add_widget(grid)

            run = make_button("ÇALIŞTIR", accent=True,
                              size_hint_y=None, height=dp(48))
            run.bind(on_release=lambda *_: print(">>> ÇALIŞTIR <<<"))
            inner.add_widget(run)

            BaseCustomPopup(
                title_text="Test",
                content_widget=inner,
                use_scroll=True,
            ).open()

    TestApp().run()