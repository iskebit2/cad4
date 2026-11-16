# tests/conftest.py
from __future__ import annotations

import pytest

from app.commands.registry import CommandRegistry, build_registry


class FakeProject:
    """Minimum proje stub'ı — sadece handler'ların dokunduğu container'lar."""

    def __init__(self) -> None:
        self.sections: dict = {}
        self.materials: dict = {}
        self.load_patterns: dict = {}
        self.link_props: dict = {}
        self.frame_props: dict = {}
        self.area_props: dict = {}
        self.math_model = None
        self.scene = None


class FakeApp:
    """CadApp'in test edilebilir minimum yüzeyi."""

    def __init__(self) -> None:
        self.current_project = FakeProject()
        self.engine = None
        self._ui_host = None
        self.command_queue = None
        self._show_only_ids: set[int] | None = None
        self._hidden_ids: set[int] | None = None
        self._command_registry = build_registry()

    def set_project(self, project) -> None:
        self.current_project = project

    def set_unit_system(self, unit) -> None:
        self.current_project.unit_system = unit

    def set_loads_visible(self, enabled: bool) -> None:
        pass

    def toggle_2d(self) -> None:
        pass

    def show_entire_model(self) -> None:
        pass


@pytest.fixture
def fake_app() -> FakeApp:
    return FakeApp()


@pytest.fixture
def registry() -> CommandRegistry:
    return CommandRegistry()