# render/polygonrenderer.py
from __future__ import annotations

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from domain.polygon import Polygon
from geometry.polygon_builder import PolygonBuilder
from render.base_renderer import BaseRenderer, _final_color_for


class PolygonRenderer(BaseRenderer[Polygon]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = PolygonBuilder()
        self.vertex_stride = 6 * 4
        self.has_center = False
        self.simple_draw_mode = GL_TRIANGLES

    def build(self, p):
        return self.builder.build(p)

    def build_lines(self, p):
        return self.builder.build_lines(p)

    def build_simple(self, p):
        v = self.builder.build_simple(p)
        if v is None or len(v) == 0:
            return (np.array([], dtype=np.float32),
                    np.array([], dtype=np.float32))
        vc = len(v) // 6
        c = np.tile(_final_color_for(p)[:3], (vc, 1)).astype(np.float32)
        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def render_pick(self, mvp, pick_shader, visible_ids=None):
        if not self.simple_vao or self.simple_vcount == 0 or not pick_shader:
            return
        pick_shader.use()
        loc = pick_shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        glBindVertexArray(self.simple_vao)
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-1.0, -1.0)
        if visible_ids is None:
            glDrawArrays(self.simple_draw_mode, 0, self.simple_vcount)
        else:
            offset = 0
            for e in self.elements:
                vc_ = self.elem_to_simple_vcount.get(e.unique_id, 0)
                if vc_ == 0:
                    continue
                if e.unique_id in visible_ids:
                    glDrawArrays(self.simple_draw_mode, offset, vc_)
                offset += vc_
        glDisable(GL_POLYGON_OFFSET_FILL)
        glBindVertexArray(0)