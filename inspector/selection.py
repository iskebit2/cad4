"""Seçim modeli — Inspector'ın gördüğü element kümesi."""

from typing import Any, Dict, List, Optional


class SelectionModel:

    def __init__(self):
        self.elements: List[Any] = []
        self.values: Dict[str, Any] = {}     # current edit buffer
        self.original: Dict[str, Any] = {}   # apply öncesi snapshot

    # ------------------------------------------------------------------
    def set_single(self, element, values: Dict[str, Any]):
        self._deselect_all()                    # önce eski seçimi temizle
        self.elements = [element]
        element.is_selected = True              # ← YENİ
        self.values = values
        self.original = _deep_copy(values)

    def set_multi(self, elements, common_values: Dict[str, Any]):
        self._deselect_all()
        self.elements = list(elements)
        for e in self.elements:
            e.is_selected = True                # ← YENİ
        self.values = common_values
        self.original = _deep_copy(common_values)

    def clear(self):
        self._deselect_all()
        self.elements = []
        self.values = {}
        self.original = {}

    def _deselect_all(self):
        for el in self.elements:
            try:
                el.is_selected = False
            except Exception:
                pass
    # ------------------------------------------------------------------
    @property
    def is_empty(self) -> bool:
        return not self.elements

    @property
    def is_single(self) -> bool:
        return len(self.elements) == 1

    @property
    def count(self) -> int:
        return len(self.elements)

    @property
    def primary(self) -> Optional[Any]:
        return self.elements[0] if self.elements else None

    # ------------------------------------------------------------------
    def reset_to_original(self):
        """Cancel — değişiklikleri geri al (scene'e dokunmadan)."""
        self.values = _deep_copy(self.original)


# ----------------------------------------------------------------------
def _deep_copy(d):
    """MIXED gibi sentinel'leri koruyan basit kopya."""
    if isinstance(d, dict):
        return {k: _deep_copy(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_deep_copy(v) for v in d]
    return d