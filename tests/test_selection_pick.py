# tests/test_selection_pick.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from core.selection_manager import SelectionManager
from core.selection_policy import SelectionMode

class DummyElement:
    """Test için hafif siklet sahte CAD elemanı."""
    def __init__(self, unique_id: int):
        self.unique_id = unique_id
        self.is_selected = False

def test_gpu_pick_to_selection_flow():
    """GPU pick sonucu dönen ID'nin elemente dönüşmesini ve SelectionManager'ı tetiklemesini test et."""
    # Renderer ve math_model bileşenlerini mock'la
    mock_renderer = MagicMock()
    mock_math_model = MagicMock()
    
    # Sahneye sahte bir eleman yerleştir (ID: 42)
    elem = DummyElement(42)
    mock_math_model.all_elements = {42: elem}
    mock_renderer.math_model = mock_math_model
    mock_renderer.scene = None

    sel_mgr = SelectionManager(mock_renderer)

    # 1. Adım: GPU'dan gelen ID ile element bulunabiliyor mu? (PickPass mantığı)
    found_element = sel_mgr.find_element_by_id(42)
    assert found_element is elem, "GPU pick ID'si yanlış elementi eşledi!"

    # 2. Adım: Bulunan element SelectionManager ile seçilebiliyor mu?
    sel_mgr.select(found_element, additive=False)
    assert elem.is_selected is True, "Element seçili duruma geçmedi."
    assert 42 in sel_mgr.selected, "ID seçili kümesine eklenmedi."

    # 3. Adım: Toggle / Çoklu seçim senaryosu
    elem2 = DummyElement(43)
    mock_math_model.all_elements[43] = elem2
    
    # Shift/Ctrl (additive) seçim testi
    sel_mgr.select(elem2, additive=True)
    assert len(sel_mgr.selected) == 2
    assert elem.is_selected and elem2.is_selected

    # 4. Adım: Temizlik (Clear)
    sel_mgr.clear()
    assert len(sel_mgr.selected) == 0
    assert elem.is_selected is False
    assert elem2.is_selected is False