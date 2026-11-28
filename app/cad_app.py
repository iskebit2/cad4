# app/cad_app.py
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from app.commands.base import Command, CommandQueue, CommandResult, bind_app
from app.commands.edit_controller import EditController
from app.commands.impl import Redo, Undo
from app.services.panel_registry import PanelRegistry
from app.services.project_service import ProjectService
from app.services.view_service import ViewService
from app.services.visibility_service import VisibilityService
from app.services.wind_service import WindService
from tools.wind_manager import WindManager
import app.commands as cmd_
registry = cmd_.get_registry()

print("Import edilen komutlar:")
print("Komut Sayısı:",len(registry.list_names()))
# print("Tüm registry komutlar:", registry.list_names())


if TYPE_CHECKING:
    from core.engine import Engine
    from domain.project import Project
    from ui.ui_host import UIHost
    from viewport.viewport_manager import ViewportManager

from logging_config import CadLogger

logger = CadLogger.get(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_MAX_FOLLOWUP_CHAIN = 1000


class CadApp:
    def __init__(self, width: int = 1200, height: int = 800) -> None:
        self.width = max(1, width)
        self.height = max(1, height)

        self.engine: Engine | None = None
        self.viewport_manager: ViewportManager | None = None
        self.command_queue = CommandQueue()
        self.edit_controller: EditController | None = None

        self._ui_host: UIHost | None = None
        self.on_quit: Callable[[], None] | None = None

        self.project_service = ProjectService(self)
        self.view_service = ViewService(self)
        self.visibility_service = VisibilityService(self)
        self.panel_registry = PanelRegistry(self)
        self.wind_service = WindService(self)
        self.wind_manager = WindManager(self)
        self.wind_service.attach(self.wind_manager)

        self._command_registry = None
        self._section_catalog: dict | None = None
        self.shortcut_store = None

        bind_app(self)

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
            self._section_catalog = load_catalog_from_dir(_DATA_DIR)
            logger.info("[CadApp] Kesit kataloğu: %d kesit", len(self._section_catalog))
        return self._section_catalog

    def init_engine(self) -> None:
        from app.input_bindings import apply_shortcuts
        from app.settings.shortcut_store import ShortcutStore
        from core.engine import Engine
        from viewport.viewport_manager import ViewportManager

        self.engine = Engine(self.width, self.height, self.command_queue)
        self.engine.init_gl()

        if self.shortcut_store is None:
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
        self.edit_controller = EditController(self)

        if self._ui_host is not None and self.engine.sel_mgr is not None:
            self.engine.sel_mgr.on_selection_changed = self._ui_host.on_selection_changed

    def attach_ui(self, ui_host: UIHost) -> None:
        self._ui_host = ui_host
        if self.engine is not None and self.engine.sel_mgr is not None:
            self.engine.sel_mgr.on_selection_changed = ui_host.on_selection_changed
        ui_host.on_engine_ready()
        self._refresh_hover_listener_flag()

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
        if self.wind_manager is not None and hasattr(self.wind_manager, "shutdown"):
            self.wind_manager.shutdown()
        if self.engine is not None:
            renderer = getattr(self.engine, "renderer", None)
            if renderer is not None:
                renderer.cleanup()
            self.engine = None
        self.edit_controller = None
        self.command_queue = CommandQueue()

    def put_command(self, cmd) -> None:
        self.command_queue.put(cmd)
        # Terminal varsa echo et
        try:
            reg = getattr(self, "panel_registry", None)
            entry = reg.get("command_panel") if reg is not None else None
            panel = entry.instance if entry is not None else None
            if panel is not None and hasattr(panel, "append_echo"):
                panel.append_echo(f"→ {cmd!r}")
        except Exception:
            pass

    def log_command_result(self, msg: str, level: str = "info") -> None:
        if self._ui_host is not None:
            self._ui_host.log_command_result(msg, level=level)

    # ------------------------------------------------------------------
    # Komut akışı
    # ------------------------------------------------------------------

    def _execute_command(self, cmd) -> CommandResult:
        if isinstance(cmd, Undo):
            if self.edit_controller is None:
                return CommandResult(handled=False, message="EditController yok", level="warn")
            return self.edit_controller.commands.undo()
        if isinstance(cmd, Redo):
            if self.edit_controller is None:
                return CommandResult(handled=False, message="EditController yok", level="warn")
            return self.edit_controller.commands.redo()
        if not isinstance(cmd, Command):
            return CommandResult(
                handled=False,
                message=f"Bilinmeyen komut: {type(cmd).__name__}",
                level="warn",
            )
        if self.edit_controller is None:
            return CommandResult(handled=False, message="EditController yok", level="warn")
        return self.edit_controller.commands.execute(cmd)

    def _drain_commands(self) -> None:
        pending = self.command_queue.drain()
        if not pending:
            return

        geometry_dirty = False
        project_dirty = False
        processed = 0

        while pending and processed < _MAX_FOLLOWUP_CHAIN:
            cmd = pending.pop(0)
            processed += 1
            result = self._execute_command(cmd)

            if self._ui_host is not None and result.message:
                self._ui_host.log_command_result(result.message, level=result.level)

            if not result.handled:
                logger.warning(
                    "[cmd] işlenemedi: %s (%s)",
                    type(cmd).__name__,
                    result.message,
                )
                continue

            if result.followup is not None:
                pending.append(result.followup)

            geometry_dirty |= result.geometry_dirty
            project_dirty |= result.project_dirty

        if processed >= _MAX_FOLLOWUP_CHAIN:
            logger.error("[cmd] followup zinciri sınırı aşıldı (%d)", _MAX_FOLLOWUP_CHAIN)

        if geometry_dirty and self.engine is not None and self.project_service.project is not None:
            self.engine.update_geo(self.project_service.project)
        if project_dirty and self._ui_host is not None:
            self._ui_host.on_project_changed()

    def _update_scene_if_dirty(self) -> None:
        model = self.engine.math_model if self.engine else None
        if model is None:
            return
        is_dirty = getattr(model, "is_dirty", None)
        if not callable(is_dirty) or not is_dirty():
            return
        self.engine.renderer.update_geo(model)
        clear = getattr(model, "clear_dirty", None)
        if callable(clear):
            clear()

    def _refresh_hover_listener_flag(self) -> None:
        eng = self.engine
        if eng is None or eng.hover is None:
            return
        eng.hover.listeners_present = any(
            getattr(panel, "on_hover_changed", None)
            for _spec, panel in self.panel_registry.visible_instances()
        )