# app/panel_registry.py
"""
Panel & ikon kayıt merkezi.

PANEL_SPECS:
    her giriş bir dict — name/cls/title/category/toolbar/shortcut/menu_label/icon

ICON_MAP:
    semantik ikon adı → assets/icons_base64.ICON_DATA anahtarı
    Toolbar, panel kaydındaki 'icon' alanını önce buradan çözer,
    bulamazsa doğrudan ICON_DATA'ya bakar, o da yoksa imgui.button fallback.

IconManager:
    base64 PNG → OpenGL texture cache. Toolbar bu sınıfı kullanır.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Optional, Tuple

import OpenGL.GL as gl
from PIL import Image

from assets.icons_base64 import ICON_DATA

from inspector import InspectorWindow
from ui.sd_convert_panel import SDConvertPanel
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
from ui.s2k_panel import S2KPanel


# ======================================================================
# Panel Kayıtları
# ======================================================================
PANEL_SPECS = [
    # --- Dosya ---
    {
        "name": "new_project", "cls": None, "title": "Yeni Proje",
        "category": "Dosya", "kind": "action",
        "quick": False, "shortcut": "CTRL+N",
        "menu_label": "Yeni", "icon": "file-plus","context": [],
    },
    {
        "name": "open", "cls": None, "title": "Aç",
        "category": "Dosya", "kind": "action",
        "quick": False, "shortcut": "CTRL+O",
        "menu_label": "Aç", "icon": "folder","context": [],
    },
    {
        "name": "save", "cls": None, "title": "Kaydet",
        "category": "Dosya", "kind": "action",
        "quick": True, "shortcut": "CTRL+S",
        "menu_label": "Kaydet", "icon": "save","context": [],
    },
    {
        "name": "save_as", "cls": None, "title": "Farklı Kaydet",
        "category": "Dosya", "kind": "action",
        "quick": False, "shortcut": "SHIFT+CTRL+S",
        "menu_label": "Farklı Kaydet", "icon": "save","context": [],
    },
    {
        "name":       "s2k_panel",
        "cls":        S2KPanel,
        "title":      "S2K İçe / Dışa Aktarma",
        "category":   "Dosya",
        "quick":      False,
        "shortcut":   "F11",
        "menu_label": "S2K İçe / Dışa Aktar",
        "icon":       "log-in","context": [],
    },
    {
        "name": "close_app", "cls": None, "title": "Çıkış",
        "category": "Dosya", "kind": "action",
        "quick": False, "shortcut": None,
        "menu_label": "Çıkış", "icon": "x","context": [],
    },
    # --- Çizim (mod/aksiyon, panel değil) ---
    {
        "name":       "draw_poly",
        "cls":        None,           # panel sınıfı yok
        "title":      "Poly Çiz",
        "category":   "Çizim",
        "kind":       "action",
        "quick":      False,
        "shortcut":   "D",
        "menu_label": "Poly (D)",
        "icon":       "edit","context": [],
    },
    {
        "name":       "draw_plane",
        "cls":        None,
        "title":      "Plane Çiz",
        "category":   "Çizim",
        "kind":       "action",
        "quick":      False,
        "shortcut":   "SHIFT+W",
        "menu_label": "Plane (Shift+W)",
        "icon":       "grid","context": [],
    },

    # --- Görünüm ---
    {
        "name":       "grid",
        "cls":        GridPanel,
        "title":      "Grid Ayarları",
        "category":   "Görünüm",
        "quick":      True,
        "shortcut":   "CTRL+G",
        "menu_label": "Grid Ayarları",
        "icon":       "hash","context": [],
    },
    {
        "name":       "inspector",
        "cls":        InspectorWindow,
        "title":      "Özellikler (Inspector)",
        "category":   "Görünüm",
        "quick":      True,
        "shortcut":   "CTRL+P",
        "menu_label": "Inspector / Özellikler",
        "icon":       "layout",
        "context": ["scene", "catalog"],
    },
    {
        "name":       "visibility",
        "cls":        VisibilityPanel,
        "title":      "Görünürlük Paneli",
        "category":   "Görünüm",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Görünürlük",
        "icon":       "eye","context": [],
    },
    {
        "name":       "view_filter",
        "cls":        ViewFilterPanel,
        "title":      "Görünüm Filtresi",
        "category":   "Görünüm",
        "quick":      False,
        "shortcut":   "F6",
        "menu_label": "Görünüm Filtresi",
        "icon":       "filter","context": [],
    },
    {
        "name":       "plane_manager",
        "cls":        PlaneManagerPanel,
        "title":      "Plane Manager",
        "category":   "Görünüm",
        "quick":      True,
        "shortcut":   "F12",
        "menu_label": "Plane Manager",
        "icon":       "layers","context": [],
    },
    {
        "name":       "plane_plot",
        "cls":        PlanePlotPanel,
        "title":      "Plane Plot (2D)",
        "category":   "Görünüm",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Plane Plot (2D)",
        "icon":       "grid","context": [],
    },

    # --- Yükler ---
    {
        "name":       "assign_area_load",
        "cls":        LoadAssignPanel,
        "title":      "Alan Yükü Atama",
        "category":   "Yükler",
        "quick":      True,
        "shortcut":   None,
        "menu_label": "Alan Yükü Atama",
        "icon":       "arrow-down-circle",
        "context": ["selection_areas", "patterns"],
    },
    {
        "name":       "assign_frame_distributed_load",
        "cls":        FrameLoadPanel,
        "title":      "Çubuk Yayılı Yük",
        "category":   "Yükler",
        "quick":      True,
        "shortcut":   None,
        "menu_label": "Çubuk Yayılı Yük",
        "icon":       "arrow-down",
        "context": ["selection_frames", "patterns"],
    },
    {
        "name":       "load_display_panel",
        "cls":        LoadDisplayPanel,
        "title":      "Yük Görüntüleme",
        "category":   "Yükler",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Yük Görüntüleme",
        "icon":       "eye",
        "context": ["scene", "patterns"],
    },

    # --- Yönetim ---
    {
        "name":       "definitions",
        "cls":        DefinitionPanel,
        "title":      "Tanımlar",
        "category":   "Yönetim",
        "quick":      True,
        "shortcut":   "CTRL+R",
        "menu_label": "Tanımlar",
        "icon":       "database","context": [],
    },
    {
        "name":       "project_info",
        "cls":        ProjectInfoPanel,
        "title":      "Proje Bilgileri",
        "category":   "Yönetim",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Proje Bilgileri",
        "icon":       "info","context": [],
    },
    {
        "name":       "project_config",
        "cls":        ProjectConfigPanel,
        "title":      "Proje Yapılandırması",
        "category":   "Yönetim",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Proje Yapılandırması",
        "icon":       "settings","context": [],
    },
    {
        "name":       "analysis",
        "cls":        AnalysisManagerPanel,
        "title":      "Analiz Yöneticisi",
        "category":   "Yönetim",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Analiz Yöneticisi",
        "icon":       "code",
        "context": ["scene", "project"],
    },
    {
        "name":       "report",
        "cls":        ReportPanel,
        "title":      "Raporlar",
        "category":   "Yönetim",
        "quick":      True,
        "shortcut":   None,
        "menu_label": "Raporlar",
        "icon":       "file-text","context": [],
    },

    # --- Araçlar ---
    {
        "name":       "wind",
        "cls":        ZonesPanel,
        "title":      "Rüzgar Bölgeleri",
        "category":   "Araçlar",
        "quick":      False,
        "shortcut":   None,
        "menu_label": "Rüzgar Bölgeleri",
        "icon":       "wind",
        "context": ["on_run_analysis", "on_select_direction", "on_distribute"],
    },
    {
        "name":       "sd_convert",
        "cls":        SDConvertPanel,
        "title":      "SD → Area",
        "category":   "Araçlar",
        "quick":      False,
        "shortcut":   "CTRL+SHIFT+J",
        "menu_label": "SD → Area Dönüşümü",
        "icon":       "edit","context": [],
    },
]

# Menü sıralaması
CATEGORY_ORDER = ["Dosya", "Çizim", "Görünüm", "Yükler", "Yönetim", "Araçlar"]
WIDGET_SPECS = [
    {
        "name":   "unit_selector",
        "render": lambda tb: tb._render_unit_selector(),
    },
    {
        "name":   "model_label",
        "render": lambda tb: tb._render_model_label(),
    },
]

# ======================================================================
# Texture cache
# ======================================================================
class IconManager:
    """Base64 PNG → OpenGL texture önbelleği. GPU bağlamı hazırken çağır."""

    def __init__(self):
        self._textures: dict[str, Tuple[int, int, int]] = {}

    def get_texture(self, icon_name: Optional[str]):
        """'icon_name' doğrudan ICON_DATA anahtarıdır. Yoksa None."""
        if not icon_name:
            return None
        if icon_name in self._textures:
            return self._textures[icon_name]
        if icon_name not in ICON_DATA:
            return None

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