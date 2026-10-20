# app/panel_registry.py

from inspector import InspectorWindow
from ui.visibility_panel import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.grid_panel import GridPanel
from ui.zones_panel import ZonesPanel
from ui.definition_panel import DefinitionPanel
from ui.project_panels import (
    ProjectInfoPanel, ProjectConfigPanel, AnalysisManagerPanel, ReportPanel,
)
from ui.load_assign_panel import LoadAssignPanel
from ui.frame_load_panel import FrameLoadPanel
from ui.load_display_panel import LoadDisplayPanel
from ui.plane_plot_panel import PlanePlotPanel
from ui.plane_manager_panel import PlaneManagerPanel
from ui.s2k_import_panel import S2KImportPanel
from ui.section_panel import SectionPanel

# name: (class, title, category, toolbar, shortcut)
PANEL_SPECS = [
    ("s2k_import",                  S2KImportPanel,       "S2K İçe Aktarma",         "tools",      False, "F11"),
    ("grid",                        GridPanel,            "Grid Ayarları",           "view",       True,  "CTRL+G"),
    ("inspector",                   InspectorWindow,      "Özellikler (Inspector)",  "view",       True,  "CTRL+P"),
    ("visibility",                  VisibilityPanel,      "Görünürlük Paneli",       "view",       True,  None),
    ("view_filter",                 ViewFilterPanel,      "Görünüm Filtresi",        "view",       True,  "F6"),
    ("wind",                        ZonesPanel,           "Rüzgar Bölgeleri",        "analysis",   True,  None),
    ("definitions",                 DefinitionPanel,      "Tanımlar",                "management", True,  "CTRL+R"),
    ("project_info",                ProjectInfoPanel,     "Proje Bilgileri",         "management", True,  None),
    ("project_config",              ProjectConfigPanel,   "Proje Yapılandırması",    "management", True,  None),
    ("analysis",                    AnalysisManagerPanel, "Analiz Yöneticisi",      "management", True,  None),
    ("report",                      ReportPanel,          "Raporlar",                "management", True,  None),
    ("assign_area_load",            LoadAssignPanel,      "Alan Yükü Atama",         "loads",      True,  None),
    ("assign_frame_distributed_load", FrameLoadPanel,     "Çubuk Yayılı Yük",        "loads",      True,  None),
    ("load_display_panel",          LoadDisplayPanel,     "Yük Görüntüleme",         "loads",      True,  None),
    ("plane_plot",                  PlanePlotPanel,       "Plane Plot (2D)",         "tools",      False, None),
    ("plane_manager",               PlaneManagerPanel,    "Plane Manager",           "tools",      True,  "F12"),
    
    # ("material_panel", MaterialPanel, "Malzeme Yönetimi", "Tanımlar", True, "CTRL+M"),
]