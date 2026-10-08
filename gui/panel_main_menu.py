# gui/panel_main_menu.py
import sys
from pathlib import Path

FILE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FILE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT

MENU_THEME = {
    "btn_bg": (0.12, 0.15, 0.20, 1),
    "btn_accent": (0.20, 0.50, 0.85, 1),
    "text_main": (0.92, 0.94, 0.98, 1),
}

class MenuButton(Button):
    def __init__(self, title="", subtitle="", callback=None, is_accent=False, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = MENU_THEME["btn_accent"] if is_accent else MENU_THEME["btn_bg"]
        self.size_hint_y = None
        self.height = dp(64)
        self.text = f"[b]{title}[/b]\n[size=11sp]{subtitle}[/size]"
        self.markup = True
        self.font_name = FONT_DEFAULT
        self.font_size = dp(14)
        self.color = MENU_THEME["text_main"]
        self.halign = "center"
        self.valign = "middle"
        if callback:
            self.bind(on_release=callback)

class MainMenuContent(BoxLayout):
    def __init__(self, on_action_selected=None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(10), padding=dp(6), **kwargs)
        self.on_action_selected = on_action_selected

        status_box = BoxLayout(size_hint_y=None, height=dp(24))
        lbl_status = Label(
            text="[color=50a0ff]●[/color] SISTEM HAZIR | CAD Sahnesi Aktif",
            markup=True,
            font_size=dp(11),
            font_name=FONT_DEFAULT,
            halign="left",
            valign="middle"
        )
        lbl_status.bind(size=lbl_status.setter("text_size"))
        status_box.add_widget(lbl_status)
        self.add_widget(status_box)

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=1)

        grid.add_widget(MenuButton("MODEL INSPECTOR", "Eleman ve metraj detaylari", lambda *a: self._trigger("inspector"), True))
        grid.add_widget(MenuButton("ANALIZ VE YUKLER", "Statik / Deprem hesap paneli", lambda *a: self._trigger("analysis")))
        grid.add_widget(MenuButton("PROJE AÇ (JSON)", "Kayıtlı modeli sahneye yükle", lambda *a: self._trigger("open_project")))
        grid.add_widget(MenuButton("PROJE KAYDET (JSON)", "Mevcut sahneyi diske kaydet", lambda *a: self._trigger("save_project")))
        grid.add_widget(MenuButton("SAP2000 IMPORT", "S2K veya Canlı Bağlantı", lambda *a: self._trigger("import_s2k")))
        grid.add_widget(MenuButton("YENİ MODEL", "Temiz bir çalışma alanı aç", lambda *a: self._trigger("new_project")))
        grid.add_widget(MenuButton("GÖRÜNÜRLÜK FİLTRESİ", "Elemanları tek tek veya toplu gizle", lambda *a: self._trigger("visibility")))
        self.add_widget(grid)

    def _trigger(self, action_key):
        if self.on_action_selected:
            self.on_action_selected(action_key)

class MainMenuPanel(BaseCustomPopup):
    def __init__(self, on_action_selected=None, **kwargs):
        self.menu_content = MainMenuContent(on_action_selected=self._handle_action)
        self.external_callback = on_action_selected
        super().__init__(
            title_text="ANA MENU / KONTROL MERKEZI",
            content_widget=self.menu_content,
            size_hint=(0.85, 0.80),
            **kwargs
        )

    def _handle_action(self, action_key):
        self.dismiss()
        if self.external_callback:
            self.external_callback(action_key)

if __name__ == "__main__":
    class MainMenuTestApp(App):
        def build(self):
            btn = Button(
                text="ANA MENUYU AÇ",
                size_hint=(None, None),
                size=(dp(200), dp(50)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            )
            btn.bind(on_release=self.show_menu)
            return btn

        def show_menu(self, *_):
            menu = MainMenuPanel(on_action_selected=self.on_menu_choice)
            menu.open()

        def on_menu_choice(self, action_key):
            print(f"Secilen Menü Aksiyonu: {action_key}")

    MainMenuTestApp().run()