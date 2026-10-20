# inspector/schema_bridge.py
from typing import Any, List, Optional, Protocol


class Catalog(Protocol):
    """Inspector'ın definition alanları için ihtiyaç duyduğu arayüz."""
    def list_sections(self) -> List[str]: ...
    def get_section(self, name: str) -> Optional[Any]: ...
    def list_materials(self) -> List[str]: ...
    def get_material(self, name: str) -> Optional[Any]: ...
    def list_link_props(self) -> List[str]: ...
    def list_load_patterns(self) -> List[str]: ...

from ui.adapters import (
    MIXED,
    element_to_values,
    elements_to_common_values,
    values_to_element,
)
from ui.schemas import schema_for, multi_schema_for

__all__ = [
    "MIXED",
    "element_to_values",
    "elements_to_common_values",
    "values_to_element",
    "schema_for",
    "multi_schema_for",
]

_schema_cache = {}

def schema_for_cached(element_type: str):
    if element_type not in _schema_cache:
        _schema_cache[element_type] = schema_for(element_type)
    return _schema_cache[element_type]