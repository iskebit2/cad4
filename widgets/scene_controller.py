# app/scene_controller.py
"""Sahne yükleme/değiştirme işlemleri."""

import threading
from kivy.clock import Clock
from domain.scene import Scene

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class SceneController:
    """Sahne değişikliği, yükleme, wind analizi sonrası güncellemeler."""

    def __init__(self, app):
        self.app = app

    # ------------------------------------------------------------------
    # SAHNE DEĞİŞTİRME
    # ------------------------------------------------------------------
    def apply_scene(self, new_scene, path=""):
        try:
            self.app.scene = new_scene
            eng = self.app.engine
            if eng:
                eng.set_scene(new_scene)
                if hasattr(eng, 'renderer') and eng.renderer:
                    eng.renderer.update_geo(new_scene)
                if hasattr(eng, 'focus_on_model'):
                    eng.focus_on_model()
        except Exception as e:
            logger.error(f"apply_scene hatası: {e}", exc_info=True)
        finally:
            self.app._hide_loading()

    def new_scene(self, *_):
        self.app.scene = Scene()
        self.app.actions.set_current_path("")
        self.apply_scene(self.app.scene)
        self.app.lbl_info.text = "MODEL: YENİ SAHNE"
        logger.info("[Action] Yeni proje")

    # ------------------------------------------------------------------
    # RÜZGAR ANALİZİ
    # ------------------------------------------------------------------
    def run_wind_analysis(self, w_dir, engine_kwargs):
        import threading
        from tools.wind_service import WindSceneAdapter

        self.app._show_loading("Rüzgar bölgeleri hesaplanıyor...")

        def _async():
            try:
                zones = WindSceneAdapter.run_wind_analysis_and_update_scene(
                    scene=self.app.scene,
                    w_dir=w_dir,
                    engine_kwargs=engine_kwargs,
                )
                Clock.schedule_once(
                    lambda dt: self._on_wind_done(len(zones)), 0)
            except Exception as e:
                logger.error(f"Rüzgar analizi: {e}", exc_info=True)
                Clock.schedule_once(
                    lambda dt: self.app._show_error(
                        f"Rüzgar Hesabı Hatası:\n{e}"), 0)

        threading.Thread(target=_async, daemon=True).start()

    def _on_wind_done(self, zone_count):
        self.app._hide_loading()
        logger.info(f"{zone_count} adet rüzgar bölgesi oluşturuldu")
        eng = self.app.engine
        if eng and getattr(eng, 'renderer', None):
            eng.renderer.update_geo(self.app.scene)
        if self.app.cad_widget:
            self.app.cad_widget.canvas.ask_update()

    # ------------------------------------------------------------------
    # SAP IMPORT
    # ------------------------------------------------------------------
    def import_from_sap(self, *_):
        try:
            from tools.sap_connect import cSap
            from exchange.cad4_sap_exchange import import_sap_to_scene

            sap = cSap()
            sap.set_units(9)
            counts = import_sap_to_scene(sap, self.app.engine.scene)
            if counts and self.app.engine:
                self.app.engine.renderer.update_geo(self.app.engine.scene)
                self.app.engine.focus_on_model()
        except Exception as e:
            logger.error(f"SAP Import: {e}", exc_info=True)
            self.app._show_error(f"SAP2000 Bağlantı Hatası:\n{e}")