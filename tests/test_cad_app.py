#tests/test_cad_app.py
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_stubs():
    for name in ["core", "core.engine", "viewport", "viewport.viewport_manager",
                 "app.input_bindings", "app.settings", "app.settings.shortcut_store",
                 "app.services", "app.services.panel_registry", "app.services.project_service",
                 "app.services.view_service", "app.services.visibility_service",
                 "app.services.wind_service", "tools", "tools.wind_manager",
                 "data", "data.section_catalog", "ui", "ui.ui_host"]:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    sys.modules["core.engine"].Engine = MagicMock()
    sys.modules["viewport.viewport_manager"].ViewportManager = MagicMock()
    sys.modules["app.input_bindings"].apply_shortcuts = MagicMock(return_value=[])
    sys.modules["app.settings.shortcut_store"].ShortcutStore = MagicMock()
    sys.modules["app.services.panel_registry"].PanelRegistry = MagicMock
    sys.modules["app.services.project_service"].ProjectService = MagicMock
    sys.modules["app.services.view_service"].ViewService = MagicMock
    sys.modules["app.services.visibility_service"].VisibilityService = MagicMock
    sys.modules["app.services.wind_service"].WindService = MagicMock
    sys.modules["tools.wind_manager"].WindManager = MagicMock
    sys.modules["data.section_catalog"].load_catalog_from_dir = MagicMock(return_value={})
    sys.modules["ui.ui_host"].UIHost = MagicMock


_install_stubs()


def test_edit_controller_receives_app():
    from app.commands.edit_controller import EditController
    from app.cad_app import CadApp
    app = CadApp()
    app.init_engine()
    assert isinstance(app.edit_controller, EditController)
    assert app.edit_controller._app is app


def test_undo_not_in_stack():
    from app.cad_app import CadApp
    from app.commands.impl import Undo
    from app.commands.base import CommandResult
    app = CadApp()
    app.init_engine()
    result = app._execute_command(Undo())
    assert isinstance(result, CommandResult)
    assert not app.edit_controller.commands.can_undo


def test_drain_followup_immediate():
    from app.cad_app import CadApp
    from app.commands.base import Command, CommandResult
    from app.commands.impl import AddNode

    class Follower(Command):
        executed = False
        def execute(self):
            Follower.executed = True
            return CommandResult(handled=True)
        def undo(self): pass

    app = CadApp()
    app.init_engine()
    app.put_command(Follower())
    app._drain_commands()
    assert Follower.executed


def test_drain_followup_chain_limit():
    from app.cad_app import CadApp, _MAX_FOLLOWUP_CHAIN
    from app.commands.base import Command, CommandResult

    class Looper(Command):
        def execute(self):
            return CommandResult(handled=True, followup=Looper())
        def undo(self): pass

    app = CadApp()
    app.init_engine()
    app.put_command(Looper())
    app._drain_commands()
    assert True


def test_shutdown_idempotent():
    from app.cad_app import CadApp
    app = CadApp()
    app.init_engine()
    app.shutdown()
    app.shutdown()


def test_attach_ui_before_engine():
    from app.cad_app import CadApp
    app = CadApp()
    ui = MagicMock()
    app.attach_ui(ui)
    app.init_engine()
    assert ui.on_engine_ready.called


def test_current_project_delegates():
    from app.cad_app import CadApp
    app = CadApp()
    assert app.current_project is app.project_service.project


def test_put_command_queues():
    from app.cad_app import CadApp
    app = CadApp()
    app.put_command("x")
    assert app.command_queue.drain() == ["x"]


def test_refresh_hover_listener_flag():
    from app.cad_app import CadApp
    app = CadApp()
    app.engine = MagicMock()
    app.engine.hover = MagicMock(listeners_present=False)
    app.panel_registry.visible_instances = MagicMock(return_value=[])
    app._refresh_hover_listener_flag()
    assert app.engine.hover.listeners_present is False