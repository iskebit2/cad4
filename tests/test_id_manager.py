# tests/test_id_manager.py
from __future__ import annotations
import pytest
from core.id_manager import IDManager

@pytest.fixture(autouse=True)
def reset_id_manager():
    """Her test öncesi IDManager singleton state'ini sıfırla."""
    IDManager.reset(1)
    yield
    IDManager.reset(1)

def test_singleton_behavior():
    """IDManager'ın Singleton yapıda olduğunu doğrula."""
    m1 = IDManager()
    m2 = IDManager()
    assert m1 is m2

def test_generate_id_sequence():
    """ID üretim sırasının 1'den başlayıp ardışık arttığını test et."""
    assert IDManager.generate_id() == 1
    assert IDManager.generate_id() == 2
    assert IDManager.generate_id() == 3

def test_sync_counter():
    """Dışarıdan (dosyadan) yüklenen ID'ye göre sayacın güncellendiğini test et."""
    assert IDManager.generate_id() == 1  # 1 üretildi, counter = 2 oldu
    
    # Yüklenen ID mevcut sayaçtan büyükse sayaç güncellenmeli (loaded_id + 1)
    IDManager.sync_counter(10)
    assert IDManager.generate_id() == 11

    # Yüklenen ID mevcut sayaçtan küçük veya eşitse sayaç geriye gitmemeli
    IDManager.sync_counter(5)
    assert IDManager.generate_id() == 12

def test_reset_counter():
    """Sayacın özel bir başlangıç değerine sıfırlanabildiğini test et."""
    IDManager.generate_id() # 1
    IDManager.generate_id() # 2
    
    IDManager.reset(50)
    assert IDManager.generate_id() == 50
    assert IDManager.generate_id() == 51

    # Negatif veya 1'den küçük değer verilirse 1'e sabitlemeli
    IDManager.reset(-10)
    assert IDManager.generate_id() == 1