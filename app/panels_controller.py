# app/panels_controller.py
"""Panel aç/kapa koordinasyonu — MainApp'in UI sorumluluğunu üstlenir."""

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class PanelsController:
    """
    MainApp panel popup'larını yönetir.
    PropertiesPanel gibi non-popup paneller burada değil, KivyCADWidget'ta.
    """

    def __init__(self, app):
        self.app = app
        self.inspector_popup = None
        self.analysis_popup = None
        self.menu_popup = None
        self.wind_panel_popup = None

    # ------------------------------------------------------------------
    # MAIN MENU
    # ------------------------------------------------------------------
    def open_main_menu(self, *_):
        if self.menu_popup:
            return
        from gui.panel_main_menu import MainMenuPanel
        self.menu_popup = MainMenuPanel(
            on_action_selected=self._on_menu_choice)
        self.menu_popup.bind(
            on_dismiss=lambda *_: setattr(self, 'menu_popup', None))
        self.menu_popup.open()

    def _on_menu_choice(self, action_key):
        dispatch = {
            "inspector":     self.show_inspector,
            "analysis":      self.show_analysis,
            "open_project":  self.app.actions.open_project,
            "save_project":  self.app.actions.save_project,
            "import_s2k":    self.app.actions.import_s2k,
            "new_project":   self.app.action_new,
            "visibility":    self.show_visibility,
        }
        handler = dispatch.get(action_key)
        if handler:
            handler()

    # ------------------------------------------------------------------
    # INSPECTOR
    # ------------------------------------------------------------------
    def show_inspector(self, *_):
        if self.inspector_popup:
            return
        from gui.panel_inspector import ModelInspectorPanel
        self.inspector_popup = ModelInspectorPanel(scene=self.app.scene)
        self.inspector_popup.bind(
            on_dismiss=lambda *_: setattr(self, 'inspector_popup', None))
        self.inspector_popup.open()

    # ------------------------------------------------------------------
    # ANALYSIS
    # ------------------------------------------------------------------
    def show_analysis(self, *_):
        if self.analysis_popup:
            return
        from gui.analysis_popup import AnalysisPopup
        self.analysis_popup = AnalysisPopup(proje_data=self.app.scene)
        self.analysis_popup.bind(
            on_dismiss=lambda *_: setattr(self, 'analysis_popup', None))
        self.analysis_popup.open()

    # ------------------------------------------------------------------
    # VISIBILITY
    # ------------------------------------------------------------------
    def show_visibility(self, *_):
        from gui.panel_visibility import VisibilityPanel

        def on_changed():
            if self.app.engine and hasattr(self.app.engine, 'renderer'):
                self.app.engine.renderer.update_geo(self.app.scene)

        panel = VisibilityPanel(scene=self.app.scene,
                                on_visibility_changed=on_changed)
        panel.open()

    # ------------------------------------------------------------------
    # WIND CONFIG
    # ------------------------------------------------------------------
    def show_wind_config(self, *_):
        from gui.panel_wind_config import WindConfigPanel

        def _on_confirm(w_dir, engine_kwargs):
            if self.wind_panel_popup:
                self.wind_panel_popup.dismiss()
            self.app.run_wind_analysis_ui(w_dir, engine_kwargs)

        self.wind_panel_popup = WindConfigPanel(
            scene=self.app.scene,
            on_run_analysis=_on_confirm,
        )
        self.wind_panel_popup.open()