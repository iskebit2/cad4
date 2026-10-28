# logging_config.py
"""
Merkezi log yapılandırması.

Tasarım:
    - KONSOL  : sadece WARNING+ (veya CAD_LOG_CONSOLE_LEVEL ile override)
    - DOSYA   : DEBUG+ (logs/cad.log, rotate 4 MB x 5)

Environment:
    CAD_LOG_LEVEL=DEBUG          # tüm cad.* logger'ları için (root)
    CAD_LOG_CONSOLE_LEVEL=WARNING # konsol handler seviyesi
    CAD_LOG_FILE_LEVEL=DEBUG      # dosya handler seviyesi
    CAD_LOG_DIR=logs             # log dizini
    CAD_LOG_TO_CONSOLE=1         # 0 yaparsanız konsol tamamen kapanır
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ============================================================================
# FILTERS
# ============================================================================
class DuplicateMessageFilter(logging.Filter):
    """Art arda aynı (logger, level, mesaj) üçlüsünü bastırır."""

    def __init__(self, max_tracked: int = 1024):
        super().__init__()
        self._last: dict[tuple, str] = {}
        self._max_tracked = max_tracked

    def filter(self, record: logging.LogRecord) -> bool:
        # Traceback'leri asla bastırma
        if record.exc_info:
            return True

        try:
            message = record.getMessage()
        except Exception:
            return True

        if not message or not message.strip():
            return False

        key = (record.name, record.levelno)
        if self._last.get(key) == message:
            return False

        self._last[key] = message
        if len(self._last) > self._max_tracked:
            for k in list(self._last.keys())[: self._max_tracked // 2]:
                self._last.pop(k, None)
        return True


# ============================================================================
# FORMATTERS
# ============================================================================
class _ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",
        "INFO":     "\033[32m",
        "WARNING":  "\033[33m",
        "ERROR":    "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname_colored = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


# ============================================================================
# LOGGER
# ============================================================================
class CadLogger:
    """Tüm cad.* logger'larının merkezi."""

    _loggers: dict[str, logging.Logger] = {}
    _root_configured: bool = False

    # Modül bazlı seviyeler (dosya handler'ı bunları kullanır).
    # Değer yoksa → NOTSET (root'tan miras)
    MODULE_LEVELS: dict[str, str] = {
        "cad.tools.s2k.loader":       "INFO",
        "cad.tools.s2k_utils":       "INFO",
        "cad.geometry.scenebuilder": "INFO",
        "cad.data.serializer":       "INFO",
        "cad.core.gl_engine":        "INFO",
        "cad.render.axes_renderer":  "INFO",
    }

    ROOT_NAME = "cad"

    # ------------------------------------------------------------------
    @classmethod
    def _env(cls, key: str, default: str) -> str:
        return os.environ.get(key, default).strip()

    @classmethod
    def _console_level(cls) -> int:
        """Konsol için minimum seviye. Varsayılan: WARNING."""
        name = cls._env("CAD_LOG_CONSOLE_LEVEL", "WARNING").upper()
        return getattr(logging, name, logging.WARNING)

    @classmethod
    def _file_level(cls) -> int:
        """Dosya için minimum seviye. Varsayılan: DEBUG."""
        name = cls._env("CAD_LOG_FILE_LEVEL", "DEBUG").upper()
        return getattr(logging, name, logging.DEBUG)

    @classmethod
    def _root_level(cls) -> int:
        """Root logger seviyesi. Varsayılan: DEBUG (handler'lar filtreler)."""
        name = cls._env("CAD_LOG_LEVEL", "DEBUG").upper()
        return getattr(logging, name, logging.DEBUG)

    @classmethod
    def _console_enabled(cls) -> bool:
        return cls._env("CAD_LOG_TO_CONSOLE", "1") not in ("0", "false", "no")

    # ------------------------------------------------------------------
    @classmethod
    def _configure_root_once(cls) -> None:
        if cls._root_configured:
            return
        cls._root_configured = True

        root = logging.getLogger(cls.ROOT_NAME)
        root.setLevel(cls._root_level())
        root.propagate = False

        # Eski handler'ları temizle
        for h in list(root.handlers):
            root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        # ---------------- Console ----------------
        if cls._console_enabled():
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(cls._console_level())
            console.setFormatter(_ColorFormatter(
                fmt="%(asctime)s [%(levelname_colored)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
            console.addFilter(DuplicateMessageFilter())
            root.addHandler(console)

        # ---------------- File ----------------
        try:
            log_dir = Path(cls._env("CAD_LOG_DIR", "logs"))
            log_dir.mkdir(parents=True, exist_ok=True)

            log_path = log_dir / "cad.log"

            # Her yeni süreçte aktif log dosyasını açıkça boşalt.
            with log_path.open("w", encoding="utf-8"):
                pass

            file_h = RotatingFileHandler(
                log_path,
                maxBytes=4_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            file_h.setLevel(cls._file_level())
            file_h.setFormatter(logging.Formatter(
                fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            file_h.addFilter(DuplicateMessageFilter())
            root.addHandler(file_h)

        except Exception as e:
            print(
                f"[CadLogger] Dosya handler kurulamadı: {e}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    @classmethod
    def get(cls, name: str = ROOT_NAME) -> logging.Logger:
        cls._configure_root_once()

        full_name = name if name.startswith(cls.ROOT_NAME) else f"{cls.ROOT_NAME}.{name}"
        if full_name in cls._loggers:
            return cls._loggers[full_name]

        log = logging.getLogger(full_name)

        env_level = os.environ.get("CAD_LOG_LEVEL", "").upper()
        if env_level:
            log.setLevel(getattr(logging, env_level, logging.NOTSET))
        else:
            level_name = cls.MODULE_LEVELS.get(full_name)
            log.setLevel(
                getattr(logging, level_name.upper(), logging.NOTSET)
                if level_name else logging.NOTSET
            )

        log.setup = lambda level="INFO": cls.setup(level)  # type: ignore[attr-defined]
        cls._loggers[full_name] = log
        return log

    @classmethod
    def set_module_level(cls, name: str, level: str) -> None:
        full_name = name if name.startswith(cls.ROOT_NAME) else f"{cls.ROOT_NAME}.{name}"
        logging.getLogger(full_name).setLevel(getattr(logging, level.upper()))
        cls._loggers.setdefault(full_name, logging.getLogger(full_name))

    @classmethod
    def setup(cls, level: str = "INFO") -> None:
        cls._configure_root_once()
        logging.getLogger(cls.ROOT_NAME).setLevel(getattr(logging, level.upper(), logging.INFO))

    @classmethod
    def log_file_path(cls) -> Path | None:
        root = logging.getLogger(cls.ROOT_NAME)
        for h in root.handlers:
            if isinstance(h, RotatingFileHandler):
                return Path(h.baseFilename)
        return None

    @classmethod
    def print_summary(cls) -> None:
        """Aktif yapılandırmayı konsola bas (main'den bir kez)."""
        root = logging.getLogger(cls.ROOT_NAME)
        console_level = cls._console_level()
        file_level = cls._file_level()
        log_path = cls.log_file_path()

        def _name(lvl: int) -> str:
            return logging.getLevelName(lvl)

        print("=" * 64)
        print(" LOG YAPILANDIRMASI")
        print("=" * 64)
        print(f"  Root seviye   : {_name(root.level)}")
        print(f"  Konsol seviye : {_name(console_level)}"
              + ("" if cls._console_enabled() else "  (kapalı)"))
        print(f"  Dosya seviye  : {_name(file_level)}")
        print(f"  Dosya         : {log_path if log_path else '<yok>'}")
        print("-" * 64)
        for mod, lvl in cls.MODULE_LEVELS.items():
            print(f"  {mod:<40} {lvl}")
        print("=" * 64)