# render/node_renderer.py
"""NodeRenderer — shaded mesh ve simple noktaları çizer.

Node'un görsel özellikleri (küp, restraint sembolleri) NodeBuilder tarafından
üretilir. Bu sınıf sadece GPU buffer yönetimi ve render yapar.

Shaded: standard.vert, isConstantSize=1
    → aCenter + aPos*factor (ekran boyutu sabit, doğru konum)
Simple: node.vert, GL_POINTS
    → aPos global (aCenter = aPos olarak doldurulur)
"""
from __future__ import annotations

import ctypes

import glm
import numpy as np
from OpenGL.GL import *

from domain.element import Node
from geometry.node_builder import NodeBuilder
from render.base_renderer import BaseRenderer, _final_color_for


class NodeRenderer(BaseRenderer[Node]):
    """Node mesh'lerini ve noktalarını çizer."""

    # ---- Simple modda nokta boyutu (piksel) ----
    DEFAULT_POINT_SIZE = 4.0

    # ---- Shaded mesh için sabit ekran boyutu ölçeği ----
    POINT_SCALE = 0.002

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = NodeBuilder()

        # Vertex layout: pos3 + normal3 + center3 = 9 float
        self.vertex_stride = 9 * 4
        self.has_center = True
        self.simple_draw_mode = GL_POINTS

        # Basit modda nokta boyutu
        self.point_size = self.DEFAULT_POINT_SIZE
        # Simple restraint çizgileri için ayrı buffer
        self.rlines_vao = None
        self.rlines_vbo = None
        self.rlines_cbo = None
        self.rlines_idbo = None
        self.rlines_vcount = 0

    # ==================================================================
    # PUBLIC API
    # ==================================================================
    def set_node_size(self, size: float) -> bool:
        """Shaded mesh boyutu (dünya birimi → ekran oranı). True → değişti."""
        return self.builder.set_size(size)

    def set_point_size(self, px: float) -> bool:
        """Simple modda piksel boyutu. True → değişti."""
        px = float(px)
        if px <= 0 or abs(self.point_size - px) < 1e-6:
            return False
        self.point_size = px
        return True

    # ==================================================================
    # BUILD (BaseRenderer abstract)
    # ==================================================================
    def build(self, n: Node):
        return self.builder.build(n)

    def build_simple(self, n: Node):
        v = self.builder.build_simple_points(n)
        c = np.array([_final_color_for(n)], dtype=np.float32)
        return v, c

    def draw_mode(self) -> int:
        return GL_TRIANGLES

    # ==================================================================
    # SHADED RENDER
    # ==================================================================
    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        if not self.vao or self.icount == 0:
            return
        if model is None:
            model = glm.mat4(1.0)

        sh = self.shader
        sh.use()

        # --- Uniform'lar ---
        loc = sh.get_loc("pointSize")
        if loc != -1:
            glUniform1f(loc, self.point_size)

        loc = sh.get_loc("alpha")
        if loc != -1:
            glUniform1f(loc, 1.0)

        # isConstantSize=1 → aCenter + aPos*factor (doğru konum + sabit ekran boyutu)
        loc = sh.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 1)

        loc = sh.get_loc("pointScale")
        if loc != -1:
            glUniform1f(loc, self.POINT_SCALE)

        # --- Base render (mvp, model, normalMatrix, view, proj, useVertexColor) ---
        super().render(mvp, model, cam_pos, view, proj)

    # ==================================================================
    # SIMPLE RENDER
    # ==================================================================
    def render_simple(self, mvp, shader, color=None, alpha=0.5):
        if not self.simple_vao or self.simple_vcount == 0:
            return
        sh = shader or self.shader
        sh.use()

        loc = sh.get_loc("pointSize")
        if loc != -1:
            glUniform1f(loc, self.point_size)

        loc = sh.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

        glBindVertexArray(self.simple_vao)
        glEnable(GL_PROGRAM_POINT_SIZE)
        glDrawArrays(GL_POINTS, 0, self.simple_vcount)
        glDisable(GL_PROGRAM_POINT_SIZE)
        glBindVertexArray(0)

    def update(self, raw):
        super().update(raw)
        self._build_restraint_lines()

    def _build_restraint_lines(self):
        """Restraint'li node'lar için simple çizgiler üret."""
        all_v = []
        all_c = []
        all_id = []

        for node in self.elements:
            v = self.builder.build_simple_restraint_lines(node)
            if len(v) == 0:
                continue
            vc = len(v) // 6
            color = _final_color_for(node)
            all_v.append(v)
            all_c.append(np.tile(np.array(color[:3], dtype=np.float32), (vc, 1)))
            all_id.append(np.full(vc, node.unique_id, dtype=np.uint32))

        if not all_v:
            self._cleanup_rlines()
            return

        self._upload_rlines(
            np.concatenate(all_v),
            np.concatenate(all_c),
            np.concatenate(all_id),
        )

    def _upload_rlines(self, v, c, ids):
        self._cleanup_rlines()
        if len(v) == 0:
            return

        self.rlines_vao  = glGenVertexArrays(1)
        self.rlines_vbo  = glGenBuffers(1)
        self.rlines_cbo  = glGenBuffers(1)
        self.rlines_idbo = glGenBuffers(1)

        glBindVertexArray(self.rlines_vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.rlines_vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))

        glBindBuffer(GL_ARRAY_BUFFER, self.rlines_cbo)
        glBufferData(GL_ARRAY_BUFFER, c.nbytes, c, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

        glBindBuffer(GL_ARRAY_BUFFER, self.rlines_idbo)
        glBufferData(GL_ARRAY_BUFFER, ids.nbytes, ids, GL_STATIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, ctypes.c_void_p(0))

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.rlines_vcount = len(v) // 6

    def _cleanup_rlines(self):
        for buf in (self.rlines_vbo, self.rlines_cbo, self.rlines_idbo):
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])
        if self.rlines_vao and glIsVertexArray(self.rlines_vao):
            glDeleteVertexArrays(1, [int(self.rlines_vao)])
        self.rlines_vao = self.rlines_vbo = self.rlines_cbo = self.rlines_idbo = None
        self.rlines_vcount = 0

    def render_simple_restraint_lines(self, mvp, shader, alpha=1.0):
        """GL_LINES ile restraint sembolleri çiz."""
        if self.rlines_vcount == 0 or not self.rlines_vao:
            return
        sh = shader or self.shader
        sh.use()

        loc = sh.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

        loc = sh.get_loc("useVertexColor")
        if loc != -1:
            glUniform1i(loc, 1)

        loc = sh.get_loc("alpha")
        if loc != -1:
            glUniform1f(loc, float(alpha))

        glBindVertexArray(self.rlines_vao)
        glDrawArrays(GL_LINES, 0, self.rlines_vcount)
        glBindVertexArray(0)

    def cleanup(self):
        self._cleanup_rlines()
        super().cleanup()