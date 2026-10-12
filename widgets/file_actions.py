# app/file_actions.py
"""Dosya aç/kaydet/import işlemleri — MainApp'ten bağımsız."""

import os
import threading
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.popup import Popup

from gui.basecustompopup import FONT_DEFAULT
from domain.scene import Scene

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class FileActions:
    """
    MainApp'e bağımlı olmayan dosya işlemleri.
    Sahne değişikliği için bir callback alır: on_scene_loaded(scene, path)
    """

    def __init__(self, on_scene_loaded, on_error, on_loading_show, on_loading_hide):
        self.on_scene_loaded = on_scene_loaded
        self.on_error = on_error
        self.on_loading_show = on_loading_show
        self.on_loading_hide = on_loading_hide
        self._picker_open = False

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def open_project(self, *_):
        def on_file(path):
            logger.info(f"[File] JSON açılıyor: {path}")
            self.on_loading_show("Model yükleniyor...")

            def load_thread():
                try:
                    loaded = Scene.load_from_json(path)
                    Clock.schedule_once(
                        lambda dt: self._on_loaded(loaded, path), 0)
                except Exception as e:
                    logger.error(f"Proje açma hatası: {e}", exc_info=True)
                    Clock.schedule_once(
                        lambda dt: self.on_error(f"Dosya Açılamadı:\n{e}"), 0)

            threading.Thread(target=load_thread, daemon=True).start()

        self.pick_file(mode="open", filters=["*.json"], on_select=on_file)

    def save_project(self, *_):
        if not hasattr(self, "_current_path"):
            self._current_path = ""
        if self._current_path:
            self._save_to_path(self._current_path)
        else:
            self.save_as()

    def save_as(self, *_):
        def on_file(path):
            if not path.endswith(".json"):
                path += ".json"
            self._save_to_path(path)
            self._current_path = path

        self.pick_file(
            mode="save",
            filters=["*.json"],
            on_select=on_file,
            default_name="model_projesi.json",
        )

    def import_s2k(self, *_):
        def on_file(path):
            logger.info(f"[File] S2K: {path}")
            self.on_loading_show("S2K yükleniyor...")

            def load_thread():
                try:
                    from tools.s2kloader import S2KLoader
                    imported = S2KLoader(path).load()
                    Clock.schedule_once(
                        lambda dt: self.on_scene_loaded(imported, path), 0)
                except Exception as e:
                    logger.error(f"S2K yükleme hatası: {e}", exc_info=True)
                    Clock.schedule_once(
                        lambda dt: self.on_error(f"S2K Yüklenemedi:\n{e}"), 0)

            threading.Thread(target=load_thread, daemon=True).start()

        self.pick_file(mode="open", filters=["*.s2k"], on_select=on_file)

    def set_current_path(self, path):
        self._current_path = path

    def get_current_path(self):
        return getattr(self, "_current_path", "")

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------
    def _save_to_path(self, path):
        try:
            # Sahne erişimi MainApp üzerinden
            from domain.scene import Scene
            # NOT: Sahneyi parametre olarak almak daha temiz olur
            # (bu örnekte basit tutuyoruz)
            self.on_save_to_path(path)
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}", exc_info=True)
            self.on_error(f"Kaydedilemedi:\n{e}")

    def _on_loaded(self, scene, path):
        self._current_path = path
        self.on_scene_loaded(scene, path)
        self.on_loading_hide()

    # ------------------------------------------------------------------
    # FILE PICKER
    # ------------------------------------------------------------------
    def pick_file(self, mode: str, filters: list, on_select, default_name=""):
        if self._picker_open:
            return
        self._picker_open = True

        fc = FileChooserListView(filters=filters, path=os.getcwd())
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        box.add_widget(fc)

        name_input = None
        if mode == "save":
            name_input = TextInput(
                text=default_name, size_hint_y=None, height=dp(40),
                hint_text="Dosya adı girin...",
                font_name=FONT_DEFAULT, multiline=False,
            )
            box.add_widget(name_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        ok_btn = Button(
            text="Tamam", font_name=FONT_DEFAULT,
            background_normal="", background_color=(0.18, 0.50, 0.32, 1),
            color=(1, 1, 1, 1), bold=True,
        )
        cancel_btn = Button(
            text="İptal", font_name=FONT_DEFAULT,
            background_normal="", background_color=(0.40, 0.40, 0.40, 1),
            color=(1, 1, 1, 1),
        )
        btn_row.add_widget(ok_btn)
        btn_row.add_widget(cancel_btn)
        box.add_widget(btn_row)

        popup = Popup(
            title="Dosya Seç", content=box,
            size_hint=(0.85, 0.85), auto_dismiss=False,
            separator_height=0,
        )

        processed = [False]

        def _finish(selection=None):
            if processed[0]:
                return
            processed[0] = True
            self._picker_open = False
            popup.dismiss()
            if selection:
                on_select(selection)

        def _on_ok(*_):
            sel = fc.selection[0] if fc.selection else None
            if mode == "save" and name_input is not None:
                name = name_input.text.strip()
                if name:
                    sel = os.path.join(fc.path, name)
            if sel:
                _finish(sel)

        def _on_cancel(*_):
            _finish(None)

        def _on_dismiss(*_):
            self._picker_open = False
            if not processed[0]:
                processed[0] = True

        ok_btn.bind(on_release=_on_ok)
        cancel_btn.bind(on_release=_on_cancel)
        popup.bind(on_dismiss=_on_dismiss)
        popup.open()