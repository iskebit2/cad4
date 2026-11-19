# app/services/toolbar_specs.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandSpec:
    """Quick-bar / menüde görünecek anlık komut (panel değil)."""
    cmd: Any                      # PC.xxx() örneği (dataclass instance)
    name: str                     # benzersiz anahtar
    label: str                    # menü metni
    icon: str = ""                # IconManager anahtarı
    shortcut: str = ""
    category: str = "Edit"
    quick: bool = False
    tooltip: str = ""
    check_state: Any = None       # Callable[[App], bool] | None — toggle komutları için


def default_commands() -> list[CommandSpec]:
    """Uygulamanın toolbar'da görmek istediği tüm dosya/düzen/görünüm komutları."""
    from app.commands import project_commands as PC

    return [
        # ---------- Dosya ----------
        CommandSpec(PC.NewProject(),     "file_new",     "Yeni",        "file-new",  "Ctrl+N", "File", True,  "Yeni proje"),
        CommandSpec(PC.OpenProject(""),  "file_open",    "Aç…",         "folder-open","Ctrl+O","File", True,  "Proje aç"),
        CommandSpec(PC.SaveProject(None),"file_save",    "Kaydet",      "save",      "Ctrl+S", "File", True,  "Kaydet"),
        CommandSpec(PC.SaveProjectAs(""),"file_save_as", "Farklı Kaydet…","save-as", "Ctrl+Shift+S", "File", False, "Farklı kaydet"),
        CommandSpec(PC.ImportS2K("", "import"), "file_import_s2k", "S2K İçe Al…", "import", "", "File", False, "SAP2000 import"),
        CommandSpec(PC.ExportS2K(""),    "file_export_s2k","S2K Dışa Ver…","export",  "",       "File", False, "SAP2000 export"),
        CommandSpec(PC.QuitApp(),        "file_quit",    "Çıkış",       "quit",      "Alt+F4", "File", False, "Uygulamadan çık"),

        # ---------- Düzen ----------
        CommandSpec(PC.Undo(),           "edit_undo",     "Geri Al",    "undo",      "Ctrl+Z", "Edit", True,  "Geri al"),
        CommandSpec(PC.Redo(),           "edit_redo",     "Yinele",     "redo",      "Ctrl+Y", "Edit", True,  "Yinele"),
        CommandSpec(PC.DeleteSelected(), "edit_delete",   "Sil",        "trash",     "Del",    "Edit", True,  "Seçilileri sil"),
        CommandSpec(PC.ClearSelection(), "edit_deselect", "Seçimi Bırak","deselect", "Esc",    "Edit", False, "Seçimi temizle"),

        # ---------- Görünüm ----------
        CommandSpec(PC.ZoomExtents(),    "view_fit",       "Sığdır",    "fit",       "F",      "View", True,  "Tümünü sığdır"),
        CommandSpec(PC.FitView(),        "view_fit_sel",   "Seçiliye Git","fit-sel", "Shift+F","View", False, "Seçiliye odakla"),
        CommandSpec(PC.Toggle2D(),       "view_2d",        "2D/3D",     "2d3d",      "T",      "View", True,  "2D/3D geçiş"),
        CommandSpec(PC.ToggleLocalAxes(),"view_axes",      "Yerel Eksenler","axes",  "X",      "View", True,  "Yerel eksenleri aç/kapa"),
        CommandSpec(PC.ToggleLoadsVisible(), "view_loads", "Yükler",    "loads",     "Y",      "View", True,  "Yükleri göster"),
        CommandSpec(PC.ToggleRenderMode(),"view_render",   "Render Modu","render",   "",       "View", False, "Shaded/simple"),

        # ---------- Çizim ----------
        CommandSpec(PC.StartDrawTool("line"), "draw_line", "Line Çiz", "line-draw",  "L",     "Draw", True,  "Line çiz"),
        CommandSpec(PC.StartDrawTool("poly"), "draw_poly", "Polygon Çiz","poly-draw","P",     "Draw", True,  "Polygon çiz"),
        CommandSpec(PC.StartPlaneTool(),      "draw_plane","Düzlem Çiz","plane-draw","",      "Draw", True,  "Çalışma düzlemi"),
        CommandSpec(PC.StartPlane3pt(),       "draw_plane3","3 Nokta Düzlem","plane-3pt","",  "Draw", False, "3 noktadan düzlem"),
        CommandSpec(PC.StartPlane2ptZ(),      "draw_plane2","2 Nokta + Z","plane-2ptz","",    "Draw", False, "2 nokta + Z düzlem"),

        # ---------- Dönüştür ----------
        CommandSpec(PC.ConvertFramesToLinks("DefaultLink"), "conv_to_link", "Link'e Çevir","to-link","", "Convert", True, "Frame → Link"),
    ]