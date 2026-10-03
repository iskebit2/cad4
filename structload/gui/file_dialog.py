# gui/file_dialog.py
"""
JSON Dosya Aç / Kaydet Diyaloğu (Kivy)

Kullanım:
    dialog = FileDialog(mode="open", callback=func)
    popup  = Popup(title="...", content=dialog, size_hint=(0.95, 0.9))
    dialog.popup = popup
    popup.open()
"""

import json
import os
from pathlib import Path

import traceback

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput


class FileDialog(BoxLayout):
    """
    mode = "open"  → mevcut JSON dosyasını seçer, callback(config_dict) çağırır.
    mode = "save"  → dosya adı girer, callback(path) çağırır.
    """

    def __init__(self, callback, mode="open", path=None, default_name="config.json", **kwargs):
        super().__init__(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(8),
            **kwargs,
        )
        self.callback = callback
        self.mode = mode
        self.popup = None

        # Başlangıç dizini
        start_path = str(Path.cwd())
        if not os.path.exists(start_path):
            start_path = os.path.expanduser("~")

        self.filechooser = FileChooserListView(
            path=start_path,
            filters=["*.json", "*.JSON"],
        )
        self.add_widget(self.filechooser)

        # Save modunda dosya adı alanı
        if mode == "save":
            name_row = BoxLayout(
                size_hint_y=None,
                height=dp(45),
                spacing=dp(6),
            )
            name_row.add_widget(Label(text="Dosya adı:", size_hint_x=0.3))
            self.name_input = TextInput(
                text=default_name,
                multiline=False,
                size_hint_x=0.7,
            )
            name_row.add_widget(self.name_input)
            self.add_widget(name_row)
        else:
            self.name_input = None

        # Butonlar
        buttons = BoxLayout(
            size_hint_y=None,
            height=dp(52),
            spacing=dp(8),
        )
        action_text = "Aç" if mode == "open" else "Kaydet"
        action_btn = Button(
            text=action_text,
            background_color=(0.20, 0.70, 0.35, 1),
            background_normal="",
        )
        cancel_btn = Button(
            text="İptal",
            background_color=(0.85, 0.30, 0.30, 1),
            background_normal="",
        )
        buttons.add_widget(action_btn)
        buttons.add_widget(cancel_btn)
        self.add_widget(buttons)

        action_btn.bind(on_press=self._on_action)
        cancel_btn.bind(on_press=self.close)

    # ------------------------------------------------------------------
    def _on_action(self, *args):
        if self.mode == "open":
            self._open_file()
        else:
            self._save_file()

    # ------------------------------------------------------------------
    def _open_file(self):
        try:
            if not self.filechooser.selection:
                self._msg("Uyarı", "Lütfen bir dosya seçin")
                return

            path = self.filechooser.selection[0]
            if not os.path.isfile(path):
                self._msg("Uyarı", "Lütfen bir dosya seçin (klasör değil)")
                return

            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)

            self.callback(config, path)
            self.close()

        except json.JSONDecodeError as e:
            self._msg("JSON Hatası", f"Geçersiz JSON:\n{e}")
        except Exception as e:
            traceback.print_exc()
            self._msg("Dosya Hatası", str(e))

    # ------------------------------------------------------------------
    def _save_file(self):
        try:
            # Klasör seçili mi?
            if self.filechooser.selection:
                sel = self.filechooser.selection[0]
                folder = sel if os.path.isdir(sel) else os.path.dirname(sel)
            else:
                folder = self.filechooser.path

            name = (self.name_input.text or "").strip()
            if not name:
                self._msg("Uyarı", "Dosya adı boş olamaz")
                return
            if not name.lower().endswith(".json"):
                name += ".json"

            full_path = os.path.join(folder, name)
            self.callback(full_path)
            self.close()

        except Exception as e:
            traceback.print_exc()
            self._msg("Kayıt Hatası", str(e))

    # ------------------------------------------------------------------
    def close(self, *args):
        if self.popup:
            self.popup.dismiss()

    def _msg(self, title, msg):
        p = Popup(
            title=title,
            content=Label(text=str(msg)),
            size_hint=(0.7, 0.35),
        )
        p.open()