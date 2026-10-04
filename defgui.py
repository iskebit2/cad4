# main.py
"""
Definition Kitchen — Kivy App girişi.
"""
from kivy.app import App
from kivy.core.window import Window

from gui.project_data_screen import ProjectDataScreen

Window.size = (1280, 800)


class DefinitionKitchenApp(App):
    title = "Definition Kitchen — SAP2000 Uyumlu Veri Yönetimi"

    def build(self):
        return ProjectDataScreen()


if __name__ == "__main__":
    DefinitionKitchenApp().run()