# app/cad_app.py
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from app.commands.command_queue import CommandQueue
from app.services.panel_registry import PanelRegistry
from app.services.project_service import ProjectService
from app.services.view_service import ViewService
from app.services.visibility_service import VisibilityService
from app.services.wind_service import WindService
from app.commands.edit_controller import EditController
from logging_config import CadLogger
from tools.wind_manager import WindManager

if TYPE_CHECKING:
    from core.engine import Engine
    from domain.project import Project
    from ui.ui_host import UIHost
    from viewport.viewport_manager import ViewportManager

logger = CadLogger.get(__name__)


class CadApp:
    """Orkestratör. İş mantığı servislerde; sadece yaşam döngüsü + komut akışı."""

    def __init__(self, width: int = 1200, height: int = 800):
        self.width = max(1, width)
        self.height = max(1, height)

        self.engine: Engine | None = None
        self.viewport_manager: ViewportManager | None = None
        self.command_queue = CommandQueue()

        self._ui_host: UIHost | None = None
        self.on_quit: Callable[[], None] | None = None

        # Servisler
        self.project_service = ProjectService(self)
        self.view_service = ViewService(self)
        self.visibility_service = VisibilityService(self)
        self.panel_registry = PanelRegistry(self)
        self.wind_service = WindService(self)

        self.edit_controller: EditController | None = None
        self.wind_manager = WindManager(self)
        self.wind_service.attach(self.wind_manager)

        self._command_registry = None
        self._section_catalog: dict | None = None
        self._data_dir = Path(__file__).parent.parent / "data"

    # ------------------------------------------------------------------
    # PROPERTIES
    # ------------------------------------------------------------------
    @property
    def ui(self) -> UIHost | None:
        return self._ui_host

    @property
    def current_project(self) -> Project:
        return self.project_service.project

    @property
    def command_registry(self):
        if self._command_registry is None:
            from app.commands.registry import get_registry
            self._command_registry = get_registry()
        return self._command_registry

    @property
    def section_catalog(self) -> dict:
        if self._section_catalog is None:
            from data.section_catalog import load_catalog_from_dir
            self._section_catalog = load_catalog_from_dir(self._data_dir)
            logger.info("[CadApp] Kesit kataloğu: %d kesit", len(self._section_catalog))
        return self._section_catalog

    # ------------------------------------------------------------------
    # YAŞAM DÖNGÜSÜ
    # ------------------------------------------------------------------
    def init_engine(self) -> None:
        from core.engine import Engine
        from viewport.viewport_manager import ViewportManager
        from app.input_bindings import apply_shortcuts
        from app.settings.shortcut_store import ShortcutStore

        self.engine = Engine(self.width, self.height, self.command_queue)
        self.engine.init_gl()

        if not hasattr(self, "shortcut_store") or self.shortcut_store is None:
            self.shortcut_store = ShortcutStore()

        dropped = apply_shortcuts(
            self.engine.input,
            self.command_queue,
            self.command_registry,
            self.shortcut_store,
            
        )
        for cmd_id in dropped:
            logger.warning("[shortcuts] geçersiz kombinasyon, atlandı: %s", cmd_id)

        self.viewport_manager = ViewportManager(self.engine)
        self.engine.viewport_manager = self.viewport_manager
        self.edit_controller = EditController(self.engine)

    def attach_ui(self, ui_host: "UIHost") -> None:
        self._ui_host = ui_host
        if self.engine is not None and self.engine.sel_mgr is not None:
            self.engine.sel_mgr.on_selection_changed = ui_host.on_selection_changed
        if self.engine is not None:
            ui_host.on_engine_ready()

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        if self.engine is not None:
            self.engine.resize(self.width, self.height)

    def tick(self, dt: float) -> None:
        if self.engine is None:
            return
        self._drain_commands()
        self.wind_manager.process_queue()
        self._update_scene_if_dirty()
        if self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def request_quit(self) -> None:
        if self.on_quit is not None:
            self.on_quit()

    def shutdown(self) -> None:
        if self._ui_host is not None:
            self._ui_host.shutdown()
            self._ui_host = None
        if self.engine is not None:
            self.engine.renderer.cleanup()
            self.engine = None
        self.edit_controller = None

    # ------------------------------------------------------------------
    # KOMUT AKIŞI
    # ------------------------------------------------------------------
    def put_command(self, cmd) -> None:
        self.command_queue.put(cmd)

    def log_command_result(self, msg: str, level: str = "info") -> None:
        if self._ui_host is not None:
            self._ui_host.log_command_result(msg, level=level)

    def _drain_commands(self) -> None:
        cmds = self.command_queue.drain()
        if not cmds:
            return

        geometry_dirty = False
        project_dirty = False

        for cmd in cmds:
            result = self.command_registry.dispatch(self, cmd)

            if self._ui_host is not None and result.message:
                self._ui_host.log_command_result(result.message, level=result.level)

            if not result.handled:
                logger.warning("[cmd] bilinmeyen: %r (%s)", cmd, type(cmd).__qualname__)
                continue

            if result.followup is not None:
                self.command_queue.put(result.followup)

            geometry_dirty |= result.geometry_dirty
            project_dirty |= result.project_dirty

        if geometry_dirty and self.engine and self.project_service.project:
            self.engine.update_geo(self.project_service.project)
        if project_dirty and self._ui_host is not None:
            self._ui_host.on_project_changed()

    def _update_scene_if_dirty(self) -> None:
        model = self.engine.math_model if self.engine else None
        if model and model.is_dirty():
            self.engine.renderer.update_geo(model)
            model.clear_dirty()

    def _refresh_hover_listener_flag(self) -> None:
        eng = self.engine
        if eng is None or eng.hover is None:
            return
        eng.hover.listeners_present = any(
            getattr(e.instance, "on_hover_changed", None)
            for e in self.panel_registry.visible()
        )