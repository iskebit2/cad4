# render/line_renderer.py
from __future__ import annotations

import ctypes

import numpy as np
from OpenGL.GL import *
from pyglm import glm
from render.base_renderer import _final_color_for

class LineRenderer:
    STRIDE = 24

    def __init__(self, shader):
        self.shader = shader
        self.vao = None
        self.vbo = None
        self.vcount = 0

    def update(self, lines):
        verts, ids = [], []
        for ln in lines:
            if not getattr(ln, "visible", True):
                continue
            c = _final_color_for(ln)[:3]
            verts += [ln.v1.x, ln.v1.y, ln.v1.z, *c,
                    ln.v2.x, ln.v2.y, ln.v2.z, *c]
            ids += [ln.unique_id, ln.unique_id]
        if not verts:
            self._cleanup()
            return
        data = np.array(verts, np.float32)
        id_data = np.array(ids, np.uint32)
        if self.vao is None:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)
            self.idbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.STRIDE, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self.STRIDE, ctypes.c_void_p(12))
        glBindBuffer(GL_ARRAY_BUFFER, self.idbo)
        glBufferData(GL_ARRAY_BUFFER, id_data.nbytes, id_data, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, ctypes.c_void_p(0))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.vcount = len(verts) // 6

    def draw(self, mvp):
        
        if not self.vcount or self.shader is None:
            return
        
        glDisable(GL_DEPTH_TEST)
        self.shader.use()
        loc = self.shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        vc = self.shader.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 1)
        a = self.shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 1.0)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_LINES, 0, self.vcount)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def _cleanup(self):
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None
        self.vcount = 0

    def cleanup(self):
        self._cleanup()