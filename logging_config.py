"""
merkezi logging yapılandırması.

Kullanım:

    from logging_config import setup_logging

    setup_logging()

Geliştirme sırasında:

    setup_logging("DEBUG")

Modül bazında logger:

    import logging
    logger = logging.getLogger(__name__)

Örneğin:
    cad4.wind.engine
    cad4.wind.analyzer
    cad4.snow
    cad4.earthquake
    cad4.ui
"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Mapping


# =============================================================================
# AYARLAR
# =============================================================================

APP_NAME = "cad4"

# Log dosyasının yeri.
# İstersen bunu daha sonra Android'e özel hale getirebiliriz.
LOG_FILE = Path("cad4.log")


# Uygulama logger'larının varsayılan seviyeleri.
#
# Daha ayrıntılı bilgi istediğin modülü DEBUG yapabilirsin.
MODULE_LEVELS: dict[str, str] = {
    "cad4": "INFO",

    # Örnek:
    # "cad4.wind": "DEBUG",
    # "cad4.snow": "DEBUG",
    # "cad4.earthquake": "WARNING",
    # "cad4.ui": "INFO",

    # Üçüncü parti kütüphaneler
    "kivy": "WARNING",
    "PIL": "WARNING",
    "matplotlib": "WARNING",
}


# =============================================================================
# FORMATLAR
# =============================================================================

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
# YARDIMCI
# =============================================================================

def _build_logger_levels(
    module_levels: Mapping[str, str],
) -> dict[str, dict[str, str]]:
    """
    dictConfig için logger tanımlarını oluşturur.
    """

    loggers = {}

    for name, level in module_levels.items():
        loggers[name] = {
            "level": level,
            "handlers": ["console", "file"],
            "propagate": False,
        }

    return loggers


# =============================================================================
# CONFIG
# =============================================================================

def _build_config(
    default_level: str = "INFO",
    module_levels: Mapping[str, str] | None = None,
) -> dict:
    """
    logging.config.dictConfig() için configuration üretir.
    """

    levels = dict(module_levels or MODULE_LEVELS)

    # cad4 için genel seviye
    levels.setdefault(APP_NAME, default_level)

    return {
        "version": 1,

        # Daha önce kurulmuş handler'ları temizle.
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

        "handlers": {
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
        },

        "loggers": _build_logger_levels(levels),

        # Root logger.
        #
        # Tanımlanmamış üçüncü parti logger'lar buraya düşebilir.
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }


# =============================================================================
# PUBLIC API
# =============================================================================

def setup_logging(
    level: str = "INFO",
    *,
    module_levels: Mapping[str, str] | None = None,
    log_file: str | Path | None = None,
) -> None:
    """
    Uygulamanın merkezi logging sistemini kurar.

    Parameters
    ----------
    level:
        cad4 için varsayılan seviye.
        Örnek: "DEBUG", "INFO", "WARNING", "ERROR"

    module_levels:
        Modül bazında seviye değiştirmek için sözlük.

    log_file:
        Log dosyasının yolunu değiştirmek için kullanılır.
    """

    global LOG_FILE

    if log_file is not None:
        LOG_FILE = Path(log_file)

    # Log klasörü varsa oluştur.
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    config = _build_config(
        default_level=level,
        module_levels=module_levels,
    )

    logging.config.dictConfig(config)


# =============================================================================
# MODÜL SEVİYESİNİ SONRADAN DEĞİŞTİRME
# =============================================================================

def set_level(logger_name: str, level: str) -> None:
    """
    Çalışan uygulamada belirli bir logger'ın seviyesini değiştirir.

    Örnek:

        set_level("cad4.wind", "DEBUG")
        set_level("cad4.wind", "INFO")
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(level.upper())


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Uygulama logger'ı döndürür.

    Örnek:

        logger = get_logger(__name__)
    """

    return logging.getLogger(name or APP_NAME)
