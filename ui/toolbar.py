# ui/toolbar.py
"""
CAD için toolbar bileşeni.

Kullanım:
    from ui.toolbar import Toolbar
    
    toolbar = Toolbar(actions=[
        ("S2K", "folder", callback_fn),
        ("Test", "box", callback_fn),
        ...
    ])
    root.add_widget(toolbar)
"""
from pathlib import Path

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock


# İkon dizini
ICON_DIR = Path("assets/icons")


# ============================================================
# BUTON
# ============================================================

from kivy.uix.behaviors import ButtonBehavior

class IconTextButton(ButtonBehavior, BoxLayout):
    def __init__(self, text, icon=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_x', None)
        kwargs.setdefault('width', dp(95))
        kwargs.setdefault('spacing', dp(4))
        kwargs.setdefault('padding', (dp(6), dp(2)))
        
        super().__init__(**kwargs)
        
        # Arka plan
        with self.canvas.before:
            self._bg_color = Color(0.22, 0.24, 0.30, 1.0)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(state=self._update_state)
        
        if icon:
            icon_path = ICON_DIR / f"{icon}.png"
            if icon_path.exists():
                self.add_widget(Image(
                    source=str(icon_path),
                    size_hint=(None, 1),
                    width=dp(18),
                ))
        
        self.add_widget(Label(
            text=text,
            font_size=dp(11),
            color=(0.9, 0.9, 0.9, 1.0),
        ))
    
    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
    
    def _update_state(self, *args):
        if self.state == 'down':
            self._bg_color.rgba = (0.35, 0.42, 0.55, 1.0)
        else:
            self._bg_color.rgba = (0.22, 0.24, 0.30, 1.0)


# ============================================================
# TOOLBAR
# ============================================================

class Toolbar(BoxLayout):
    """
    Yatay toolbar.
    
    `actions` listesi:
        [
            ("Metin", "icon_ismi", callback),
            ...
            None,   # ayırıcı
            ...
        ]
    """
    
    def __init__(self, actions=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('size_hint_x', 1)
        kwargs.setdefault('height', dp(34))
        kwargs.setdefault('spacing', dp(2))
        kwargs.setdefault('padding', (dp(4), dp(2)))
        kwargs.setdefault('pos_hint', {'top': 1, 'x': 0})
        
        super().__init__(**kwargs)
        
        # Arka plan
        with self.canvas.before:
            Color(0.12, 0.14, 0.18, 1.0)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Butonlar
        if actions:
            for action in actions:
                if action is None:
                    self._add_separator()
                else:
                    text, icon, callback = action
                    btn = IconTextButton(
                        text=text,
                        icon=icon,
                    )
                    btn.bind(on_release=callback)
                    self.add_widget(btn)
    
    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
    
    def _add_separator(self):
        """Dikey ayırıcı çizgi."""
        sep = BoxLayout(
            size_hint_x=None,
            width=dp(1),
            padding=(0, dp(6)),
        )
        with sep.canvas:
            Color(0.35, 0.38, 0.42, 1.0)
            sep._rect = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(
            pos=lambda *a: setattr(sep._rect, 'pos', sep.pos),
            size=lambda *a: setattr(sep._rect, 'size', sep.size),
        )
        self.add_widget(sep)