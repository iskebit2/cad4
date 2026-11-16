# logging_config.py
from __future__ import annotations

import logging
import os
import sys
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock
from time import monotonic


# ============================================================================
# FILTERS
# ============================================================================

class DuplicateMessageFilter(logging.Filter):
    """Aynı logger/seviye/mesaj birleşimini zaman penceresi içinde bastırır.

    Filtre her handler için ayrı örneklenmelidir. Böylece konsolda bastırılan
    bir kayıt dosya handler'ında da bağımsız olarak değerlendirilebilir.
    """

    def __init__(
        self,
        window_seconds: float = 1.0,
        max_tracked: int = 2048,
    ) -> None:
        super().__init__()
        self._window = max(0.0, float(window_seconds))
        self._max_tracked = max(1, int(max_tracked))
        self._recent: OrderedDict[tuple[str, int, str], float] = OrderedDict()
        self._lock = RLock()

    def filter(self, record: logging.LogRecord) -> bool:
        # Exception kayıtlarını bastırma: traceback'ler teşhis açısından önemli.
        if record.exc_info:
            return True

        # Mesajı kilit dışında oluştur; formatlama maliyetini lock süresine
        # dahil etme. getMessage() başarısız olursa kaydı kaybetme.
        try:
            message = record.getMessage()
        except Exception:
            return True

        if not message or not message.strip() or self._window <= 0:
            return bool(message and message.strip())

        now = monotonic()
        key = (record.name, record.levelno, message)

        with self._lock:
            # OrderedDict son görülme zamanına göre sıralı tutulur.
            # Süresi dolmuş eski kayıtları baştan temizlemek yeterlidir.
            while self._recent:
                oldest_key, oldest_time = next(iter(self._recent.items()))
                if now - oldest_time < self._window:
                    break
                self._recent.pop(oldest_key, None)

            previous_time = self._recent.get(key)
            if previous_time is not None:
                self._recent[key] = now
                self._recent.move_to_end(key)
                return False

            self._recent[key] = now

            while len(self._recent) > self._max_tracked:
                self._recent.popitem(last=False)

        return True


# ============================================================================
# FORMATTERS
# ============================================================================

class _ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname_colored = (
            f"{color}{record.levelname:<8}{self.RESET}"
        )
        return super().format(record)


# ============================================================================
# LOGGER
# ============================================================================

class CadLogger:
    """Tüm cad.* logger'larının merkezi yapılandırma noktası."""

    _loggers: dict[str, logging.Logger] = {}
    _root_configured = False
    _config_lock = RLock()

    MODULE_LEVELS: dict[str, str] = {
        "cad.core.pickpass": "WARNING",
        "cad.render.load_renderer": "INFO",
        "cad.render.area_load_renderer": "INFO",
        "cad.render.scenerenderer": "INFO",
        "cad.render.snapsquare": "WARNING",
        "cad.render.presentationrenderer": "INFO",
        "cad.ui.plane_manager_panel": "WARNING",
        "cad.app.cad_app": "INFO",
        "cad.core.plane_draw_manager": "WARNING",
        "cad.core.camera": "WARNING",
        "cad.core.input_manager": "WARNING",
        "cad.core.gl_engine": "INFO",
        "cad.plane.plane_creation_tool": "WARNING",
        "cad.tools.gridsystem": "WARNING",
        "cad.ui.ui_host": "INFO",
        "cad.tools.s2k.loader": "INFO",
    }

    ROOT_NAME = "cad"

    @classmethod
    def _env(cls, key: str, default: str) -> str:
        return os.environ.get(key, default).strip()

    @staticmethod
    def _resolve_level(name: str, default: int) -> int:
        value = getattr(logging, name.upper(), None)
        return value if isinstance(value, int) else default

    @classmethod
    def _console_level(cls) -> int:
        return cls._resolve_level(
            cls._env("CAD_LOG_CONSOLE_LEVEL", "WARNING"),
            logging.INFO,
        )

    @classmethod
    def _file_level(cls) -> int:
        return cls._resolve_level(
            cls._env("CAD_LOG_FILE_LEVEL", "INFO"),
            logging.INFO,
        )

    @classmethod
    def _root_level(cls) -> int:
        return cls._resolve_level(
            cls._env("CAD_LOG_LEVEL", "DEBUG"),
            logging.DEBUG,
        )

    @classmethod
    def _console_enabled(cls) -> bool:
        return cls._env("CAD_LOG_TO_CONSOLE", "1").lower() not in {
            "0", "false", "no", "off",
        }

    @classmethod
    def _configure_root_once(cls) -> None:
        if cls._root_configured:
            return

        with cls._config_lock:
            if cls._root_configured:
                return

            root = logging.getLogger(cls.ROOT_NAME)
            root.setLevel(cls._root_level())
            root.propagate = False

            # Önceki yapılandırmadan kalmış handler'ları temizle.
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

            if cls._console_enabled():
                console = logging.StreamHandler(sys.stdout)
                console.setLevel(cls._console_level())
                console.setFormatter(_ColorFormatter(
                    fmt=(
                        "%(asctime)s [%(levelname_colored)s] "
                        "%(name)s: %(message)s"
                    ),
                    datefmt="%H:%M:%S",
                ))
                console.addFilter(DuplicateMessageFilter())
                root.addHandler(console)

            try:
                log_dir = Path(cls._env("CAD_LOG_DIR", "logs"))
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / "cad.log"

                # Her yeni süreçte aktif dosyayı sıfırla; yedekler korunur.
                log_path.write_text("", encoding="utf-8")

                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=4_000_000,
                    backupCount=5,
                    encoding="utf-8",
                )
                file_handler.setLevel(cls._file_level())
                file_handler.setFormatter(logging.Formatter(
                    fmt="%(asctime)s [%(levelname)-8s] "
                        "%(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                ))
                file_handler.addFilter(DuplicateMessageFilter())
                root.addHandler(file_handler)

            except Exception as exc:
                print(
                    f"[CadLogger] Dosya handler kurulamadı: {exc}",
                    file=sys.stderr,
                )

            # Dosya handler'ı kurulmasa da konsol yapılandırması tamamlanmıştır.
            cls._root_configured = True

    @classmethod
    def _full_name(cls, name: str) -> str:
        if name == cls.ROOT_NAME or name.startswith(cls.ROOT_NAME + "."):
            return name
        return f"{cls.ROOT_NAME}.{name}"

    @classmethod
    def get(cls, name: str = ROOT_NAME) -> logging.Logger:
        cls._configure_root_once()
        full_name = cls._full_name(name)

        with cls._config_lock:
            cached = cls._loggers.get(full_name)
            if cached is not None:
                return cached

            log = logging.getLogger(full_name)

            env_level = cls._env("CAD_LOG_LEVEL", "")
            if env_level:
                log.setLevel(cls._resolve_level(env_level, logging.NOTSET))
            else:
                module_level = cls.MODULE_LEVELS.get(full_name)
                log.setLevel(
                    cls._resolve_level(module_level, logging.NOTSET)
                    if module_level else logging.NOTSET
                )

            # Eski kullanım biçimiyle uyumluluk.
            log.setup = lambda level="INFO": cls.setup(level)  # type: ignore[attr-defined]

            cls._loggers[full_name] = log
            return log

    @classmethod
    def set_module_level(cls, name: str, level: str) -> None:
        full_name = cls._full_name(name)
        numeric_level = cls._resolve_level(level, -1)
        if numeric_level < 0:
            raise ValueError(f"Geçersiz log seviyesi: {level}")

        with cls._config_lock:
            log = logging.getLogger(full_name)
            log.setLevel(numeric_level)
            cls._loggers[full_name] = log

    @classmethod
    def setup(cls, level: str = "INFO") -> None:
        numeric_level = cls._resolve_level(level, -1)
        if numeric_level < 0:
            raise ValueError(f"Geçersiz root log seviyesi: {level}")

        cls._configure_root_once()
        logging.getLogger(cls.ROOT_NAME).setLevel(numeric_level)

    @classmethod
    def log_file_path(cls) -> Path | None:
        root = logging.getLogger(cls.ROOT_NAME)
        for handler in root.handlers:
            if isinstance(handler, RotatingFileHandler):
                return Path(handler.baseFilename)
        return None

    @classmethod
    def print_summary(cls) -> None:
        """Aktif yapılandırmayı konsola bas."""
        cls._configure_root_once()

        root = logging.getLogger(cls.ROOT_NAME)
        log_path = cls.log_file_path()

        print("=" * 64)
        print(" LOG YAPILANDIRMASI")
        print("=" * 64)
        print(f"  Root seviye   : {logging.getLevelName(root.level)}")
        print(
            f"  Konsol seviye : {logging.getLevelName(cls._console_level())}"
            + ("" if cls._console_enabled() else "  (kapalı)")
        )
        print(f"  Dosya seviye  : {logging.getLevelName(cls._file_level())}")
        print(f"  Dosya         : {log_path if log_path else '<yok>'}")
        print("-" * 64)
        for module, level in cls.MODULE_LEVELS.items():
            print(f"  {module:<40} {level}")
        print("=" * 64)
