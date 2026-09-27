"""
ui/viewport_manager.py - PySide6 ile Native GLFW Motoru Arasındaki Köprü


"""

import logging
import multiprocessing as mp
from typing import Optional, Any

from domain.scene import Scene

logger = logging.getLogger(__name__)


def _run_engine_process(scene_data: Optional[Any], queue: mp.Queue):
    """
    Müstakil süreç (Process) içinde çalışan GLFW Başlatıcı Fonksiyon.
    OpenGL Context ve GLFW Olay Döngüsü bu fonksiyonda doğar ve ölür.
    """
    try:
        # Import işlemini process içine alıyoruz ki OpenGL context çakışması olmasın
        from core.engine import RenderEngine

        logger.info("GLFW Render Engine süreci başlatılıyor...")
        engine = RenderEngine()

        if not engine.init():
            logger.error("RenderEngine başlatılamadı (GLFW / GL Init Başarısız).")
            return

        # Dışarıdan gelen Scene verisini yükle
        if scene_data is not None:
            engine.scene = scene_data
            if hasattr(engine, 'renderer') and engine.renderer:
                engine.renderer.set_scene(scene_data)

        # Komut Dinleyici (Arka planda Qt'den gelen güncellemeleri kontrol eder)
        def check_queue():
            while not queue.empty():
                try:
                    cmd, payload = queue.get_nowait()
                    if cmd == "UPDATE_SCENE":
                        engine.scene = payload
                        if hasattr(engine, 'renderer') and engine.renderer:
                            engine.renderer.set_scene(payload)
                            engine.renderer.update_geo(payload)
                            engine._focus()
                    elif cmd == "CLOSE":
                        if engine.window:
                            
                            glfw.set_window_should_close(engine.window, True)
                except Exception as e:
                    logger.error(f"Kuyruk komutu işlenirken hata: {e}")

        # Ana döngüye küçük bir hook eklemek gerekebilir ya da run() içinde döndürülebilir
        # engine.run() kendi while döngüsünü çalıştırır.
        engine.run()

    except Exception as e:
        logger.exception(f"RenderEngine sürecinde kritik hata: {e}")
    finally:
        logger.info("GLFW Render Engine süreci sonlandı.")


class ViewportManager:
    """
    PySide6 tarafından çağrılan, GLFW Motorunun yaşam döngüsünü
    yöneten Thread-Safe Yöneticisi Sınıf.
    """

    def __init__(self):
        self._process: Optional[mp.Process] = None
        self._queue: mp.Queue = mp.Queue()

    @property
    def is_running(self) -> bool:
        """Motor penceresinin açık ve çalışır durumda olup olmadığını döndürür."""
        return self._process is not None and self._process.is_alive()

    def launch_viewport(self, scene: Optional[Scene] = None):
        """
        Native GLFW 3D Viewport penceresini ayrı bir süreçte başlatır.
        Pencere zaten açıksa öne getirir / sahneyi günceller.
        """
        if self.is_running:
            logger.warning("Viewport zaten açık. Sahne güncelleniyor...")
            self.update_scene(scene)
            return

        logger.info("3D Viewport süreci oluşturuluyor...")
        
        # Windows/macOS spawn uyumluluğu için
        self._process = mp.Process(
            target=_run_engine_process,
            args=(scene, self._queue),
            daemon=True
        )
        self._process.start()

    def update_scene(self, scene: Scene):
        """
        Çalışmakta olan GLFW motoruna yeni/güncellenmiş Scene verisini fırlatır.
        """
        if self.is_running:
            self._queue.put(("UPDATE_SCENE", scene))
        else:
            logger.warning("Güncelleme gönderilemedi: Viewport kapalı.")

    def close_viewport(self):
        """
        GLFW penceresini güvenli bir şekilde kapatır.
        """
        if self.is_running:
            self._queue.put(("CLOSE", None))
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                logger.warning("Engine süreci zaman aşımına uğradı, zorla sonlandırılıyor.")
                self._process.terminate()
            self._process = None
            logger.info("Viewport başarıyla kapatıldı.")

if __name__ == "__main__":
    viewport_mgr = ViewportManager()