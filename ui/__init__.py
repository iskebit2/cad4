# ui/__init__.py
"""
UI katmanı — dışarıya sadece yüksek seviyeli arayüz sunar.
ImGui detayları bu paketin dışına sızmaz.
"""
from ui.inspector import InspectorPanel
from ui.schema import FieldSpec, GroupSpec
from ui.adapters import (
    node_to_values, values_to_node,
    frame_to_values, values_to_frame,
    area_to_values, values_to_area,
    link_to_values, values_to_link,
    polygon_to_values, values_to_polygon,
    element_to_values, values_to_element,
    elements_to_common_values,            # ← EKLENDİ
)
from ui.imgui_backend import UiBackend
from ui.schemas import (schema_for, multi_schema_for)
from ui.visibility_panel import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.inspector_panel import InspectorPanel
from ui.inspector_tab import InspectorTab
from ui.definitions_tab import DefinitionsTab
from ui.zones_panel import ZonesPanel

__all__ = [
    "InspectorPanel",
    "FieldSpec", "GroupSpec",
    "node_to_values", "values_to_node",
    "frame_to_values", "values_to_frame",
    "area_to_values", "values_to_area",
    "link_to_values", "values_to_link",
    "polygon_to_values", "values_to_polygon",
    "element_to_values", "values_to_element",
    "elements_to_common_values",
    "multi_schema_for",
    "UiBackend",
    "schema_for",
    "VisibilityPanel",
    "ViewFilterPanel",
    "InspectorPanel", "InspectorTab", "DefinitionsTab",
    "ZonesPanel"
]