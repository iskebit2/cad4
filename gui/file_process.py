# gui/file_process.py

from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput

# __init__ içine:
#   self.project_popup = None
#   self.current_path = ""


# ========================================================
# PROJECT DATA POPUP
# ========================================================

def show_project_data(self, *_):
    """Definition verisini popup'ta göster."""
    if not self.engine:
        logger.warning("Engine hazır değil")
        return
    if self.project_popup:
        return

    from gui.project_data_panel import ProjectDataPanel

    scene = self.engine.scene
    manager = getattr(scene, "def_mgr", None)
    if manager is None:
        logger.warning("scene.def_mgr yok — boş panel açılıyor")
        from domain.definition_manager import DefinitionManager
        manager = DefinitionManager()

    panel = ProjectDataPanel(
        manager=manager,
        on_change=self._on_project_data_changed,
    )
    self._project_panel = panel   # referans tut

    self.project_popup = Popup(
        title="Project Data",
        content=panel,
        size_hint=(0.92, 0.92),
    )
    self.project_popup.bind(on_dismiss=self._project_closed)
    self.project_popup.open()


def _project_closed(self, *_):
    self.project_popup = None
    self._project_panel = None


def _on_project_data_changed(self):
    """DefinitionManager değişti → CAD'i yeniden çiz."""
    logger.info("[Main] Project data değişti, CAD yeniden çiziliyor")
    try:
        if hasattr(self.engine, "request_redraw"):
            self.engine.request_redraw()
        elif hasattr(self.engine.renderer, "update_geo"):
            self.engine.renderer.update_geo(self.engine.scene)
    except Exception as e:
        logger.warning(f"Redraw hatası: {e}")


# ========================================================
# FILE — New / Open / Save / Save As
# ========================================================

def action_new(self, *_):
    """Yeni proje — mevcut manager'ı YERİNDE sıfırla (referansı koparma)."""
    if not self.engine:
        return

    scene = self.engine.scene
    manager = getattr(scene, "def_mgr", None)
    if manager is None:
        return

    manager.materials.clear()
    manager.sections.clear()
    manager.link_props.clear()
    manager.load_patterns.clear()
    manager.load_cases.clear()
    manager.modal_cases.clear()
    manager.combinations.clear()
    manager.spectrum_functions.clear()
    manager.response_spectrum_cases.clear()
    manager.auto_seismics.clear()
    manager.mass_source_map.clear()

    self.current_path = ""
    self._on_project_data_changed()

    if self._project_panel:
        self._project_panel.refresh()

    logger.info("[Main] Yeni proje")


def action_open(self, *_):
    """JSON projeden yükle → mevcut manager'a in-place."""
    if not self.engine:
        return

    def on_file(path: str):
        try:
            from data.serializer import load_project
            scene = self.engine.scene
            manager = getattr(scene, "def_mgr", None)
            if manager is None:
                from domain.definition_manager import DefinitionManager
                manager = DefinitionManager()
                scene.def_mgr = manager

            load_project(manager, path)
            self.current_path = path

            self._on_project_data_changed()
            if self._project_panel:
                self._project_panel.refresh()

            logger.info(f"[Main] Proje açıldı: {path}")
        except Exception as e:
            logger.error(f"Proje açma hatası: {e}", exc_info=True)
            self._show_error(str(e))

    self._pick_file(
        mode="open",
        filters=["*.json"],
        on_select=on_file,
    )


def action_save(self, *_):
    """Kaydet — path varsa direkt, yoksa Save As."""
    if self.current_path:
        try:
            from data.serializer import save_project
            save_project(self.engine.scene.def_mgr, self.current_path)
            logger.info(f"[Main] Kaydedildi: {self.current_path}")
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}", exc_info=True)
            self._show_error(str(e))
    else:
        self.action_save_as()


def action_save_as(self, *_):
    def on_file(path: str):
        try:
            from data.serializer import save_project
            save_project(self.engine.scene.def_mgr, path)
            self.current_path = path
            logger.info(f"[Main] Kaydedildi: {path}")
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}", exc_info=True)
            self._show_error(str(e))

    self._pick_file(
        mode="save",
        filters=["*.json"],
        on_select=on_file,
        default_name="project.json",
    )


# ========================================================
# S2K IMPORT / EXPORT (definition tablosu)
# ========================================================

def action_import_s2k_definition(self, *_):
    """S2K'dan SADECE definition tablolarını içe aktar (geometri yok)."""
    if not self.engine:
        return

    def on_file(path: str):
        self._show_loading("S2K tanımları yükleniyor...")

        def worker():
            try:
                from data.s2k_importer import S2KParser
                scene = self.engine.scene
                manager = getattr(scene, "def_mgr", None)
                if manager is None:
                    from domain.definition_manager import DefinitionManager
                    manager = DefinitionManager()
                    scene.def_mgr = manager

                S2KParser(path).import_to(manager)

                Clock.schedule_once(
                    lambda dt: self._after_import_definition(), 0
                )
            except Exception as e:
                logger.error(f"S2K definition import hatası: {e}", exc_info=True)
                Clock.schedule_once(lambda dt: self._hide_loading(), 0)

        threading.Thread(target=worker, daemon=True).start()

    self._pick_file(
        mode="open",
        filters=["*.s2k"],
        on_select=on_file,
    )


def _after_import_definition(self):
    self._hide_loading()
    self._on_project_data_changed()
    if self._project_panel:
        self._project_panel.refresh()
    logger.info("[Main] S2K definition import tamam")


def action_export_s2k_definition(self, *_):
    """Definition tablolarını S2K olarak dışa aktar."""
    if not self.engine:
        return

    def on_file(path: str):
        try:
            from data.s2k_exporter import S2KWriter
            S2KWriter(self.engine.scene.def_mgr).write(path)
            logger.info(f"[Main] S2K dışa aktarıldı: {path}")
        except Exception as e:
            logger.error(f"S2K export hatası: {e}", exc_info=True)
            self._show_error(str(e))

    self._pick_file(
        mode="save",
        filters=["*.s2k"],
        on_select=on_file,
        default_name="export.s2k",
    )


# ========================================================
# YARDIMCI: File dialog + Hata popup
# ========================================================

def _pick_file(self, mode: str, filters: list, on_select, default_name: str = ""):
    """
    mode: 'open' | 'save'
    on_select: (path: str) -> None
    """
    import os

    fc = FileChooserListView(filters=filters, path=os.getcwd())
    box = BoxLayout(orientation="vertical", spacing=4, padding=4)
    box.add_widget(fc)

    name_input = None
    if mode == "save":
        name_input = TextInput(
            text=default_name,
            size_hint_y=None, height=36,
            hint_text="Dosya adı",
        )
        box.add_widget(name_input)

    btn_row = BoxLayout(size_hint_y=None, height=44, spacing=6)
    ok_btn = Button(text="Tamam")
    cancel_btn = Button(text="İptal")
    btn_row.add_widget(ok_btn)
    btn_row.add_widget(cancel_btn)
    box.add_widget(btn_row)

    popup = Popup(title="Dosya Seç", content=box,
                  size_hint=(0.9, 0.9))

    def on_ok(*_):
        try:
            if mode == "save":
                if not name_input.text:
                    return
                base = fc.path or os.getcwd()
                path = os.path.join(base, name_input.text)
            else:
                if not fc.selection:
                    return
                path = fc.selection[0]

            popup.dismiss()
            on_select(path)
        except Exception as e:
            logger.error(f"File dialog hatası: {e}", exc_info=True)

    ok_btn.bind(on_release=on_ok)
    cancel_btn.bind(on_release=lambda *_: popup.dismiss())
    popup.open()


def _show_error(self, message: str):
    box = BoxLayout(orientation="vertical", padding=10, spacing=8)
    box.add_widget(Label(text=message))
    btn = Button(text="Tamam", size_hint_y=None, height=40)
    box.add_widget(btn)
    popup = Popup(title="Hata", content=box, size_hint=(0.6, 0.4))
    btn.bind(on_release=lambda *_: popup.dismiss())
    popup.open()