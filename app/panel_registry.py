"""
Panel & Icon Registry Center.
Optimized with dataclasses, type hints, and English definitions.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Callable

import OpenGL.GL as gl
from PIL import Image

from assets.icons_base64 import ICON_DATA
from inspector import InspectorWindow
from ui.area_to_frame_panel import AreaToFramePanel
from ui.definition_panel import DefinitionPanel
from ui.frame_load_panel import FrameLoadPanel
from ui.frame_preview_panel import FramePreviewPanel
from ui.grid_panel import GridPanel
from ui.joint_load_panel import JointLoadPanel
from ui.line_properties_panel import LinePropertiesPanel
from ui.load_assign_panel import LoadAssignPanel
from ui.load_display_panel import LoadDisplayPanel
from ui.load_manager_panel import LoadManagerPanel
from plane.plane_manager_panel import PlaneManagerPanel
from ui.polygon_properties_panel import PolygonPropertiesPanel
from ui.project_panels import AnalysisManagerPanel, ProjectConfigPanel, ProjectInfoPanel
from ui.project_settings_panel import ProjectSettingsPanel  # Centralized settings panel
from ui.render_settings_panel import RenderSettingsPanel
from ui.report_panel import ReportPanel
from ui.s2k_panel import S2KPanel
from ui.sd_convert_panel import SDConvertPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.visibility_panel import VisibilityPanel
from ui.wind_analysis_panel import WindAnalysisPanel
from app.debug_panel import DebugPanel


@dataclass
class PanelSpec:
    """Type-safe specification container for panels and actions."""
    name: str
    cls: Any | None = None
    title: str = ""
    category: str = "General"
    kind: str = "panel"  # 'panel' or 'action'
    quick: bool = False
    shortcut: str | None = None
    menu_label: str = ""
    icon: str = "settings"
    context: list[str] = field(default_factory=list)


# ======================================================================
# Panel & Action Specifications (English Standard)
# ======================================================================
PANEL_SPECS: list[PanelSpec] = [
    # --- File ---
    PanelSpec(name="new_project", title="New Project", category="File", kind="action", shortcut="CTRL+N", menu_label="New", icon="file-plus"),
    PanelSpec(name="open", title="Open Project", category="File", kind="action", shortcut="CTRL+O", menu_label="Open...", icon="folder"),
    PanelSpec(name="save", title="Save Project", category="File", kind="action", quick=True, shortcut="CTRL+S", menu_label="Save", icon="save"),
    PanelSpec(name="save_as", title="Save As", category="File", kind="action", shortcut="SHIFT+CTRL+S", menu_label="Save As...", icon="save"),
    PanelSpec(name="s2k_panel", cls=S2KPanel, title="S2K Import / Export", category="File", quick=True, shortcut="F11", menu_label="S2K Exchange", icon="log-in"),
    PanelSpec(name="close_app", title="Exit", category="File", kind="action", menu_label="Exit", icon="x"),

    # --- Draw ---
    PanelSpec(name="draw_poly", title="Draw Polygon", category="Draw", kind="action", shortcut="D", menu_label="Polygon (D)", icon="edit"),
    PanelSpec(name="draw_plane", title="Draw Plane", category="Draw", kind="action", shortcut="SHIFT+W", menu_label="Plane (Shift+W)", icon="grid"),

    # --- View ---
    PanelSpec(
    name="render_settings",
    cls=RenderSettingsPanel,
    title="Render Settings",
    category="View",
    quick=True,
    shortcut="F7",
    menu_label="Render Settings",
    icon="sliders",
    context=["engine", "renderer", "math_model_renderer", "scene"],
),

    PanelSpec(name="grid", cls=GridPanel, title="Grid Settings", category="View", quick=True, shortcut="CTRL+G", menu_label="Grid Settings", icon="hash"),
    PanelSpec(name="inspector", cls=InspectorWindow, title="Inspector", category="View", quick=True, shortcut="CTRL+P", menu_label="Inspector", icon="layout", context=["scene", "math_model", "catalog", "project"]),
    PanelSpec(name="visibility", cls=VisibilityPanel, title="Visibility", category="View", menu_label="Visibility", icon="eye"),
    PanelSpec(name="view_filter", cls=ViewFilterPanel, title="View Filter", category="View", shortcut="F6", menu_label="View Filter", icon="filter", context=["camera"]),
    PanelSpec(name="plane_manager", cls=PlaneManagerPanel, title="Plane Manager", category="View", quick=True, shortcut="F12", menu_label="Plane Manager", icon="layers"),

    # --- Loads ---
    PanelSpec(name="load_manager", cls=LoadManagerPanel, title="Load Manager", category="Loads", quick=True, shortcut="F9", menu_label="Load Manager", icon="layers", context=["project", "scene", "math_model", "patterns", "selection_polygons", "selection_frames", "selection_nodes", "renderer"]),
    PanelSpec(name="assign_joint_load", cls=JointLoadPanel, title="Joint Load", category="Loads", quick=True, menu_label="Assign Joint Load", icon="arrow-up", context=["selection_nodes", "patterns"]),
    PanelSpec(name="assign_area_load", cls=LoadAssignPanel, title="Area Load Assignment", category="Loads", quick=True, menu_label="Assign Area Load", icon="arrow-down-circle", context=["project", "selection_polygons"]),
    PanelSpec(name="area_to_frame", cls=AreaToFramePanel, title="Area to Frame Load", category="Loads", quick=True, menu_label="Area to Frame", icon="arrow-down", context=["project", "math_model", "selection_polygons"]),
    PanelSpec(name="assign_frame_distributed_load", cls=FrameLoadPanel, title="Frame Distributed Load", category="Loads", quick=True, menu_label="Frame Distributed Load", icon="arrow-down", context=["selection_frames", "patterns"]),
    PanelSpec(name="load_display_panel", cls=LoadDisplayPanel, title="Load Display", category="Loads", menu_label="Load Display", icon="eye", context=["math_model", "renderer", "patterns"]),

    # --- Management ---
    PanelSpec(name="definitions", cls=DefinitionPanel, title="Definitions", category="Management", quick=True, shortcut="CTRL+R", menu_label="Definitions", icon="database"),
    PanelSpec(name="project_settings", cls=ProjectSettingsPanel, title="Project Settings", category="Management", quick=True, shortcut="CTRL+I", menu_label="Project Settings", icon="settings", context=["scene", "project"]),
    PanelSpec(name="analysis", cls=AnalysisManagerPanel, title="Analysis Manager", category="Management", menu_label="Analysis Manager", icon="code", context=["scene", "project"]),
    PanelSpec(name="report", cls=ReportPanel, title="Reports", category="Management", quick=True, menu_label="Reports", icon="file-text", context=["scene", "project"]),

    # --- Tools ---
    PanelSpec(name="polygon_properties", cls=PolygonPropertiesPanel, title="Polygon", category="Tools", quick=True, menu_label="Polygon", icon="edit", context=["project"]),
    PanelSpec(name="wind_analysis", cls=WindAnalysisPanel, title="Wind Analysis", category="Tools", quick=True, menu_label="Wind Analysis", icon="wind", context=["scene", "project"]),
    PanelSpec(name="sd_convert", cls=SDConvertPanel, title="SD to Area Conversion", category="Tools", shortcut="CTRL+SHIFT+J", menu_label="SD to Area", icon="edit"),
    PanelSpec(name="debug_panel", cls=DebugPanel, title="Debug Panel", category="Tools", shortcut="CTRL+SHIFT+D", menu_label="Debug Panel", icon="edit", context=["engine"]),
    PanelSpec(name="frame_preview", cls=FramePreviewPanel, title="FramePreview Panel", category="Tools", quick=True, menu_label="Preview Panel", icon="edit", context=["project","engine"]),
]

# Category Display Order
CATEGORY_ORDER: list[str] = ["File", "Draw", "View", "Loads", "Management", "Tools"]

# Toolbar Extra Widgets
WIDGET_SPECS: list[dict[str, Any]] = [
    {
        "name": "unit_selector",
        "render": lambda tb: tb._render_unit_selector(),
    },
    {
        "name": "model_label",
        "render": lambda tb: tb._render_model_label(),
    },
]


# ======================================================================
# Icon Manager (GPU Texture Cache)
# ======================================================================
class IconManager:
    """Manages Base64 PNG to OpenGL texture caching safely."""

    def __init__(self) -> None:
        self._textures: dict[str, tuple[int, int, int]] = {}

    def get_texture(self, icon_name: str | None) -> tuple[int, int, int] | None:
        """Retrieves or creates an OpenGL texture ID for the given icon name."""
        if not icon_name or icon_name not in ICON_DATA:
            return None

        if icon_name in self._textures:
            return self._textures[icon_name]

        try:
            img_data = base64.b64decode(ICON_DATA[icon_name])
            img = Image.open(BytesIO(img_data)).convert("RGBA")
            w, h = img.size
            raw = img.tobytes("raw", "RGBA")

            tex_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, w, h,
                0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw,
            )
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

            self._textures[icon_name] = (tex_id, w, h)
            return self._textures[icon_name]
        except Exception as e:
            print(f"[IconManager Error] Failed to load icon '{icon_name}': {e}")
            return None