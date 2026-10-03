# gui/debug_panel.py
"""
Debug/Log paneli.
StatusManager'daki log kayıtlarını renkli olarak gösterir.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp

from structload.utils.status_manager import status


LOG_COLORS = {
    "info":    (0.85, 0.85, 0.85, 1),
    "success": (0.4,  0.9,  0.4,  1),
    "warning": (0.95, 0.75, 0.2,  1),
    "error":   (0.95, 0.4,  0.4,  1),
    "debug":   (0.6,  0.6,  0.6,  1),
}


class DebugPanel(BoxLayout):
    """Log görüntüleme paneli."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(4)
        self.padding = dp(6)

        # Üst bar
        ust = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        ust.add_widget(Label(
            text="Sistem Logları",
            bold=True,
            size_hint_x=0.5,
        ))

        yenile_btn = Button(text="Yenile", size_hint_x=0.2)
        yenile_btn.bind(on_press=lambda *a: self.yenile())
        ust.add_widget(yenile_btn)

        temizle_btn = Button(
            text="Temizle",
            size_hint_x=0.2,
            background_color=(0.7, 0.2, 0.2, 1),
        )
        temizle_btn.bind(on_press=self.temizle)
        ust.add_widget(temizle_btn)

        self.add_widget(ust)

        # Scroll + liste
        self.scroll = ScrollView()
        self.log_layout = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(2),
        )
        self.log_layout.bind(minimum_height=self.log_layout.setter("height"))
        self.scroll.add_widget(self.log_layout)
        self.add_widget(self.scroll)

        # Bağlantı
        status.bind(log_entries=lambda *a: self.yenile())
        self.yenile()

    def yenile(self):
        self.log_layout.clear_widgets()
        for ts, level, msg in status.log_entries:
            color = LOG_COLORS.get(level, LOG_COLORS["info"])
            lbl = Label(
                text=f"[{ts}] [{level.upper():7s}] {msg}",
                size_hint_y=None,
                height=dp(22),
                color=color,
                halign="left",
                valign="middle",
                font_size=dp(11),
            )
            lbl.bind(size=lambda l, s: setattr(l, "text_size", (s[0], None)))
            self.log_layout.add_widget(lbl)

    def temizle(self, instance):
        status.clear_log()