# ui/actions_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from app.commands import project_commands as PC
from ui.base.panel_base import Category

if TYPE_CHECKING:
    from ui.ui_host import UIHost


@dataclass(frozen=True)
class ActionSpec:
    name: str
    category: Category | str
    menu_label: str
    shortcut: str = ""
    icon: str = ""
    quick: bool = False
    # Komut fabrikası veya UIHost modal diyalog adı
    command_factory: Callable[[], Any] | None = None
    host_dialog: str | None = None
    state_fn: Callable[[Any], bool] | None = None


ACTION_SPECS: list[ActionSpec] = [
    # --- FILE ---
    ActionSpec(
        name="new_project",
        category=Category.FILE,
        menu_label="Yeni Proje",
        shortcut="Ctrl+N",
        icon="new",
        quick=True,
        command_factory=lambda: PC.NewProject(),
    ),
    ActionSpec(
        name="open_project",
        category=Category.FILE,
        menu_label="Proje Aç...",
        shortcut="Ctrl+O",
        icon="open",
        quick=True,
        host_dialog="open_open_dialog",
    ),
    ActionSpec(
        name="save_project",
        category=Category.FILE,
        menu_label="Kaydet",
        shortcut="Ctrl+S",
        icon="save",
        quick=True,
        command_factory=lambda: PC.SaveProject(),
    ),
    ActionSpec(
        name="save_project_as",
        category=Category.FILE,
        menu_label="Farklı Kaydet...",
        shortcut="Ctrl+Shift+S",
        host_dialog="open_save_dialog",
    ),
    ActionSpec(
        name="s2k_import",
        category=Category.FILE,
        menu_label="SAP2000 (.s2k) İçe Aktar...",
        command_factory=lambda: PC.OpenPanel("s2k_panel", {"mode": "import"}),
    ),
    ActionSpec(
        name="s2k_export",
        category=Category.FILE,
        menu_label="SAP2000 (.s2k) Dışa Aktar...",
        command_factory=lambda: PC.OpenPanel("s2k_panel", {"mode": "export"}),
    ),
    ActionSpec(
        name="quit",
        category=Category.FILE,
        menu_label="Çıkış",
        shortcut="Alt+F4",
        command_factory=lambda: PC.QuitApp(),
    ),

    # --- EDIT ---
    ActionSpec(
        name="undo",
        category=Category.EDIT,
        menu_label="Geri Al",
        shortcut="Ctrl+Z",
        icon="undo",
        quick=True,
        command_factory=lambda: PC.Undo(),
    ),
    ActionSpec(
        name="redo",
        category=Category.EDIT,
        menu_label="Yinele",
        shortcut="Ctrl+Y",
        icon="redo",
        quick=True,
        command_factory=lambda: PC.Redo(),
    ),
    ActionSpec(
        name="delete_selected",
        category=Category.EDIT,
        menu_label="Seçilileri Sil",
        shortcut="Del",
        icon="delete",
        command_factory=lambda: PC.DeleteSelected(),
    ),

    # --- DRAW / MODEL ---
    ActionSpec(
        name="draw_line",
        category=Category.DRAW,
        menu_label="Çizgi Çiz",
        shortcut="D",
        icon="line",
        quick=True,
        command_factory=lambda: PC.StartDrawTool("line"),
        state_fn=lambda app: bool(app.engine and app.engine.draw_mgr and app.engine.draw_mgr.is_active),
    ),
    ActionSpec(
        name="draw_poly",
        category=Category.DRAW,
        menu_label="Poligon Çiz",
        shortcut="P",
        icon="polygon",
        quick=True,
        command_factory=lambda: PC.StartDrawTool("sequential"),
    ),
    ActionSpec(
        name="draw_plane_3pt",
        category=Category.DRAW,
        menu_label="3 Nokta ile Düzlem",
        command_factory=lambda: PC.StartPlane3pt(),
    ),
    ActionSpec(
        name="draw_plane_2pt_z",
        category=Category.DRAW,
        menu_label="2 Nokta + Z Düzlem",
        command_factory=lambda: PC.StartPlane2ptZ(),
    ),
    ActionSpec(
        name="plane_from_source",
        category=Category.DRAW,
        menu_label="Eleman/Grid'den Düzlem...",
        host_dialog="open_plane_source_dialog",
    ),

    # --- VIEW ---
    ActionSpec(
        name="fit_view",
        category=Category.VIEW,
        menu_label="Tüm Modeli Sığdır",
        shortcut="F",
        icon="fit",
        quick=True,
        command_factory=lambda: PC.ShowEntireModel(),
    ),
    ActionSpec(
        name="toggle_2d",
        category=Category.VIEW,
        menu_label="2D / 3D Geçişi",
        shortcut="F2",
        icon="2d",
        quick=True,
        command_factory=lambda: PC.Toggle2D(),
        state_fn=lambda app: bool(
            app.engine and app.engine.renderer and app.engine.renderer.projection == "plane_2d"
        ),
    ),
    ActionSpec(
        name="toggle_render_mode",
        category=Category.VIEW,
        menu_label="Render Modu (Shaded/Simple)",
        shortcut="F4",
        command_factory=lambda: PC.ToggleRenderMode(),
    ),
    ActionSpec(
        name="toggle_loads",
        category=Category.VIEW,
        menu_label="Yükleri Göster/Gizle",
        command_factory=lambda: PC.ToggleLoadsVisible(None),
        state_fn=lambda app: bool(app.view_service.get_loads_visible()),
    ),
    ActionSpec(
        name="toggle_local_axes",
        category=Category.VIEW,
        menu_label="Yerel Eksenleri Göster/Gizle",
        command_factory=lambda: PC.ToggleLocalAxes(),
        state_fn=lambda app: bool(
            app.engine and app.engine.scene and app.engine.scene.show_local_axes
        ),
    ),
    ActionSpec(
        name="open_inspector",
        category=Category.VIEW,
        menu_label="Inspector",
        shortcut="F3",
        command_factory=lambda: PC.OpenInspector(),
    ),
]


def build_commands(host: "UIHost") -> dict[str, Callable]:
    """
    Toolbar tıklamalarını doğrudan app.command_queue'ya bağlar.
    Yalnızca ImGui file/modal diyalogları UIHost üzerinden açılır.
    """
    cq = host.app.command_queue
    cmds: dict[str, Callable] = {
        "on_unit_change": lambda unit: cq.put(PC.SetUnitSystem(unit)),
    }

    for spec in ACTION_SPECS:
        if spec.command_factory is not None:
            factory = spec.command_factory
            cmds[spec.name] = lambda f=factory: cq.put(f())
        elif spec.host_dialog is not None:
            dialog_fn = getattr(host, spec.host_dialog, None)
            if callable(dialog_fn):
                cmds[spec.name] = dialog_fn

    return cmds


def build_panel_states(host: "UIHost") -> dict[str, Callable[[], bool]]:
    """Toolbar aktif buton ve menü checkmark durumlarını üretir."""
    app = host.app
    return {
        spec.name: (lambda fn=spec.state_fn: bool(fn(app)))
        for spec in ACTION_SPECS
        if spec.state_fn is not None
    }