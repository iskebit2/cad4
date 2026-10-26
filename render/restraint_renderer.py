# render/restraint_renderer.py
from __future__ import annotations

import ctypes
from typing import List, Optional, Tuple

import glm
import numpy as np
from OpenGL.GL import *
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, GL_ELEMENT_ARRAY_BUFFER, GL_FALSE,
    GL_FLOAT, GL_STATIC_DRAW, GL_TRIANGLES, GL_UNSIGNED_INT,
    glBindBuffer, glBindVertexArray, glBufferData,
    glDeleteBuffers, glDeleteVertexArrays, glDrawElements,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glIsBuffer, glIsVertexArray, glUniform1f, glUniform1i,
    glUniform3f, glUniformMatrix3fv, glUniformMatrix4fv,
    glVertexAttribIPointer, glVertexAttribPointer,
)

from domain.element import Node
from geometry.node_builder import NodeBuilder
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ======================================================================
# Yardımcılar
# ======================================================================
def _v9_global_to_standard(v9: np.ndarray) -> np.ndarray:
    """
    9-float (pos3 local, normal3, center3) → 9-float (pos3 GLOBAL, normal3, center3=0).
    standard.vert else dalı `mvp * aPos` kullandığı için aPos global olmalı.
    """
    if len(v9) == 0:
        return v9
    out = v9.reshape(-1, 9).copy()
    out[:, 0:3] += out[:, 6:9]     # aPos += aCenter
    out[:, 6:9] = 0.0              # aCenter = 0
    return out.flatten()


def _v9_global_to_simple(v9_global: np.ndarray) -> np.ndarray:
    """
    9-float (pos3 GLOBAL, normal3, center3=0) → 6-float (pos3 GLOBAL, pad3).
    simple.vert `aPos`'u doğrudan kullanır.
    """
    if len(v9_global) == 0:
        return np.array([], dtype=np.float32)
    out = v9_global.reshape(-1, 9)
    v6 = np.zeros((out.shape[0], 6), dtype=np.float32)
    v6[:, 0:3] = out[:, 0:3]
    return v6.flatten()


# ======================================================================
# RestraintRenderer
# ======================================================================
class RestraintRenderer:
    """
    Node.restraint sembollerini çizer.

    İki ayrı buffer seti:
      - shaded : standard.vert uyumlu (aPos GLOBAL, aCenter=0, normal, color, pick_id)
      - simple : simple.vert uyumlu (aPos GLOBAL, color, pick_id)

    Her ikisi de EBO ile GL_TRIANGLES çizer.
    """

    # Vertex başına float sayısı
    STRIDE_MAIN_FLOATS   = 9   # pos3 + normal3 + center3
    STRIDE_SIMPLE_FLOATS = 6   # pos3 + pad3

    # Turuncu mesnet rengi
    COLOR = (1.0, 0.55, 0.1)

    def __init__(self, standard_shader, simple_shader):
        self.standard_shader = standard_shader
        self.simple_shader = simple_shader
        self.builder = NodeBuilder()

        # ---- Shaded buffer ----
        self.vao: Optional[int] = None
        self.vbo: Optional[int] = None
        self.cbo: Optional[int] = None
        self.id_vbo: Optional[int] = None
        self.ebo: Optional[int] = None
        self.icount: int = 0

        # ---- Simple buffer ----
        self.simple_vao: Optional[int] = None
        self.simple_vbo: Optional[int] = None
        self.simple_cbo: Optional[int] = None
        self.simple_idbo: Optional[int] = None
        self.simple_ebo: Optional[int] = None
        self.simple_icount: int = 0

        self.elements: List[Node] = []
        self.enabled: bool = True

    # ==================================================================
    # PUBLIC
    # ==================================================================
    def set_size(self, size: float) -> bool:
        return self.builder.set_size(size)

    def update(self, raw: List[Node], scene_size: float = 1.0):
        """
        Restraint'li node listesini al, iki buffer setini de yeniden üret.
        scene_size → sembol boyutu (sahnenin %2'si, min 1mm).
        """
        # --- Boyutu ÖNCE ayarla (buffer'lar yeni boyutla üretilsin) ---
        desired_size = max(scene_size * 0.02, 1.0)
        self.builder.set_size(desired_size)

        self.elements = [n for n in raw if n.is_visible]

        if not self.elements:
            self._cleanup_main()
            self._cleanup_simple()
            logger.debug("[RestraintRenderer] boş — buffer'lar temizlendi")
            return

        # --- Biriktiriciler ---
        main_v, main_c, main_id, main_i = [], [], [], []
        simple_v, simple_c, simple_id, simple_i = [], [], [], []

        main_voff = main_ioff = 0
        simple_voff = simple_ioff = 0

        color_np = np.array(self.COLOR, dtype=np.float32)

        for node in self.elements:
            v9_local, _, i9 = self.builder.build_restraint_only(node)
            if len(v9_local) == 0:
                continue

            vc = len(v9_local) // self.STRIDE_MAIN_FLOATS

            # --- Shaded: aPos'u global yap ---
            v9_global = _v9_global_to_standard(v9_local)
            main_i.append(i9 + main_voff)
            main_v.append(v9_global)
            main_c.append(np.tile(color_np, (vc, 1)))
            main_id.append(np.full(vc, node.unique_id, dtype=np.uint32))
            main_voff += vc
            main_ioff += len(i9)

            # --- Simple: 9-float global → 6-float ---
            v6 = _v9_global_to_simple(v9_global)
            simple_i.append(i9 + simple_voff)
            simple_v.append(v6)
            simple_c.append(np.tile(color_np, (vc, 1)))
            simple_id.append(np.full(vc, node.unique_id, dtype=np.uint32))
            simple_voff += vc
            simple_ioff += len(i9)

        # --- Upload ---
        if main_v:
            self._upload_main(
                np.concatenate(main_v),
                np.concatenate(main_c),
                np.concatenate(main_id),
                np.concatenate(main_i),
            )
            self.icount = main_ioff
        else:
            self._cleanup_main()

        if simple_v:
            self._upload_simple(
                np.concatenate(simple_v),
                np.concatenate(simple_c),
                np.concatenate(simple_id),
                np.concatenate(simple_i),
            )
            self.simple_icount = simple_ioff
        else:
            self._cleanup_simple()

        logger.debug(
            "[RestraintRenderer] elements=%d shaded_icount=%d simple_icount=%d size=%.1f",
            len(self.elements), self.icount, self.simple_icount, desired_size,
        )

    # ==================================================================
    # RENDER — shaded (standard_shader)
    # ==================================================================
    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        if not self.enabled or not self.vao or self.icount == 0:
            return
        if model is None:
            model = glm.mat4(1.0)

        sh = self.standard_shader
        sh.use()

        self._set_standard_uniforms(sh, mvp, model, cam_pos, view, proj)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(GL_TRIANGLES, self.icount, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # ==================================================================
    # RENDER — simple (simple_shader)
    # ==================================================================
    def render_simple(self, mvp, shader=None, alpha=1.0):
        if not self.enabled or not self.simple_vao or self.simple_icount == 0:
            return
        sh = shader or self.simple_shader
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

        glBindVertexArray(self.simple_vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.simple_ebo)
        glDrawElements(GL_TRIANGLES, self.simple_icount, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # ==================================================================
    # UNIFORMS
    # ==================================================================
    @staticmethod
    def _set_standard_uniforms(sh, mvp, model, cam_pos, view, proj):
        loc = sh.get_loc("renderMode")
        if loc != -1:
            glUniform1i(loc, 1)          # 1 = shaded

        glUniformMatrix4fv(sh.get_loc("mvp"), 1, GL_FALSE, glm.value_ptr(mvp))
        glUniformMatrix4fv(sh.get_loc("model"), 1, GL_FALSE, glm.value_ptr(model))

        nm = glm.transpose(glm.inverse(glm.mat3(model)))
        loc = sh.get_loc("normalMatrix")
        if loc != -1:
            glUniformMatrix3fv(loc, 1, GL_FALSE, glm.value_ptr(nm))

        if view is not None:
            loc = sh.get_loc("view")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(view))
        if proj is not None:
            loc = sh.get_loc("projection")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(proj))

        loc = sh.get_loc("useVertexColor")
        if loc != -1:
            glUniform1i(loc, 1)

        loc = sh.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 0)

        loc = sh.get_loc("alpha")
        if loc != -1:
            glUniform1f(loc, 1.0)

        loc = sh.get_loc("rimIntensity")
        if loc != -1:
            glUniform1f(loc, 0.80)
        loc = sh.get_loc("rimPower")
        if loc != -1:
            glUniform1f(loc, 3.0)

        if cam_pos is not None:
            loc = sh.get_loc("lights.viewPos")
            if loc != -1:
                glUniform3f(loc, cam_pos.x, cam_pos.y, cam_pos.z)

    # ==================================================================
    # UPLOAD — shaded (9-float: pos3 GLOBAL + normal3 + center3=0)
    # ==================================================================
    def _upload_main(self, v, c, ids, i):
        self._cleanup_main()

        self.vao    = glGenVertexArrays(1)
        self.vbo    = glGenBuffers(1)
        self.cbo    = glGenBuffers(1)
        self.id_vbo = glGenBuffers(1)
        self.ebo    = glGenBuffers(1)

        glBindVertexArray(self.vao)
        stride = self.STRIDE_MAIN_FLOATS * 4

        # VBO — pos + normal + center
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(4)
        glVertexAttribPointer(4, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))

        # CBO — color
        glBindBuffer(GL_ARRAY_BUFFER, self.cbo)
        glBufferData(GL_ARRAY_BUFFER, c.nbytes, c, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

        # IDBO — pick id
        glBindBuffer(GL_ARRAY_BUFFER, self.id_vbo)
        glBufferData(GL_ARRAY_BUFFER, ids.nbytes, ids, GL_STATIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, None)

        # EBO
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, i.nbytes, i, GL_STATIC_DRAW)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # ==================================================================
    # UPLOAD — simple (6-float: pos3 GLOBAL + pad3)
    # ==================================================================
    def _upload_simple(self, v, c, ids, i):
        self._cleanup_simple()

        self.simple_vao  = glGenVertexArrays(1)
        self.simple_vbo  = glGenBuffers(1)
        self.simple_cbo  = glGenBuffers(1)
        self.simple_idbo = glGenBuffers(1)
        self.simple_ebo  = glGenBuffers(1)

        glBindVertexArray(self.simple_vao)
        stride = self.STRIDE_SIMPLE_FLOATS * 4

        # VBO — pos (global) + pad
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        # CBO — color
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_cbo)
        glBufferData(GL_ARRAY_BUFFER, c.nbytes, c, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

        # IDBO — object id
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_idbo)
        glBufferData(GL_ARRAY_BUFFER, ids.nbytes, ids, GL_STATIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, ctypes.c_void_p(0))

        # EBO
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.simple_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, i.nbytes, i, GL_STATIC_DRAW)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # ==================================================================
    # CLEANUP
    # ==================================================================
    def _cleanup_main(self):
        for buf in (self.vbo, self.cbo, self.id_vbo, self.ebo):
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])
        if self.vao and glIsVertexArray(self.vao):
            glDeleteVertexArrays(1, [int(self.vao)])
        self.vao = self.vbo = self.cbo = self.id_vbo = self.ebo = None
        self.icount = 0

    def _cleanup_simple(self):
        for buf in (self.simple_vbo, self.simple_cbo, self.simple_idbo, self.simple_ebo):
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])
        if self.simple_vao and glIsVertexArray(self.simple_vao):
            glDeleteVertexArrays(1, [int(self.simple_vao)])
        self.simple_vao = self.simple_vbo = self.simple_cbo = None
        self.simple_idbo = self.simple_ebo = None
        self.simple_icount = 0

    def cleanup(self):
        self._cleanup_main()
        self._cleanup_simple()

    # ==================================================================
    # ARAYÜZ UYUMU — restraint rengi sabit turuncu
    # ==================================================================
    def update_colors(self, elements, color_func):
        pass

    def update_simple_colors(self, elements, color_func):
        pass