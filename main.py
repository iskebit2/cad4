# main.py
"""
Cad4 — Uygulama giriş noktası.

Tüm UI kurulumu app/main_app.py içindedir.
Bu dosya sadece:
  - Kivy log ayarları
  - sys.path düzeltmesi
  - MainApp'i başlatma
sorumluluğunu taşır.
"""

import os

# Kivy loglarını sustur — App import'undan ÖNCE olmalı
# os.environ["KIVY_LOG_LEVEL"] = "error"
# os.environ["KIVY_NO_CONSOLELOG"] = "1"
# os.environ["KIVY_NO_FILELOG"] = "1"
# os.environ["KIVY_NO_ARGS"] = "1"



import sys
from pathlib import Path

# --- PYDROID / TERMUX DİZİN VE HİYERARŞİ DÜZELTİCİ ---
FILE_DIR = Path(__file__).resolve().parent
if str(FILE_DIR) not in sys.path:
    sys.path.insert(0, str(FILE_DIR))

# --- Uygulama ---
from app.main_app import MainApp
from logging_config import CadLogger

CadLogger.setup("INFO")
logger = CadLogger.get(__name__)

import logging
logging.getLogger("OpenGL").setLevel(logging.WARNING)
logging.getLogger("OpenGL.arrays").setLevel(logging.WARNING)
logging.getLogger("OpenGL.GL").setLevel(logging.WARNING)

logger.info("Cad4 başlatılıyor...")


if __name__ == "__main__":
    MainApp().run()