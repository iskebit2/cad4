# inspector/schema_bridge.py
from typing import Any, Protocol

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
    "schema_for_object",
    "values_to_element",
]


class Catalog(Protocol):
    def list_sections(self) -> list[str]: ...
    def get_section(self, name: str) -> Any | None: ...
    def list_materials(self) -> list[str]: ...
    def get_material(self, name: str) -> Any | None: ...
    def list_link_props(self) -> list[str]: ...
    def list_load_patterns(self) -> list[str]: ...


def schema_for_object(obj):
    from ui.schemas import (
        polygon_schema, line_schema,
        grid_schema, plane_schema, schema_for as _schema_for,
    )

    name = type(obj).__name__
    if name == "Polygon":
        return polygon_schema()
    if name == "Line":
        return line_schema()
    if name == "Grid":
        return grid_schema()
    if name == "Plane":
        return plane_schema()
    return _schema_for(getattr(obj, "element_type", name))