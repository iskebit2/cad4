# logging_config.py

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Mapping



# =============================================================================
# AYARLAR
# =============================================================================

APP_NAME = "cad4"

LOG_FILE = Path("cad4.log")

OFF = 100


DEFAULT_LEVELS: dict[str, str] = {
    "cad4": "INFO",

    "kivy": "WARNING",
    "PIL": "WARNING",
    "matplotlib": "WARNING",
}


CONSOLE_FORMAT = (
    "[%(levelname)s] "
    "%(name)s: "
    "%(message)s"
)

FILE_FORMAT = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)s | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# =============================================================================
# LOGGER
# =============================================================================

class CadLogger:
    """
    CAD4 merkezi logging yöneticisi.

    Özellikler
    ----------
    - Modül bazında log seviyesi
    - Runtime'da seviye değiştirme
    - Modülü tamamen kapatma
    - Console / file logging
    - debug_changed()
    - Logger cache
    - Mevcut Python logging API'si ile uyumlu kullanım


    Örnek
    -----
        logger = CadLogger.get(__name__)

        logger.debug("debug mesajı")
        logger.info("model yüklendi")
        logger.warning("...")
        logger.error("...")

        logger.debug_changed(
            "camera.position",
            camera.position,
        )


    main.py
    -------
        CadLogger.setup("DEBUG")

        CadLogger.set_level(
            "cad4.renderer",
            "DEBUG",
        )

        CadLogger.set_level(
            "cad4.geometry",
            "WARNING",
        )

        CadLogger.disable(
            "cad4.wind",
        )
    """

    _configured = False

    _loggers: dict[str, "CadLogger"] = {}

    _levels: dict[str, str] = {}

    _last_values: dict[str, str] = {}

    _MISSING = object()

    # -------------------------------------------------------------------------
    # INIT
    # -------------------------------------------------------------------------

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

    # -------------------------------------------------------------------------
    # SETUP
    # -------------------------------------------------------------------------

    @classmethod
    def setup(
        cls,
        level: str = "INFO",
        *,
        module_levels: Mapping[str, str] | None = None,
        log_file: str | Path | None = None,
    ) -> None:
        """
        Merkezi logging sistemini kurar.

        Örnek:

            CadLogger.setup("DEBUG")

        veya:

            CadLogger.setup(
                "INFO",
                module_levels={
                    "cad4.camera": "DEBUG",
                    "cad4.renderer": "DEBUG",
                    "cad4.geometry": "WARNING",
                },
            )
        """

        global LOG_FILE

        if log_file is not None:
            LOG_FILE = Path(log_file)

        LOG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        levels = dict(DEFAULT_LEVELS)

        levels[APP_NAME] = level.upper()

        if module_levels:
            levels.update(
                {
                    name: cls._normalize_level(value)
                    for name, value
                    in module_levels.items()
                }
            )

        handlers = {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "console",
                "stream": "ext://sys.stdout",
            },

            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "file",
                "filename": str(LOG_FILE),
                "encoding": "utf-8",
            },
        }

        logger_config = {}

        for name, logger_level in levels.items():
            logger_config[name] = {
                "level": logger_level,
                "handlers": [
                    "console",
                    "file",
                ],
                "propagate": False,
            }

        config = {
            "version": 1,

            "disable_existing_loggers": False,

            "formatters": {
                "console": {
                    "format": CONSOLE_FORMAT,
                    "datefmt": DATE_FORMAT,
                },

                "file": {
                    "format": FILE_FORMAT,
                    "datefmt": DATE_FORMAT,
                },
            },

            "handlers": handlers,

            "loggers": logger_config,

            "root": {
                "level": "WARNING",
                "handlers": ["console"],
            },
        }

        logging.config.dictConfig(config)

        cls._levels = levels
        cls._configured = True


    
    # -------------------------------------------------------------------------
    # GET LOGGER
    # -------------------------------------------------------------------------

    @classmethod
    def get(cls, name: str | None = None) -> "CadLogger":
        """
        Modül logger'ı döndürür.

        Kullanım:

            logger = CadLogger.get(__name__)
        """

        name = name or APP_NAME

        if name not in cls._loggers:
            cls._loggers[name] = cls(name)

        return cls._loggers[name]

    # -------------------------------------------------------------------------
    # LEVEL
    # -------------------------------------------------------------------------

    @classmethod
    def set_level(
        cls,
        logger_name: str,
        level: str,
    ) -> None:
        """
        Runtime'da logger seviyesini değiştirir.

        Örnek:

            CadLogger.set_level(
                "cad4.camera",
                "DEBUG",
            )
        """

        level = cls._normalize_level(level)

        logger = logging.getLogger(logger_name)

        logger.setLevel(level)

        cls._levels[logger_name] = level

    # -------------------------------------------------------------------------
    # ENABLE / DISABLE
    # -------------------------------------------------------------------------

    @classmethod
    def enable(
        cls,
        logger_name: str,
        level: str = "DEBUG",
    ) -> None:
        """
        Logger'ı etkinleştirir.
        """

        cls.set_level(
            logger_name,
            level,
        )

    @classmethod
    def disable(
        cls,
        logger_name: str,
    ) -> None:
        """
        Logger'ı tamamen kapatır.
        """

        logger = logging.getLogger(logger_name)

        logger.setLevel(OFF)

        cls._levels[logger_name] = "OFF"

    # -------------------------------------------------------------------------
    # RESET
    # -------------------------------------------------------------------------

    @classmethod
    def reset_level(
        cls,
        logger_name: str,
    ) -> None:
        """
        Logger'ı cad4 genel seviyesine döndürür.
        """

        root_level = cls._levels.get(
            APP_NAME,
            "INFO",
        )

        cls.set_level(
            logger_name,
            root_level,
        )

    # -------------------------------------------------------------------------
    # LEVEL QUERY
    # -------------------------------------------------------------------------

    @classmethod
    def get_level(
        cls,
        logger_name: str,
    ) -> str:
        """
        Logger'ın mevcut seviyesini döndürür.
        """

        logger = logging.getLogger(logger_name)

        return logging.getLevelName(
            logger.level
        )

    # -------------------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------------------

    def debug(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.debug(
            msg,
            *args,
            **kwargs,
        )

    def info(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.info(
            msg,
            *args,
            **kwargs,
        )

    def warning(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.warning(
            msg,
            *args,
            **kwargs,
        )

    def error(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.error(
            msg,
            *args,
            **kwargs,
        )

    def critical(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.critical(
            msg,
            *args,
            **kwargs,
        )

    def exception(
        self,
        msg,
        *args,
        **kwargs,
    ):
        self.logger.exception(
            msg,
            *args,
            **kwargs,
        )

    # -------------------------------------------------------------------------
    # DEBUG CHANGED
    # -------------------------------------------------------------------------

    def debug_changed(
        self,
        key: str,
        value,
    ) -> None:
        """
        Değer değiştiğinde DEBUG mesajı üretir.

        Aynı değer tekrar tekrar yazılmaz.

        Örnek:

            logger.debug_changed(
                "camera.position",
                camera.position,
            )
        """

        state_key = (
            f"{self.name}:{key}"
        )

        current = repr(value)

        previous = self._last_values.get(
            state_key,
            self._MISSING,
        )

        if (
            previous is self._MISSING
            or previous != current
        ):
            self.logger.debug(
                "%s = %s",
                key,
                value,
            )

            self._last_values[state_key] = current

    # -------------------------------------------------------------------------
    # DEBUG ONCE
    # -------------------------------------------------------------------------

    def debug_once(
        self,
        key: str,
        msg,
        *args,
    ) -> None:
        """
        Verilen mesajı yalnızca bir kez yazar.

        Örnek:

            logger.debug_once(
                "shader-init",
                "Shader oluşturuldu",
            )
        """

        state_key = (
            f"{self.name}:once:{key}"
        )

        if state_key in self._last_values:
            return

        self.logger.debug(
            msg,
            *args,
        )

        self._last_values[state_key] = "DONE"

    # -------------------------------------------------------------------------
    # RESET DEBUG STATE
    # -------------------------------------------------------------------------

    @classmethod
    def clear_debug_state(cls) -> None:
        """
        debug_changed / debug_once hafızasını temizler.
        """

        cls._last_values.clear()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_level(level: str) -> str:
        level = level.upper()

        if level == "OFF":
            return "OFF"

        if level not in {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }:
            raise ValueError(
                f"Geçersiz log seviyesi: {level}"
            )

        return level
