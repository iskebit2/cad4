# tests/test_definitions.py
from __future__ import annotations

from app.commands import definitions
from core.commands import project_commands as PC
from domain.definition import Section


def test_add_section(fake_app, registry):
    definitions.register(registry)

    section = Section(name="S1")
    cmd = PC.AddDefinition("sections", "S1", section)
    result = registry.dispatch(fake_app, cmd)

    assert result.handled
    assert result.project_dirty
    assert not result.geometry_dirty
    assert "S1" in fake_app.current_project.sections


def test_update_unknown_section(fake_app, registry):
    definitions.register(registry)

    cmd = PC.UpdateDefinition("sections", "NOPE", {"h": 1.0})
    result = registry.dispatch(fake_app, cmd)

    assert not result.handled