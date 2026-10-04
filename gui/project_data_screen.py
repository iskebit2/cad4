# gui/project_data_screen.py
"""
Ana ekran: menü + browser + detay paneli.
"""
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.properties import ObjectProperty, StringProperty

from domain.definition_manager import DefinitionManager
from data.serializer import save_project, load_project
from data.s2k_importer import S2KParser
from data.s2k_exporter import S2KWriter
from gui.definition_browser import DefinitionBrowser
from gui.definition_editor import open_editor


class ProjectDataScreen(BoxLayout):
    manager = ObjectProperty(None)
    current_path = StringProperty("")

    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.manager = DefinitionManager()
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # --- Toolbar ---
        bar = BoxLayout(size_hint_y=None, height=48, spacing=4, padding=4)
        for text, cb in (
            ("Yeni", self.action_new),
            ("Aç (.json)", self.action_open),
            ("Kaydet", self.action_save),
            ("Farklı Kaydet", self.action_save_as),
            ("S2K İçe Aktar", self.action_import_s2k),
            ("S2K Dışa Aktar", self.action_export_s2k),
        ):
            b = Button(text=text)
            b.bind(on_release=lambda *_, f=cb: f())
            bar.add_widget(b)
        self.add_widget(bar)

        # --- Gövde: browser | detail ---
        body = BoxLayout(orientation="horizontal")

        self.browser = DefinitionBrowser(
            self.manager,
            on_select=self._on_select,
            on_save=self._on_editor_save,
            size_hint_x=0.45,
        )
        body.add_widget(self.browser)

        self.detail = BoxLayout(orientation="vertical", padding=8)
        self.detail.add_widget(Label(
            text="Soldaki ağaçtan bir öğe seçin",
            color=(0.6, 0.6, 0.6, 1),
        ))
        body.add_widget(self.detail)

        self.add_widget(body)

    # ------------------------------------------------------------------
    def _on_select(self, obj):
        self.detail.clear_widgets()
        title = getattr(obj, "name", type(obj).__name__)
        self.detail.add_widget(Label(
            text=f"[b]{title}[/b]", markup=True,
            size_hint_y=None, height=30,
        ))
        info = self._summarize(obj)
        self.detail.add_widget(Label(text=info, size_hint_y=None, height=200))
        btn = Button(text="✎ Düzenle", size_hint_y=None, height=40)
        btn.bind(on_release=lambda *_: open_editor(obj, self._on_editor_save))
        self.detail.add_widget(btn)

    @staticmethod
    def _summarize(obj) -> str:
        from gui.property_editor import iter_fields
        lines = []
        for name, value in iter_fields(obj):
            if isinstance(value, (list, dict)) and len(str(value)) > 60:
                value = f"<{type(value).__name__} len={len(value)}>"
            lines.append(f"{name} = {value}")
        return "\n".join(lines)

    def _on_editor_save(self, obj, values: dict):
        for k, v in values.items():
            if v is None and k in ("static_assignments", "items", "assignments",
                                    "points", "DOF", "Ke", "Ce", "Fixed"):
                continue
            try:
                setattr(obj, k, v)
            except Exception:
                pass
        self.browser.refresh()
        self._on_select(obj)

    # ------------------------------------------------------------------
    # Dosya işlemleri
    # ------------------------------------------------------------------
    def action_new(self):
        self.manager = DefinitionManager()
        self.browser.set_manager(self.manager)
        self.current_path = ""

    def action_open(self):
        self._file_dialog(mode="open", filters=["*.json"])

    def action_save(self):
        if self.current_path:
            save_project(self.manager, self.current_path)
        else:
            self.action_save_as()

    def action_save_as(self):
        self._file_dialog(mode="save", filters=["*.json"])

    def action_import_s2k(self):
        self._file_dialog(mode="s2k", filters=["*.s2k"])

    def action_export_s2k(self):
        self._file_dialog(mode="s2k_out", filters=["*.s2k"])

    def _file_dialog(self, mode: str, filters):
        fc = FileChooserListView(filters=filters, path=os.getcwd())
        box = BoxLayout(orientation="vertical")
        box.add_widget(fc)
        name_input = None
        if mode in ("save", "s2k_out"):
            from kivy.uix.textinput import TextInput
            name_input = TextInput(text="project.json" if mode == "save"
                                   else "export.s2k",
                                   size_hint_y=None, height=36)
            box.add_widget(name_input)
        btn = Button(text="Seç", size_hint_y=None, height=40)
        box.add_widget(btn)

        popup = Popup(title="Dosya Seç", content=box, size_hint=(0.9, 0.9))

        def on_ok(*_):
            try:
                if mode in ("save", "s2k_out"):
                    if not name_input.text:
                        return
                    base = fc.path or os.getcwd()
                    path = os.path.join(base, name_input.text)
                    if mode == "save":
                        save_project(self.manager, path)
                        self.current_path = path
                    else:
                        S2KWriter(self.manager).write(path)
                else:
                    if not fc.selection:
                        return
                    path = fc.selection[0]
                    if mode == "open":
                        load_project(self.manager, path)
                        self.current_path = path
                    elif mode == "s2k":
                        S2KParser(path).import_to(self.manager)
                popup.dismiss()
                self.browser.refresh()
            except Exception as e:
                popup.dismiss()
                Popup(title="Hata",
                      content=Label(text=str(e)),
                      size_hint=(0.6, 0.4)).open()

        btn.bind(on_release=on_ok)
        popup.open()