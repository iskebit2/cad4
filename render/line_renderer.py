# render/line_renderer.py
from __future__ import annotations

import ctypes
import numpy as np
from OpenGL.GL import *
from pyglm import glm
from domain.line import Line
from render.base_renderer import BaseRenderer, _final_color_for


class LineRenderer(BaseRenderer[Line]):

    def __init__(self, shader):
        super().__init__(shader)
        self.vertex_stride = 6 * 4   # pos3 + color3
        self.has_center = False
        self.simple_draw_mode = GL_LINES

    def _line_verts(self, ln):
        return np.array([
            ln.v1.x, ln.v1.y, ln.v1.z, 0.0, 0.0, 0.0,
            ln.v2.x, ln.v2.y, ln.v2.z, 0.0, 0.0, 0.0,
        ], dtype=np.float32)

    def build(self, ln):
        v = self._line_verts(ln)
        c = np.tile(_final_color_for(ln)[:3], (2, 1)).astype(np.float32)
        i = np.array([0, 1], dtype=np.uint32)
        return v, c, i

    def build_simple(self, ln):
        v = self._line_verts(ln)
        c = np.tile(_final_color_for(ln)[:3], (2, 1)).astype(np.float32)
        return v, c

    def draw_mode(self):
        return GL_LINES

    # ------------------------------------------------------------------
    def draw(self, mvp, visible_ids=None):
        """Eski API uyumluluğu — MathModelRenderer kullanıyor."""
        if not self.simple_vao or self.simple_vcount == 0:
            return
        shader = self.shader
        if shader is None:
            return
        glDisable(GL_DEPTH_TEST)
        shader.use()
        loc = shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        vc = shader.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 1)
        a = shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 1.0)
        glBindVertexArray(self.simple_vao)
        if visible_ids is None:
            glDrawArrays(GL_LINES, 0, self.simple_vcount)
        else:
            offset = 0
            for e in self.elements:
                vc_ = self.elem_to_simple_vcount.get(e.unique_id, 0)
                if vc_ == 0:
                    continue
                if e.unique_id in visible_ids:
                    glDrawArrays(GL_LINES, offset, vc_)
                offset += vc_
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def render_pick(self, mvp, pick_shader, visible_ids=None):
        if not self.simple_vao or self.simple_vcount == 0 or not pick_shader:
            return
        pick_shader.use()
        loc = pick_shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        glBindVertexArray(self.simple_vao)
        if visible_ids is None:
            glDrawArrays(GL_LINES, 0, self.simple_vcount)
        else:
            offset = 0
            for e in self.elements:
                vc_ = self.elem_to_simple_vcount.get(e.unique_id, 0)
                if vc_ == 0:
                    continue
                if e.unique_id in visible_ids:
                    glDrawArrays(GL_LINES, offset, vc_)
                offset += vc_
        glBindVertexArray(0)