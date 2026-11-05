# render/polygonrenderer.py
from __future__ import annotations

import ctypes
from pyglm import glm
import numpy as np
from OpenGL.GL import *

from domain.polygon import Polygon
from geometry.polygon_builder import PolygonBuilder
from render.base_renderer import _final_color_for
from logging_config import CadLogger

logger = CadLogger.get(__name__)

class PolygonRenderer:
    """
    Poligonlar için özelleştirilmiş, BaseRenderer bağımlılığı olmayan bağımsız renderer.
    """
    def __init__(self, shader):
        self.shader = shader
        self.builder = PolygonBuilder()
        self.vertex_stride = 6 * 4  # pos3 + normal3
        self.simple_draw_mode = GL_TRIANGLES

        self.elements: list[Polygon] = []
        self.elem_to_simple_vcount: dict[int, int] = {}

        # Basit mod (simple) OpenGL buffer'ları
        self.simple_vao = None
        self.simple_vbo = None
        self.simple_cbo = None
        self.simple_idbo = None
        self.simple_vcount = 0

        # Outline (kenar çizgisi) buffer'ları
        self.outline_vao = None
        self.outline_vbo = None
        self.outline_vcount = 0

    def update(self, polygons_list: list[Polygon]):
        """Poligon verilerini işler ve OpenGL buffer'larını günceller."""
        self.elements = [p for p in polygons_list if getattr(p, 'is_visible', True)]
        self.elem_to_simple_vcount.clear()

        if not self.elements:
            self._cleanup_simple()
            self._cleanup_outline()
            return

        simple_verts, simple_colors, simple_ids = [], [], []

        for p in self.elements:
            v = self.builder.build_simple(p)
            if v is not None and len(v) > 0:
                if (len(v) % 6) == 0:
                    simple_vc = len(v) // 6
                    self.elem_to_simple_vcount[p.unique_id] = simple_vc

                    color = _final_color_for(p)
                    sc = np.tile(np.array(color[:3], dtype=np.float32), (simple_vc, 1))

                    simple_verts.append(v)
                    simple_colors.append(sc)
                    simple_ids.append(np.full(simple_vc, p.unique_id, dtype=np.uint32))
                else:
                    logger.debug("PolygonBuilder build_simple veri uzunluğu uyuşmazlığı")
            else:
                self.elem_to_simple_vcount[p.unique_id] = 0

        if simple_verts:
            sv_all = np.concatenate(simple_verts).astype(np.float32)
            sc_all = np.concatenate(simple_colors).astype(np.float32)
            sid_all = np.concatenate(simple_ids)
            self._upload_simple(sv_all, sc_all, sid_all)
        else:
            self._cleanup_simple()

    def _upload_simple(self, v, c, ids):
        self._cleanup_simple()
        if len(v) == 0:
            return

        self.simple_vao = glGenVertexArrays(1)
        self.simple_vbo = glGenBuffers(1)
        self.simple_cbo = glGenBuffers(1)
        self.simple_idbo = glGenBuffers(1)

        glBindVertexArray(self.simple_vao)

        # Position (Attrib 0)
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        stride = self.vertex_stride
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        # Color (Attrib 1)
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_cbo)
        glBufferData(GL_ARRAY_BUFFER, c.nbytes, c, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

        # Pick ID (Attrib 3)
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_idbo)
        glBufferData(GL_ARRAY_BUFFER, ids.nbytes, ids, GL_STATIC_DRAW)
        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, ctypes.c_void_p(0))

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

        self.simple_vcount = len(v) // 6

    def render_simple(self, mvp, shader, color=None, alpha=0.5):
        """Poligon iç dolgusunu çizer."""
        if not self.simple_vao or self.simple_vcount == 0:
            return
        shader.use()
        
        loc = shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            
        vc = shader.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 1 if color is None else 0)
            
        if color is not None:
            oc = shader.get_loc("objectColor")
            if oc != -1:
                glUniform3f(oc, color[0], color[1], color[2])
                
        a = shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, float(alpha))

        glBindVertexArray(self.simple_vao)
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-1.0, -1.0)

        glDrawArrays(self.simple_draw_mode, 0, self.simple_vcount)

        glDisable(GL_POLYGON_OFFSET_FILL)
        glBindVertexArray(0)

    def render_pick(self, mvp, shader):
        """Pick pass için poligonları ID buffer'a çizer."""
        if not self.simple_vao or self.simple_vcount == 0 or not shader:
            return
        shader.use()
        
        loc = shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

        glBindVertexArray(self.simple_vao)
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-1.0, -1.0)

        glDrawArrays(self.simple_draw_mode, 0, self.simple_vcount)

        glDisable(GL_POLYGON_OFFSET_FILL)
        glBindVertexArray(0)

    def _upload_outline(self, outline_verts):
        self._cleanup_outline()
        if len(outline_verts) == 0:
            return
        self.outline_vao = glGenVertexArrays(1)
        self.outline_vbo = glGenBuffers(1)
        glBindVertexArray(self.outline_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.outline_vbo)
        glBufferData(GL_ARRAY_BUFFER, outline_verts.nbytes, outline_verts, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glBindVertexArray(0)
        self.outline_vcount = len(outline_verts) // 6

    def _cleanup_outline(self):
        if self.outline_vao and glIsVertexArray(self.outline_vao):
            glDeleteVertexArrays(1, [int(self.outline_vao)])
        if self.outline_vbo and glIsBuffer(self.outline_vbo):
            glDeleteBuffers(1, [int(self.outline_vbo)])
        self.outline_vao = self.outline_vbo = None
        self.outline_vcount = 0

    def render_lines_white(self, mvp, shader):
        """Poligon çevre çizgilerini (outline) beyaz olarak çizer."""
        if not self.outline_vao or self.outline_vcount == 0:
            return
        shader.use()
        
        loc = shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            
        vc = shader.get_loc("useVertexColor")
        if vc != -1: 
            glUniform1i(vc, 0)
            
        oc = shader.get_loc("objectColor")
        if oc != -1: 
            glUniform3f(oc, 1.0, 1.0, 1.0)
            
        a = shader.get_loc("alpha")
        if a != -1: 
            glUniform1f(a, 0.9)

        glBindVertexArray(self.outline_vao)
        glDrawArrays(GL_LINES, 0, self.outline_vcount)
        glBindVertexArray(0)

    def _cleanup_simple(self):
        for buf in [self.simple_vbo, self.simple_cbo, self.simple_idbo]:
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])
        if self.simple_vao and glIsVertexArray(self.simple_vao):
            glDeleteVertexArrays(1, [int(self.simple_vao)])
        self.simple_idbo = None
        self.simple_vao = None
        self.simple_vbo = None
        self.simple_cbo = None
        self.simple_vcount = 0

    def cleanup(self):
        self._cleanup_outline()
        self._cleanup_simple()