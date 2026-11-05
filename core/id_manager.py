# core/id_manager.py

from __future__ import annotations

class IDManager:
    """Tüm CAD sahne elemanları (Node, Frame, Area, Link, Polygon vb.) 
    için global ve merkezi ID üretim yöneticisi.
    """
    _instance = None
    _counter = 1

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IDManager, cls).__new__(cls)
            cls._counter = 1
        return cls._instance

    @classmethod
    def generate_id(cls) -> int:
        """Yeni ve benzersiz bir global unique_id üretir."""
        current_id = cls._counter
        cls._counter += 1
        return current_id

    @classmethod
    def sync_counter(cls, loaded_id: int):
        """Proje dosyası (S2K / JSON) yüklenirken, dışarıdan gelen ID'ye 
        göre sayacı günceller (Çakışmaları önler).
        """
        if loaded_id >= cls._counter:
            cls._counter = loaded_id + 1

    @classmethod
    def reset(cls, start_value: int = 1):
        """Sayacı sıfırlar veya belirli bir değere ayarlar."""
        cls._counter = max(1, start_value)