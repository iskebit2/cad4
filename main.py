# main.py
from __future__ import annotations

import sys
import threading
import traceback

from logging_config import CadLogger

logger = CadLogger.get("main")


def _bootstrap() -> None:
    CadLogger._configure_root_once()
    CadLogger.print_summary()

    logger.info("=" * 64)
    logger.info("CAD4 başlatılıyor")
    logger.info("Python   : %s", sys.version.split()[0])
    logger.info("Log dos. : %s", CadLogger.log_file_path())
    logger.info("=" * 64)


def _install_excepthook() -> None:
    def _main_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        logger.critical(
            "Yakalanmamış exception:",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        if issubclass(args.exc_type, KeyboardInterrupt):
            threading.__excepthook__(args)
            return

        logger.critical(
            "Thread içinde yakalanmamış exception "
            "(thread=%s):",
            args.thread.name if args.thread else "<unknown>",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        threading.__excepthook__(args)

    sys.excepthook = _main_hook
    threading.excepthook = _thread_hook


def main():
    try:
        from app.cad_window import CadWindow
        from app.cad_app import CadApp
        from ui.ui_host import UIHost

        window = CadWindow()
        window.create()
        app = CadApp(window)
        ui_host = UIHost(app)
        app.attach_ui(ui_host)
        window.run(ui_host.frame)
    except Exception as e:
        err_str = f"Kritik Başlangıç Hatası:\n{traceback.format_exc()}"
        print(err_str, file=sys.stderr)
        
        # Log dosyası boş kalmasın diye acil log yazma
        try:
            with open("cad_fatal.log", "w", encoding="utf-8") as f:
                f.write(err_str)
        except Exception:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
