# tests/test_gl_context.py
import pytest
from OpenGL.GL import glGetString, GL_VERSION

def test_shader_names_not_empty():
    from core.engine.gl_context import SHADER_NAMES
    assert len(SHADER_NAMES) >= 8


def test_init_creates_dict_but_requires_gl():
    """GL context olmadan init() çağırma — sadece yapı testi."""
    from core.engine.gl_context import GLContext
    ctx = GLContext(800, 600)
    assert ctx.shaders == {}
    assert ctx._initialized is False


def test_resize():
    from core.engine.gl_context import GLContext
    ctx = GLContext(800, 600)
    ctx.resize(1600, 900)
    assert ctx.width == 1600
    assert ctx.height == 900


@pytest.mark.skipif(
    pytest.importorskip("OpenGL").glGetString(GL_VERSION) is None,
    reason="GL context yok",
)
def test_init_loads_shaders():
    from core.engine.gl_context import GLContext
    ctx = GLContext(800, 600)
    ctx.init()
    assert ctx.get("standard") is not None