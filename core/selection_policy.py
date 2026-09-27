# core/selection_policy.py
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SelectionMode(Enum):
    REPLACE = 0   # Öncekileri temizle, yenileri ekle (normal tıklama)
    ADD = 1       # Varolanlara ekle (Shift + tıklama)
    TOGGLE = 2    # Varolanlardan çıkar/ekle (Ctrl + tıklama)

class SelectionPolicy:
    """
    Seçim politikasını belirler - TEK KAYNAK
    - Hangi modifier tuşun hangi moda karşılık geldiğini yönetir
    - İleride değiştirmek çok kolay
    """
    
    def __init__(self, input_manager):
        self.input = input_manager
    
    def get_mode(self) -> SelectionMode:
        """Mevcut modifier tuşlara göre seçim modunu belirle"""
        
        if self.input.is_ctrl_pressed():
            # Ctrl = Toggle (ekle/çıkar)
            return SelectionMode.TOGGLE
        
        elif self.input.is_shift_pressed():
            # Shift = Add (varolanlara ekle)
            return SelectionMode.ADD
        
        else:
            # Hiçbiri = Replace (tekli seçim)
            return SelectionMode.REPLACE
    
    def should_clear_on_empty_click(self) -> bool:
        """Boşluğa tıklandığında seçim temizlensin mi?"""
        # Ctrl yoksa temizle, Ctrl varsa temizleme (toggle için)
        return not self.input.is_ctrl_pressed()
    
    def get_marquee_mode(self) -> SelectionMode:
        """Marquee seçimi için mod (Shift = Toggle)"""
        if self.input.is_shift_pressed():
            return SelectionMode.TOGGLE
        else:
            return SelectionMode.REPLACE