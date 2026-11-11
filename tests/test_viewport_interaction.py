from types import SimpleNamespace

from core.marquee_selector import MarqueeSelector
from core import mrt as mrt_module
from core.mrt import MRTFramebuffer
from render import pickpass as pickpass_module
from render.interactionrenderer import InteractionRenderer
from render.pickpass import PickPass


def test_marquee_uses_viewport_dimensions():
    engine = SimpleNamespace(w=1920, h=1080)
    selector = MarqueeSelector(engine, None, None)

    selector.start_selection(25, 30, camera=object(), viewport_size=(400, 300))
    selector.update_selection(125, 130)

    rect = selector._get_rect()

    assert rect == (25.0, 30.0, 125.0, 130.0, False, 400.0, 300.0)
    assert selector._selection_camera is not None


def test_async_pick_reads_viewport_fbo_and_coordinates(monkeypatch):
    pick = object.__new__(PickPass)
    pick.pending_pick = False
    pick.pick_timeout = 0.5
    pick.current_pbo = 0
    pick.read_pbo = 1
    pick.pbos = [12, 13]
    pick.pick_size = 3
    pick.pick_half = 1
    pick.viewport_width = 1920
    pick.viewport_height = 1080

    calls = {}
    monkeypatch.setattr(
        pickpass_module, "glBindFramebuffer",
        lambda target, fbo: calls.setdefault("framebuffers", []).append((target, fbo)),
    )
    monkeypatch.setattr(pickpass_module, "glReadBuffer", lambda value: None)
    monkeypatch.setattr(pickpass_module, "glBindBuffer", lambda target, value: None)
    monkeypatch.setattr(pickpass_module, "glPixelStorei", lambda target, value: None)
    monkeypatch.setattr(
        pickpass_module, "glReadPixels",
        lambda x, y, width, height, fmt, typ, offset: calls.update(
            pixels=(x, y, width, height)
        ),
    )

    assert pick.pick_async(100, 50, source_fbo=77, viewport_size=(200, 100))

    assert calls["framebuffers"][0] == (
        pickpass_module.GL_READ_FRAMEBUFFER, 77,
    )
    assert calls["pixels"] == (99, 48, 3, 3)
    assert pick.pending_pick
    assert (pick.pending_x, pick.pending_y) == (100, 50)


def test_mrt_clear_targets_integer_id_attachment(monkeypatch):
    framebuffer = object.__new__(MRTFramebuffer)
    framebuffer.bind = lambda: None
    calls = []
    monkeypatch.setattr(mrt_module, "glDrawBuffer", calls.append)
    monkeypatch.setattr(mrt_module, "glClearColor", lambda *args: None)
    monkeypatch.setattr(mrt_module, "glClear", lambda *args: None)
    monkeypatch.setattr(
        mrt_module, "glClearBufferuiv",
        lambda buffer, index, values: calls.append((buffer, index)),
    )

    framebuffer.clear()

    assert calls == [
        mrt_module.GL_COLOR_ATTACHMENT0,
        mrt_module.GL_COLOR_ATTACHMENT1,
        (mrt_module.GL_COLOR, 0),
        mrt_module.GL_COLOR_ATTACHMENT0,
    ]


def test_interaction_renderer_targets_matching_viewport_and_pointer():
    renderer = object.__new__(InteractionRenderer)
    renderer.preview_plane = None
    calls = []
    renderer._draw_marquee = lambda marquee, width, height: calls.append(
        ("marquee", width, height)
    )
    renderer._draw_snap = lambda engine, width, height, camera, mouse: calls.append(
        ("snap", camera, mouse)
    )
    camera = object()
    marquee = SimpleNamespace(is_active=True, viewport_name="front")
    engine = SimpleNamespace(
        cam=None,
        input=None,
        marquee=marquee,
        snap=object(),
        hover_visual_enabled=True,
        draw_mgr=None,
        plane_draw_mgr=None,
    )

    renderer.render(
        engine, 400, 300, camera=camera,
        viewport_name="front", mouse_pos=(50, 60),
    )
    assert calls == [
        ("marquee", 400, 300),
        ("snap", camera, (50, 60)),
    ]

    calls.clear()
    renderer.render(
        engine, 400, 300, camera=camera,
        viewport_name="top", mouse_pos=(20, 30),
    )
    assert calls == [("snap", camera, (20, 30))]
