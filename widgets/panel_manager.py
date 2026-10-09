# widgets/panel_manager.py
"""PanelManager — Panel aç/kapa, pozisyon, modal kontrolü."""

from kivy.core.window import Window
from gui.panel_view_filter import ViewFilterPanel
from logging_config import CadLogger
logger = CadLogger.get(__name__)


class PanelManager:
    def __init__(self, widget):
        self.w = widget
        self.panels = []       # aktif paneller

    def register(self, panel, position="top_right"):
        """Panel'i widget'a ekle ve yönet."""
        self.w.add_widget(panel)
        panel._pm_position = position
        self.panels.append(panel)
        self._reposition(panel)
        return panel

    def create_view_filter_panel(self, on_apply):
        panel = ViewFilterPanel(camera=None, on_apply=on_apply)
        return self.register(panel, "top_right")

    def toggle_view_filter_panel(self):
        for p in self.panels:
            if isinstance(p, ViewFilterPanel):
                if p.is_hidden():
                    p.show()
                else:
                    p.hide()
                return

    def is_any_open(self):
        """Sadece kullanıcıya gösterilen paneller."""
        return any(not p.is_hidden() for p in self.panels)

    def collide(self, pos):
        """Touch pozisyonu herhangi bir açık panele çarpıyor mu?"""
        for p in self.panels:
            if p.is_hidden():
                continue
            if p.collide_point(*pos):
                return True
        return False

    def reposition_all(self):
        for p in self.panels:
            self._reposition(p)

    def _reposition(self, panel):
        w = self.w
        pos = getattr(panel, "_pm_position", "top_right")
        margin = 10
        if pos == "top_right":
            panel.pos = (w.width - panel.width - margin,
                         w.height - panel.height - margin)
        elif pos == "top_left":
            panel.pos = (margin, w.height - panel.height - margin)
        elif pos == "bottom_right":
            panel.pos = (w.width - panel.width - margin, margin)
        elif pos == "bottom_left":
            panel.pos = (margin, margin)