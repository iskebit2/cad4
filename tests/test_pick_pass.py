# tests/test_pick_pass.py
from __future__ import annotations

import pytest
import glfw
from OpenGL.GL import *

from core.mrt import MRTFramebuffer


@pytest.fixture(scope="module")
def gl_context():
    if not glfw.init():
        pytest.skip("GLFW başlatılamadı")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    window = glfw.create_window(64, 64, "test", None, None)
    if not window:
        glfw.terminate()
        pytest.skip("Pencere oluşturulamadı")
    glfw.make_context_current(window)
    yield window
    glfw.destroy_window(window)
    glfw.terminate()


def test_mrt_id_write_read(gl_context):
    """MRT ID attachment'a yazıp okuyabiliyor muyuz?"""
    w, h = 64, 64
    mrt = MRTFramebuffer(w, h)
    mrt.bind()
    mrt.clear()

    glDrawBuffer(GL_COLOR_ATTACHMENT1)
    glClearBufferuiv(GL_COLOR, 0, [42, 0, 0, 0])
    glFlush()
    glDrawBuffer(GL_COLOR_ATTACHMENT0)

    glBindFramebuffer(GL_READ_FRAMEBUFFER, mrt.fbo)
    glReadBuffer(GL_COLOR_ATTACHMENT1)
    data = glReadPixels(32, 32, 1, 1, GL_RED_INTEGER, GL_UNSIGNED_INT)
    glReadBuffer(GL_NONE)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)

    val = int.from_bytes(data, "little")
    assert val == 42, f"MRT ID okuma yanlış: {val} != 42"