from pathlib import Path
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle

Window.size = (800, 400)

ICON_DIR = Path("assets/icons")


class IconButton(Button):
    def __init__(self, text, icon=None, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        super().__init__(**kwargs)
        
        self.text = ''
        
        with self.canvas.before:
            self._bg_color = Color(0.20, 0.22, 0.28, 1.0)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(state=self._update_state)
        
        self.content = BoxLayout(
            orientation='horizontal',
            spacing=dp(5),
            padding=(dp(6), 0),
            size_hint=(None, None),
            size=self.size,
            pos=self.pos,
        )
        
        if icon:
            icon_path = ICON_DIR / f"{icon}.png"
            print(f"[ICON] Yükleniyor: {icon_path}, var mı: {icon_path.exists()}")
            
            img = Image(
                source=str(icon_path),
                size_hint=(None, None),
                size=(dp(20), dp(20)),
            )
            self.content.add_widget(img)
        
        lbl = Label(
            text=text,
            font_size=dp(11),
            color=(1, 1, 1, 1),
            halign='left',
            valign='middle',
            size_hint=(1, 1),
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.content.add_widget(lbl)
        
        self.add_widget(self.content)
        self.bind(pos=self._update_content, size=self._update_content)
    
    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
    
    def _update_state(self, *args):
        if self.state == 'down':
            self._bg_color.rgba = (0.30, 0.35, 0.45, 1.0)
        else:
            self._bg_color.rgba = (0.20, 0.22, 0.28, 1.0)
    
    def _update_content(self, *args):
        self.content.pos = self.pos
        self.content.size = self.size


class TestApp(App):
    def build(self):
        root = FloatLayout()
        
        with root.canvas.before:
            Color(0, 0, 0.3, 1)
            self.bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self.bg, 'pos', root.pos),
                  size=lambda *a: setattr(self.bg, 'size', root.size))
        
        toolbar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=2,
            padding=2,
            pos_hint={'top': 1, 'x': 0},
        )
        
        # Test butonları
        toolbar.add_widget(IconButton("Test1", icon="folder", size_hint_x=None, width=dp(90)))
        toolbar.add_widget(IconButton("Test2", icon="box",         size_hint_x=None, width=dp(90)))
        toolbar.add_widget(IconButton("NoIcon",                     size_hint_x=None, width=dp(90)))
        
        root.add_widget(toolbar)
        
        return root


TestApp().run()