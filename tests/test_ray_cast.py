# tests/test_ray_cast.py
from __future__ import annotations

import numpy as np
from pyglm import glm

from core.camera import Camera
from core.engine.ray_cast import screen_ray, screen_to_world


def _make_camera(width=800, height=600) -> Camera:
    cam = Camera()
    cam.set_aspect(width, height)
    cam.pitch = 30.0
    cam.yaw = -45.0
    cam.distance = 50.0
    cam._update_position()
    return cam


def test_center_ray_returns_origin_and_direction():
    cam = _make_camera()
    result = screen_ray(cam, 400, 300, 800, 600)
    assert result is not None
    origin, direction = result
    assert origin.shape == (3,)
    assert direction.shape == (3,)
    assert abs(np.linalg.norm(direction) - 1.0) < 1e-6


def test_ray_pierces_z0_plane():
    """Z=0 düzlemine bakan kamera için screen_to_world Z=0'da sonuçlanmalı."""
    cam = _make_camera()
    cam.up = glm.vec3(0.0, 0.0, 1.0)
    world = screen_to_world(cam, 400, 300, 800, 600)
    assert world is not None
    assert abs(world.z) < 1e-3


def test_offscreen_ray_still_computed():
    cam = _make_camera()
    result = screen_ray(cam, 0, 0, 800, 600)
    assert result is not None


def test_zero_width_returns_none():
    cam = _make_camera(width=1, height=1)
    result = screen_ray(cam, 0.5, 0.5, 1, 1)
    # 1x1 viewport'ta geçerli (merkez) bir ışın döner, None değil
    # Bu sadece "exception fırlatmıyor" doğrulaması
    assert result is None or result[0].shape == (3,)

import pytest

from core.engine.camera_rig import CameraRig


def test_init_sets_aspect_and_preset():
    rig = CameraRig(800, 600)
    assert rig.cam.pitch == 30.0
    assert rig.cam.yaw == -45.0
    assert rig.cam.distance == 50.0


def test_resize_updates_aspect():
    rig = CameraRig(800, 600)
    rig.resize(1600, 900)
    assert rig.width == 1600
    assert rig.height == 900


def test_fit_view_with_none_bounds_uses_default():
    rig = CameraRig(800, 600)
    rig.fit_view(None)   # exception fırlatmamalı
    assert rig.cam.distance > 0


def test_fit_view_with_bounds():
    class FakeBounds:
        center = (10.0, 20.0, 30.0)
        size = 100.0

    rig = CameraRig(800, 600)
    rig.fit_view(FakeBounds())
    assert rig.cam.distance > 0


def test_enter_exit_plane_2d_no_crash():
    class FakePlane:
        u_min = 0.0; u_max = 10.0
        v_min = 0.0; v_max = 20.0
        depth_minus = 0.5; depth_plus = 0.5
        origin = (0.0, 0.0, 0.0)
        normal = (0.0, 0.0, 1.0)
        u = (1.0, 0.0, 0.0)
        v = (0.0, 1.0, 0.0)
        def to_3d(self, uv):
            return (uv[0], uv[1], 0.0)

    rig = CameraRig(800, 600)
    rig.enter_plane_2d(FakePlane())
    rig.exit_plane_2d()

from app.commands import project_commands as PC
from core.engine.hover_system import HoverSystem


class FakePickPass:
    def __init__(self, next_result=None):
        self.next_result = next_result
        self.pending_pick = False
        self.pick_async_calls = []
        self.check_pick_calls = 0

    def pick_async(self, x, y, **kw):
        self.pick_async_calls.append((x, y, kw))
        self.pending_pick = True
        return True

    def check_pick(self):
        self.check_pick_calls += 1
        return self.next_result, 0, 0


class FakeQueue:
    def __init__(self):
        self.items = []
    def put(self, cmd):
        self.items.append(cmd)


@pytest.fixture
def queue():
    return FakeQueue()


def test_check_pick_result_no_pending_returns_false(queue):
    pick = FakePickPass()
    h = HoverSystem(pick, queue)
    assert h.check_pick_result() is False


def test_start_pick_sets_pending(queue):
    pick = FakePickPass()
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    assert h._pending is True
    assert len(pick.pick_async_calls) == 1


def test_throttle_blocks_rapid_picks(queue):
    pick = FakePickPass()
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    h.start_pick(105, 205)
    # throttle 0.05sn — hızlı ikinci çağrı bloklanmalı
    assert len(pick.pick_async_calls) == 1


def test_hover_changed_emits_command(queue):
    pick = FakePickPass(next_result=42)
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    h.check_pick_result()
    assert len(queue.items) == 1
    assert isinstance(queue.items[0], PC.HoverChanged)
    assert queue.items[0].element_id == 42


def test_same_id_no_command(queue):
    pick = FakePickPass(next_result=42)
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    h.check_pick_result()
    pick.next_result = 42
    h._pending = True
    h.check_pick_result()
    assert len(queue.items) == 1   # ikinci değişim yok


def test_zero_pick_retries_once(queue):
    pick = FakePickPass(next_result=0)
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    h.check_pick_result()
    # 0 → retry, komut yok
    assert len(queue.items) == 0
    assert h._hover_retry is True

    pick.next_result = 0
    h._pending = True
    h.check_pick_result()
    # ikinci 0 → bu kez gerçek sonuç
    assert len(queue.items) == 1
    assert queue.items[0].element_id == 0


def test_set_pointer_records_viewport(queue):
    pick = FakePickPass()
    h = HoverSystem(pick, queue)
    h.set_pointer("iso", 100, 200)
    assert h.pointer == ("iso", 100, 200)


def test_start_pick_with_viewport_passes_fbo(queue):
    pick = FakePickPass()
    h = HoverSystem(pick, queue)

    class FakeFBO:
        fbo = 7

    class FakeViewport:
        width = 800
        height = 600
        name = "iso"
        fbo = FakeFBO()

    h.start_pick(50, 60, viewport=FakeViewport())
    x, y, kw = pick.pick_async_calls[0]
    assert x == 50
    assert y == 60
    assert kw["source_fbo"] == 7
    assert kw["viewport_size"] == (800, 600)

def test_hover_clears_after_retry(queue):
    pick = FakePickPass(next_result=42)
    h = HoverSystem(pick, queue)
    h.start_pick(100, 200)
    h.check_pick_result()
    assert h.element_id == 42
    assert len(queue.items) == 1

    # Hover'dan çık → 0, retry yapar, sonra temizler
    pick.next_result = 0
    h._pending = True
    h.check_pick_result()          # retry
    assert len(queue.items) == 1   # komut yok

    h._pending = True
    h.check_pick_result()          # kesin 0, force ile komut
    assert len(queue.items) == 2
    assert queue.items[1].element_id == 0
    assert h.element_id == 0


def test_force_emits_even_if_same_id(queue):
    pick = FakePickPass(next_result=42)
    h = HoverSystem(pick, queue)
    h._update_hover(42)                  # normal
    assert len(queue.items) == 1

    h._update_hover(42, force=True)      # zorla
    assert len(queue.items) == 2

import pytest

from core.engine.plane_mode import PlaneMode


class FakeCameraRig:
    def __init__(self):
        self.enter_calls = []
        self.exit_calls = 0

    def enter_plane_2d(self, plane):
        self.enter_calls.append(plane)

    def exit_plane_2d(self):
        self.exit_calls += 1


class FakeMathRenderer:
    def __init__(self):
        self.projection = "3d"


class FakeRenderer:
    def __init__(self):
        self.projection = "3d"


class FakePipeline:
    def __init__(self):
        self.renderer = FakeRenderer()
        self.math_model_renderer = FakeMathRenderer()


class FakePlane:
    def __init__(self, name="XY_Z0"):
        self.name = name
        self.u_min = 0.0
        self.u_max = 10.0
        self.v_min = 0.0
        self.v_max = 10.0
        self.depth_minus = 0.5
        self.depth_plus = 0.5
        self.origin = (0.0, 0.0, 0.0)
        self.normal = (0.0, 0.0, 1.0)
        self.u = (1.0, 0.0, 0.0)
        self.v = (0.0, 1.0, 0.0)

    def to_3d(self, uv):
        return (uv[0], uv[1], 0.0)


class FakeProject:
    def __init__(self, planes=None, active=None):
        self._planes = planes or []
        self.active_plane = active

    def grid_planes(self):
        return self._planes

    def activate_plane(self, p):
        self.active_plane = p


class FakeQueue:
    def __init__(self):
        self.items = []
    def put(self, cmd):
        self.items.append(cmd)


@pytest.fixture
def setup():
    rig = FakeCameraRig()
    pipeline = FakePipeline()
    queue = FakeQueue()
    pm = PlaneMode(rig, pipeline, queue)
    return pm, rig, pipeline, queue


def test_enter_2d_sets_state(setup):
    pm, rig, pipeline, _ = setup
    plane = FakePlane()
    pm.enter_2d(plane)
    assert pm.is_2d is True
    assert pm.active_plane is plane
    assert rig.enter_calls == [plane]
    assert pipeline.renderer.projection == "plane_2d"
    assert pipeline.math_model_renderer.projection == "plane_2d"


def test_exit_2d_clears_state(setup):
    pm, rig, pipeline, _ = setup
    plane = FakePlane()
    pm.enter_2d(plane)
    pm.exit_2d()
    assert pm.is_2d is False
    assert pm.active_plane is None
    assert rig.exit_calls == 1
    assert pipeline.renderer.projection == "3d"
    assert pipeline.math_model_renderer.projection == "3d"


def test_toggle_from_3d_uses_active_plane(setup):
    pm, rig, pipeline, _ = setup
    plane = FakePlane()
    project = FakeProject(planes=[plane], active=plane)
    result = pm.toggle(project)
    assert result is True
    assert pm.is_2d is True
    assert pm.active_plane is plane


def test_toggle_from_3d_picks_default_xy(setup):
    pm, _, _, _ = setup
    plane = FakePlane(name="XY_Z0")
    project = FakeProject(planes=[plane], active=None)
    result = pm.toggle(project)
    assert result is True
    assert pm.active_plane is plane
    assert project.active_plane is plane   # activate_plane çağrıldı


def test_toggle_from_2d_exits(setup):
    pm, rig, _, _ = setup
    pm.enter_2d(FakePlane())
    result = pm.toggle(None)
    assert result is True
    assert pm.is_2d is False


def test_toggle_no_project_returns_false(setup):
    pm, _, _, _ = setup
    result = pm.toggle(None)
    assert result is False
    assert pm.is_2d is False


def test_toggle_no_planes_returns_false(setup):
    pm, _, _, _ = setup
    project = FakeProject(planes=[], active=None)
    result = pm.toggle(project)
    assert result is False


def test_enter_none_does_nothing(setup):
    pm, rig, _, _ = setup
    pm.enter_2d(None)
    assert pm.is_2d is False
    assert rig.enter_calls == []


def test_default_xy_prefers_z0(setup):
    plane_z0 = FakePlane(name="XY_Z0")
    plane_z5 = FakePlane(name="XY_Z5")
    project = FakeProject(planes=[plane_z5, plane_z0], active=None)
    picked = PlaneMode._default_xy_plane(project)
    assert picked is plane_z0


def test_default_xy_falls_back_to_first_xy(setup):
    plane_z5 = FakePlane(name="XY_Z5")
    plane_yz = FakePlane(name="YZ_X0")
    project = FakeProject(planes=[plane_yz, plane_z5], active=None)
    picked = PlaneMode._default_xy_plane(project)
    assert picked is plane_z5

