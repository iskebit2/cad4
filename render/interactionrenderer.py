# render/interactionrenderer.py
from __future__ import annotations

import numpy as np
from pyglm import glm
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)

class InteractionRenderer:
    """
    Kullanıcı etkileşiminin anlık görselleri (Interaction Layer):
    - Seçim Kutusu (Marquee)
    - Yakalama İşaretçileri (SnapMarker)
    - Çizim Önizlemeleri (DrawingPreview)
    """
    def __init__(self, overlay_shader):
        self.overlay_shader = overlay_shader
        self._overlay_mvp_loc = overlay_shader.get_loc("mvp") if overlay_shader else -1
        self._overlay_color_loc = overlay_shader.get_loc("color") if overlay_shader else -1

        # Marquee (seçim dikdörtgeni) için buffer'lar
        self._marquee_ov_vao = None
        self._marquee_ov_vbo = None

    def render(self, engine, w, h):
        """Tüm etkileşim ve anlık preview görsellerini çizer."""
        if not engine:
            return

        # 1. Marquee (Seçim Kutusu) Çizimi
        if engine.marquee and engine.marquee.is_active:
            self._draw_marquee(engine.marquee, w, h)

        # 2. Snap (Yakalama) Göstergesi
        if engine.snap and getattr(engine, "hover_visual_enabled", True):
            self._draw_snap(engine, w, h)

        # 3. Çizim Önizlemesi (DrawingPreview)
        if engine.draw_mgr and engine.draw_mgr.is_active:
            mvp = engine.cam.get_projection_matrix() @ engine.cam.get_view_matrix()
            engine.draw_mgr.render_preview(mvp, engine.preview_s)

    def _draw_marquee(self, marquee, w, h):
        coords = marquee.get_box_coords()
        if not coords:
            return
        x1, y1, x2, y2 = coords
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        cross = x2 < x1

        if self._marquee_ov_vao is None:
            self._marquee_ov_vao = glGenVertexArrays(1)
            self._marquee_ov_vbo = glGenBuffers(1)
            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glBindVertexArray(0)

        depth_was_on = glIsEnabled(GL_DEPTH_TEST) != 0
        blend_was_on = glIsEnabled(GL_BLEND) != 0
        lw_prev = glGetFloatv(GL_LINE_WIDTH)

        try:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            self.overlay_shader.use()
            proj = glm.ortho(0.0, float(w), float(h), 0.0, -1.0, 1.0)
            if self._overlay_mvp_loc != -1:
                glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(proj))
            if self._overlay_color_loc == -1:
                return

            mn_x, mx_x = min(x1, x2), max(x1, x2)
            mn_y, mx_y = min(y1, y2), max(y1, y2)
            verts = np.array([mn_x, mn_y, 0, mx_x, mn_y, 0,
                              mx_x, mx_y, 0, mn_x, mx_y, 0], dtype=np.float32)

            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)

            if cross:
                fill, border = (0.2, 0.8, 0.2, 0.3), (0.2, 1.0, 0.2, 0.9)
            else:
                fill, border = (0.2, 0.5, 0.9, 0.3), (0.4, 0.7, 1.0, 0.9)

            glUniform4f(self._overlay_color_loc, *fill)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

            glLineWidth(1.5)
            glUniform4f(self._overlay_color_loc, *border)
            glDrawArrays(GL_LINE_LOOP, 0, 4)
        finally:
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glLineWidth(float(lw_prev))
            if not blend_was_on:
                glDisable(GL_BLEND)
            if depth_was_on:
                glEnable(GL_DEPTH_TEST)

    def _draw_snap(self, engine, w, h):
        snap = engine.snap
        if not engine.draw_mgr or not (engine.draw_mgr.is_active or engine.hover_id > 0):
            return

        if engine.draw_mgr.is_active:
            hover = engine.draw_mgr.hover_node
            if hover is not None:
                cam = engine.cam
                mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
                clip = mvp * glm.vec4(hover.x, hover.y, hover.z, 1.0)
                if clip.w > 0:
                    ndc = glm.vec3(clip) / clip.w
                    nx = (ndc.x + 1.0) * w / 2.0
                    ny = (1.0 - ndc.y) * h / 2.0
                    snap.draw_snap(nx, ny, w, h, active=True, hover_node=True)
                    return

        mx = engine.input.mouse_pos.x
        my = engine.input.mouse_pos.y
        snap.draw_snap(
            mx, my, w, h, active=True,
            hover_node=False,
        )

    def cleanup(self):
        if self._marquee_ov_vao and glIsVertexArray(self._marquee_ov_vao):
            glDeleteVertexArrays(1, [self._marquee_ov_vao])
        if self._marquee_ov_vbo and glIsBuffer(self._marquee_ov_vbo):
            glDeleteBuffers(1, [self._marquee_ov_vbo])