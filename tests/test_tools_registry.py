# tests/test_tools_registry.py
from __future__ import annotations

import pytest

from core.engine.tools_registry import ToolsRegistry


class FakeRenderer:
    def __init__(self):
        self.snap = None
    def set_snap(self, snap):
        self.snap = snap


class FakePipeline:
    def __init__(self):
        self.renderer = FakeRenderer()


class FakeInput:
    modifiers = 0


class FakeEngine:
    def __init__(self):
        self.input = FakeInput()
        self.pipeline = FakePipeline()


# Fake fabrikalar — argümanları yutar, dummy döndürür
def _fake_factory(*args, **kwargs):
    return object()


@pytest.fixture
def tools():
    eng = FakeEngine()
    tr = ToolsRegistry(eng)
    tr._factory_sel_policy = _fake_factory
    tr._factory_sel_mgr = _fake_factory
    tr._factory_marquee = _fake_factory
    tr._factory_edit = _fake_factory
    tr._factory_draw_mgr = _fake_factory
    tr._factory_plane_draw_mgr = _fake_factory
    tr._factory_snap = _fake_factory
    return tr, eng


def test_build_creates_all_tools(tools):
    tr, eng = tools
    tr.build()
    assert tr.sel_policy is not None
    assert tr.sel_mgr is not None
    assert tr.marquee is not None
    assert tr.edit is not None
    assert tr.draw_mgr is not None
    assert tr.plane_draw_mgr is not None
    assert tr.snap is not None


def test_build_attaches_snap_to_renderer(tools):
    tr, eng = tools
    tr.build()
    assert eng.pipeline.renderer.snap is tr.snap


def test_tick_no_crash(tools):
    tr, _ = tools
    tr.build()
    tr.tick()