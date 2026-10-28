# main.py
"""
CAD4 giriş noktası.

Konsol: sadece WARNING+ (varsayılan)
Dosya : DEBUG+  (logs/cad.log)
"""


from __future__ import annotations

import os
import sys

from logging_config import CadLogger

logger = CadLogger.get("cad.main")



def _bootstrap_logging() -> None:
    """Logger'ı başlat ve özet yazdır."""
    CadLogger._configure_root_once()
    CadLogger.print_summary()

    logger.info("=" * 64)
    logger.info("CAD4 başlatılıyor")
    logger.info("Python   : %s", sys.version.split()[0])
    logger.info("Dizin    : %s", os.getcwd())
    logger.info("Log dos. : %s", CadLogger.log_file_path())
    logger.info("=" * 64)


def _install_excepthook() -> None:
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Yakalanmamış exception:",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def main() -> int:
    _bootstrap_logging()
    _install_excepthook()

    window = None
    app = None
    exit_code = 0

    try:
        logger.info("[1/3] CadWindow oluşturuluyor...")
        from app import CadWindow

        window = CadWindow(width=1280, height=800, title="CAD4")
        window.create()

        logger.info("[2/3] CadApp oluşturuluyor...")
        from app import CadApp

        app = CadApp(window)
        
        logger.info("[3/3] Ana döngü başlıyor")
        window.run(app.frame, target_fps=60)
        
        logger.info("[3/3] Ana döngü bitti")


    except KeyboardInterrupt:
        logger.info("Kullanıcı durdurdu (Ctrl+C)")
        exit_code = 130
    except Exception:
        logger.error("Uygulama beklenmedik şekilde sonlandı:", exc_info=True)
        exit_code = 1
    finally:
        if app is not None:
            try:
                app.shutdown()
            except Exception:
                logger.error("CadApp.shutdown() hatası:", exc_info=True)
                exit_code = exit_code or 1
        if window is not None:
            try:
                window.shutdown()
            except Exception:
                logger.error("CadWindow.shutdown() hatası:", exc_info=True)
                exit_code = exit_code or 1
        logger.info("Çıkış kodu: %s", exit_code)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())