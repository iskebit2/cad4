# tests/test_engine_fasad.py
import pytest


def _has_gl() -> bool:
    try:
        from OpenGL.GL import glGetString, GL_VERSION
        return glGetString(GL_VERSION) is not None
    except Exception:
        return False


def test_engine_class_importable():
    from core.engine import Engine
    assert Engine is not None


def test_engine_init_creates_components_without_gl():
    from core.engine import Engine
    from app.commands.command_queue import CommandQueue

    class FakeQueue:
        def put(self, cmd): pass
        def drain(self): return []

    eng = Engine(800, 600, FakeQueue())
    assert eng.w == 800
    assert eng.h == 600
    assert eng.camera_rig is not None
    assert eng.gl is not None
    assert eng.input is not None
    assert eng.pipeline is None    # init_gl'ye kadar
    assert eng.tools is None
    assert eng.hover is None


def test_engine_resize():
    from core.engine import Engine

    class FakeQueue:
        def put(self, cmd): pass

    eng = Engine(800, 600, FakeQueue())
    eng.resize(1600, 900)
    assert eng.w == 1600
    assert eng.h == 900
    assert eng.camera_rig.width == 1600


def test_engine_property_delegations_none():
    from core.engine import Engine

    class FakeQueue:
        def put(self, cmd): pass

    eng = Engine(800, 600, FakeQueue())
    # init_gl öncesi delegasyonlar None döner
    assert eng.renderer is None
    assert eng.pick_pass is None
    assert eng.sel_mgr is None
    assert eng.hover_id == 0
    assert eng.pending_pick_check is False


@pytest.mark.skipif(not _has_gl(), reason="OpenGL context yok")
def test_engine_init_gl_with_real_gl():
    from core.engine import Engine

    class FakeQueue:
        def put(self, cmd): pass

    eng = Engine(800, 600, FakeQueue())
    eng.init_gl()
    assert eng.pipeline is not None
    assert eng.tools is not None
    assert eng.hover is not None
    assert eng.plane_mode is not None