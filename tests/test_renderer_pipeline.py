# tests/test_renderer_pipeline.py
import pytest


def _has_gl() -> bool:
    try:
        from OpenGL.GL import glGetString, GL_VERSION
        return glGetString(GL_VERSION) is not None
    except Exception:
        return False


def test_class_importable():
    from core.engine.renderer_pipeline import RendererPipeline
    assert RendererPipeline is not None


def test_get_element_by_id_none_renderer():
    from core.engine.renderer_pipeline import RendererPipeline

    class Stub:
        renderer = None

    assert RendererPipeline.get_element_by_id(Stub(), 42) is None


def test_fit_view_bounds_empty():
    from core.engine.renderer_pipeline import RendererPipeline

    class Stub:
        scene = None
        math_model = None

    assert RendererPipeline.fit_view_bounds(Stub()) is None


def test_in_section_no_renderer_true():
    from core.engine.renderer_pipeline import RendererPipeline

    class Stub:
        renderer = None
        @property
        def math_model_renderer(self):
            return None

    assert RendererPipeline.in_section(Stub(), None, None, None) is True


def test_iter_render_elements_empty():
    from core.engine.renderer_pipeline import RendererPipeline

    class Stub:
        renderer = None
        @property
        def math_model_renderer(self):
            return None

    items = list(RendererPipeline.iter_render_elements(Stub()))
    assert items == []


@pytest.mark.skipif(not _has_gl(), reason="OpenGL context yok")
def test_pipeline_build_with_real_gl():
    from core.engine.gl_context import GLContext
    from core.engine.renderer_pipeline import RendererPipeline
    from render.snapsquare import SnapSquareRenderer

    ctx = GLContext(800, 600)
    ctx.init()
    snap = SnapSquareRenderer()
    pipeline = RendererPipeline(800, 600, ctx.shaders, snap)
    assert pipeline.renderer is not None
    assert pipeline.pick_pass is not None
    assert pipeline.presentation is not None
    assert pipeline.interaction is not None