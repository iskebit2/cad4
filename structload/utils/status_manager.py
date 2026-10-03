# utils/status_manager.py
"""
Global durum çubuğu ve log yöneticisi.
Tüm paneller bu singleton üzerinden mesaj gönderebilir.
"""

from kivy.event import EventDispatcher
from kivy.properties import StringProperty, ListProperty, NumericProperty
from datetime import datetime
from typing import Literal


class StatusManager(EventDispatcher):
    """Global durum ve log yöneticisi."""

    message = StringProperty("Hazır.")
    level = StringProperty("info")  # info, success, warning, error, debug
    log_entries = ListProperty([])  # [(timestamp, level, message), ...]
    error_count = NumericProperty(0)
    warning_count = NumericProperty(0)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set(self, message: str, level: str = "info", log: bool = True):
        """Durum mesajını günceller ve isteğe bağlı loglar."""
        self.message = message
        self.level = level
        if log:
            self.add_log(message, level)

    def add_log(self, message: str, level: str = "info"):
        """Log kaydı ekler."""
        ts = datetime.now().strftime("%H:%M:%S")
        entry = (ts, level, message)
        self.log_entries = self.log_entries + [entry]
        # Son 500 kayıt
        if len(self.log_entries) > 500:
            self.log_entries = self.log_entries[-500:]

        if level == "error":
            self.error_count += 1
        elif level == "warning":
            self.warning_count += 1

    def info(self, msg):    self.set(msg, "info")
    def success(self, msg): self.set(msg, "success")
    def warning(self, msg): self.set(msg, "warning")
    def error(self, msg):   self.set(msg, "error")
    def debug(self, msg):   self.set(msg, "debug", log=False)

    def clear_log(self):
        self.log_entries = []
        self.error_count = 0
        self.warning_count = 0


# Singleton instance
status = StatusManager()