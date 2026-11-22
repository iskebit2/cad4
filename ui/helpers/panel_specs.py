from dataclasses import dataclass

from app.settings.categories import Category
from ui.panels.analysis_panel import AnalysisManagerPanel
from ui.panels.area_to_frame_panel import AreaToFramePanel
from ui.panels.command_panel import CommandPanel
from ui.panels.debug_panel import DebugPanel
from ui.panels.definition_panel import DefinitionPanel
from ui.panels.frame_load_panel import FrameLoadPanel
from ui.panels.grid_panel import GridPanel
from ui.panels.joint_load_panel import JointLoadPanel
from ui.panels.load_assign_panel import LoadAssignPanel
from ui.panels.load_display_panel import LoadDisplayPanel
from ui.panels.load_manager_panel import LoadManagerPanel
from ui.panels.material_panel import MaterialPanel
from ui.panels.polygon_properties_panel import PolygonPropertiesPanel
from ui.panels.project_panels import ReportPanel
from ui.panels.s2k_panel import S2KPanel
from ui.panels.selection_panel import SelectionPanel
from ui.panels.test_panel import TestPanel
from ui.panels.view_filter_panel import ViewFilterPanel
from ui.panels.visibility_panel import VisibilityPanel
from ui.panels.wind_analysis_panel import WindAnalysisPanel


@dataclass
class PanelSpec:
    cls: type
    name: str
    title: str
    category: Category = Category.TOOLS
    quick: bool = False
    shortcut: str = ""
    menu_label: str = ""
    icon: str = ""
    context: tuple[str, ...] = ()
    order: int = 0


# ==============================================================================
# ELLE KONTROL EDİLEN PANEL LİSTESİ (Sıra = Menü ve Quick-Bar Sırası)
# ==============================================================================

PANELS: dict[int, PanelSpec] = {
    0: PanelSpec(
            cls=AnalysisManagerPanel,
            name="analysis_panel",
            title="Analysis Manager",
            category=Category.MANAGEMENT,
            quick=True,
            menu_label="Analysis Manager",
            icon="command_panel",
            shortcut="F1",
            order = 100
        ),

    1: PanelSpec(
        cls=CommandPanel,
        name="command_panel",
        title="Komut Satırı",
        category=Category.MANAGEMENT,
        quick=True,
        menu_label="Komut Satırı",
        icon="command_panel",
        shortcut="F1",
    ),
    2: PanelSpec(
        cls=GridPanel,
        name="grid",
        title="Grid Settings",
        category=Category.VIEW,
        quick=True,
        menu_label="Grid Settings",
        icon="grid",
        shortcut="CTRL+G",
        context=("project", "scene"),
    ),
    3: PanelSpec(
        cls=LoadDisplayPanel,
        name="load_display",
        title="Yük Görüntüleme",
        category=Category.VIEW,
        icon="load_display",
        quick=True,
        context=("math_model", "renderer"),
    ),
    4: PanelSpec(
        cls=LoadManagerPanel,
        name="load_manager",
        title="Load Manager",
        category=Category.LOADS,
        icon="load_manager",
        quick=True,
        context=("project", "scene", "selection_polygons", "selection_frames", "selection_nodes", "patterns"),
    ),
    5: PanelSpec(
        cls=ReportPanel,
        name="report",
        title="Reports",
        category=Category.MANAGEMENT,
        quick=True,
        menu_label="Reports",
        icon="report",
        context=("scene", "project"),
    ),
    6: PanelSpec(
        cls=S2KPanel,
        name="s2k_panel",
        title="S2K Import / Export",
        category=Category.FILE,
        quick=True,
        menu_label="S2K Exchange",
        icon="s2k_panel",
        shortcut="F11",
    ),
    7: PanelSpec(
        cls=WindAnalysisPanel,
        name="wind",
        title="Rüzgar Analizi",
        category=Category.LOADS,
        icon="wind",
        quick=True,
        context=("project", "engine"),
    ),
    8: PanelSpec(
        cls=AreaToFramePanel,
        name="area_to_frame",
        title="Area to Frame",
        category=Category.LOADS,
        icon="area_to_frame",
        context=("project", "engine"),
    ),
    9: PanelSpec(
        cls=DebugPanel,
        name="debug_panel",
        title="Debug & Input Inspector",
        category=Category.DEBUG,
        icon="debug_panel",
        context=("engine",),
    ),
    10: PanelSpec(
        cls=DefinitionPanel,
        name="definition",
        title="Definition Manager",
        category=Category.MANAGEMENT,
        icon="definition",
        context=("project",),
    ),
    11: PanelSpec(
        cls=FrameLoadPanel,
        name="frame_load",
        title="Frame Distributed Load",
        category=Category.LOADS,
        icon="frame_load",
        context=("selection_frames", "patterns", "math_model"),
    ),
    12: PanelSpec(
        cls=JointLoadPanel,
        name="joint_load",
        title="Noktasal Yük",
        category=Category.LOADS,
        icon="joint_load",
        context=("selection_nodes", "patterns", "math_model"),
    ),
    13: PanelSpec(
        cls=LoadAssignPanel,
        name="load_assign",
        title="Hazır Alan Yükleri",
        category=Category.LOADS,
        icon="load_assign",
        context=("project", "selection_polygons", "patterns"),
    ),
    14: PanelSpec(
        cls=MaterialPanel,
        name="material_panel",
        title="Material Properties",
        category=Category.MANAGEMENT,
        context=("project",),
    ),
    15: PanelSpec(
        cls=PolygonPropertiesPanel,
        name="polygon_properties",
        title="Polygon",
        category=Category.MANAGEMENT,
        icon="polygon_properties",
        context=("project", "engine"),
    ),
    16: PanelSpec(
        cls=SelectionPanel,
        name="selection",
        title="Selection Manager",
        category=Category.VIEW,
        icon="selection",
        context=("selection_manager", "selection_policy", "math_model"),
    ),
    17: PanelSpec(
        cls=TestPanel,
        name="test_panel",
        title="Test Properties",
        category=Category.MANAGEMENT,
        icon="test_panel",
        context=("project",),
    ),
    18: PanelSpec(
        cls=ViewFilterPanel,
        name="view_filter",
        title="View Filter",
        category=Category.VIEW,
        menu_label="View Filter",
        icon="view_filter",
        shortcut="F6",
        context=("camera",),
    ),
    19: PanelSpec(
        cls=VisibilityPanel,
        name="visibility",
        title="Visibility",
        category=Category.VIEW,
        context=("scene",),
    ),
}