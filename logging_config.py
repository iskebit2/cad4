# logging_config.py
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

class _ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[41m",   # red bg
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.levelname_colored = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


class CadLogger:
    _loggers = {}
    _initialized = False
    _root_configured = False

    @classmethod
    def _configure_root_once(cls):
        if cls._root_configured:
            return
        cls._root_configured = True

        root = logging.getLogger("cad")
        root.setLevel(logging.DEBUG)
        root.propagate = False   # kendi handler'larımızı kullanacağız

        # Eski handler'ları temizle (çift log olmasın)
        for h in list(root.handlers):
            root.removeHandler(h)

        # 1) Terminal handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console.setFormatter(_ColorFormatter(
            fmt="%(asctime)s [%(levelname_colored)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(console)

        # 2) Dosya handler (opsiyonel ama faydalı)
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            file_h = RotatingFileHandler(
                log_dir / "cad.log",
                maxBytes=2_000_000, backupCount=3, encoding="utf-8",
            )
            file_h.setLevel(logging.DEBUG)
            file_h.setFormatter(logging.Formatter(
                fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            root.addHandler(file_h)
        except Exception as e:
            print(f"[CadLogger] Dosya handler kurulamadı: {e}")

    @classmethod
    def get(cls, name: str = "cad") -> logging.Logger:
        cls._configure_root_once()

        full_name = name if name.startswith("cad") else f"cad.{name}"
        if full_name not in cls._loggers:
            log = logging.getLogger(full_name)

            # ⬅️ Instance üzerinden setup() çağrılabilsin diye kısayol bağla
            # (Kullanıcı yanlışlıkla logger.setup("INFO") derse patlamasın)
            log.setup = lambda level="INFO": cls.setup(level)

            cls._loggers[full_name] = log
        return cls._loggers[full_name]

    @classmethod
    def setup(cls, level: str = "INFO"):
        """Geriye dönük uyumluluk için. Aslında root zaten DEBUG'da."""
        cls._configure_root_once()
        lvl = getattr(logging, level.upper(), logging.INFO)
        # Sadece konsol seviyesini değiştir
        for h in logging.getLogger("cad").handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
                h.setLevel(lvl)
        logging.getLogger("cad").setLevel(logging.DEBUG)