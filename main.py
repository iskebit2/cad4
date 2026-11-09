# main.py
from __future__ import annotations

import sys
import time

from OpenGL.GL import GL_COLOR_BUFFER_BIT, glClear, glClearColor
import glfw

from logging_config import CadLogger

logger = CadLogger.get("cad.main")


def _bootstrap() -> None:
    CadLogger._configure_root_once()
    CadLogger.print_summary()
    logger.debug("=" * 64)
    logger.debug("CAD4 başlatılıyor")
    logger.debug("Python   : %s", sys.version.split()[0])
    logger.debug("Log dos. : %s", CadLogger.log_file_path())
    logger.debug("=" * 64)


def _install_excepthook() -> None:
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Yakalanmamış exception:",
                        exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _hook


def main() -> int:
    _bootstrap()
    _install_excepthook()

    exit_code = 0
    window = None
    app = None

    try:
        t0 = time.time()

        from app.cad_window import CadWindow
        window = CadWindow(width=1280, height=800, title="CAD4")
        window.create()
        glClearColor(0.08, 0.10, 0.16, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        glfw.swap_buffers(window.window)
        logger.debug("[Boot] CadWindow: %.2fs", time.time() - t0)

        t1 = time.time()
        from app.cad_app import CadApp
        app = CadApp(window)
        logger.debug("[Boot] CadApp: %.2fs", time.time() - t1)

        t2 = time.time()
        logger.debug("[Boot] Ana döngü başlıyor")
        window.run(app.frame, target_fps=60)
        logger.debug("[Boot] Ana döngü bitti: %.2fs", time.time() - t2)

    except KeyboardInterrupt:
        logger.debug("Kullanıcı durdurdu (Ctrl+C)")
        exit_code = 130
    except Exception:
        logger.exception("Uygulama beklenmedik şekilde sonlandı")
        exit_code = 1
    finally:
        if app is not None:
            try:
                app.shutdown()
            except Exception:
                logger.exception("CadApp.shutdown() hatası")
                exit_code = exit_code or 1
        if window is not None:
            try:
                window.shutdown()
            except Exception:
                logger.exception("CadWindow.shutdown() hatası")
                exit_code = exit_code or 1
        logger.debug("Çıkış kodu: %s", exit_code)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())