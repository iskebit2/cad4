# inspector/schema_bridge.py
from typing import Any, Protocol


class Catalog(Protocol):
    """Inspector'ın definition alanları için ihtiyaç duyduğu arayüz."""
    def list_sections(self) -> list[str]: ...
    def get_section(self, name: str) -> Any | None: ...
    def list_materials(self) -> list[str]: ...
    def get_material(self, name: str) -> Any | None: ...
    def list_link_props(self) -> list[str]: ...
    def list_load_patterns(self) -> list[str]: ...

from ui.adapters import (
    MIXED,
    element_to_values,
    elements_to_common_values,
    values_to_element,
)
from ui.schemas import multi_schema_for, schema_for

__all__ = [
    "MIXED",
    "element_to_values",
    "elements_to_common_values",
    "multi_schema_for",
    "schema_for",
    "values_to_element",
]

_schema_cache = {}

def schema_for_cached(element_type: str):
    if element_type not in _schema_cache:
        _schema_cache[element_type] = schema_for(element_type)
    return _schema_cache[element_type]