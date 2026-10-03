# gui/status_bar.py
"""
Alt durum çubuğu widget'ı.
StatusManager'a bağlı olarak renk ve mesaj günceller.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import ListProperty

from structload.utils.status_manager import status


LEVEL_COLORS = {
    "info":    (0.20, 0.25, 0.30, 1),
    "success": (0.15, 0.45, 0.25, 1),
    "warning": (0.70, 0.55, 0.10, 1),
    "error":   (0.65, 0.15, 0.15, 1),
    "debug":   (0.30, 0.30, 0.40, 1),
}


class StatusBar(BoxLayout):
    """Alt durum çubuğu."""

    def __init__(self, on_log_button=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(32)
        self.padding = dp(6)
        self.spacing = dp(6)
        self.on_log_button = on_log_button

        # Arka plan
        with self.canvas.before:
            self._bg_color = Color(*LEVEL_COLORS["info"])
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Mesaj label
        self.msg_label = Label(
            text=status.message,
            halign="left",
            valign="middle",
            color=(1, 1, 1, 1),
            size_hint_x=0.85,
        )
        self.msg_label.bind(size=lambda l, s: setattr(l, "text_size", s))
        self.add_widget(self.msg_label)

        # Log butonu
        self.log_btn = Button(
            text="📋 Log",
            size_hint_x=0.15,
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=dp(12),
        )
        if on_log_button:
            self.log_btn.bind(on_press=on_log_button)
        self.add_widget(self.log_btn)

        # Bağlantılar
        status.bind(message=self._on_message, level=self._on_level)
        self._on_level(status, status.level)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _on_message(self, instance, value):
        self.msg_label.text = value

    def _on_level(self, instance, value):
        color = LEVEL_COLORS.get(value, LEVEL_COLORS["info"])
        self._bg_color.rgba = color