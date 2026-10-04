# render/base_renderer.py

from OpenGL.GL import *
import numpy as np
import glm
import ctypes

from typing import (
    List,
    Dict,
    Optional,
    Tuple,
    TypeVar,
    Generic
)

from abc import ABC, abstractmethod

from geometry.frame_builder import FrameBuilder
from geometry.area_builder import AreaBuilder
from geometry.link_builder import LinkBuilder
from geometry.node_builder import NodeBuilder
from geometry.polygon_builder import PolygonBuilder

from domain.element import (
    Frame,
    Node,
    Area,
    Link,
    Polygon
)

# =================================================================
# ORTAK RENK MANTIĞI (tek kaynak)
# =================================================================

def _final_color_for(element):
    """Elementin seçim durumuna göre son rengini döndür."""
    if element.is_selected:
        return [1.0, 0.5, 0.0]  # Turuncu — seçili

    # Polygon özel — kendi rengini kullan
    if hasattr(element, 'element_type') and element.element_type == "Polygon":
        return element.color   # Mor

    # Tip bazlı varsayılan
    if hasattr(element, 'section') and hasattr(element.section, 'color'):
        return list(element.section.color)     # Frame
    elif hasattr(element, 'thickness'):        # Area
        return [0.5, 0.8, 1.0]
    elif hasattr(element, 'propname'):         # Link
        return [0.0, 1.0, 0.0]
    else:                                       # Node
        return [1.0, 1.0, 1.0]

from logging_config import CadLogger

from logging_config import CadLogger

logger = CadLogger.get(__name__)

T = TypeVar("T")


class BaseRenderer(ABC, Generic[T]):

    def __init__(self, shader):

        self.shader = shader
        self.render_mode = 1   # 0 = normal debug, 1 = shaded
        # ---------------------------------------------------------
        # Ana OpenGL buffer'ları
        # ---------------------------------------------------------

        self.vao = None
        self.vbo = None
        self.cbo = None
        self.ebo = None
        self.line_ebo = None
        self.id_vbo = None

        # ---------------------------------------------------------
        # Basit mod OpenGL buffer'ları
        # ---------------------------------------------------------
        self.simple_idbo = None
        self.simple_vao = None
        self.simple_vbo = None
        self.simple_cbo = None
        self.simple_vcount = 0
        self.simple_draw_mode = GL_LINES   # Alt sınıflar override eder

        # ---------------------------------------------------------
        # Elements
        # ---------------------------------------------------------

        self.elements: List[T] = []

        self.elem_to_idx: Dict[str, Tuple[int, int]] = {}
        self.elem_to_vcount: Dict[str, int] = {}
        self.elem_to_inst: Dict[str, int] = {}

        self.vcount = 0
        self.icount = 0
        self.line_icount = 0
        self.inst_count = 0

        # ---------------------------------------------------------
        # Bounds
        # ---------------------------------------------------------

        self.bounds_min = np.array([float("inf")] * 3)
        self.bounds_max = np.array([float("-inf")] * 3)
        self.bounds_center = np.zeros(3)
        self.bounds_size = 1.0

        # ---------------------------------------------------------
        # Pick
        # ---------------------------------------------------------

        self.id_buffer_initialized = False

        # ---------------------------------------------------------
        # Vertex layout
        #   Frame / Area : pos3 + normal3 = 6 float
        #   Node  / Link : pos3 + normal3 + center3 = 9 float
        # ---------------------------------------------------------

        self.vertex_stride = 6 * 4
        self.has_center = False

    # =============================================================
    # ABSTRACT
    # =============================================================

    @abstractmethod
    def build(self, e: T) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        pass

    @abstractmethod
    def draw_mode(self) -> int:
        pass

    def build_lines(self, e: T) -> np.ndarray:
        """FrameRenderer override eder."""
        return np.array([], dtype=np.uint32)

    def build_simple(self, e: T):
        """
        Basit mod (simple) için vertex + renk üretir.
        Alt sınıflar override eder.
        Returns: (vertices, colors)
        """
        return (
            np.array([], dtype=np.float32),
            np.array([], dtype=np.float32),
        )

    # =============================================================
    # DIRTY
    # =============================================================

    def update_dirty(self):
        """
        Sadece renk buffer'larını (main + simple) günceller.
        Geometri yeniden üretilmez — hızlıdır.
        """
        dirty = [e for e in self.elements if e.needs_update]
        if not dirty:
            return
        # # logger.debug(f"{self.__class__.__name__}: {len(dirty)} dirty element - sadece renkler güncelleniyor")
        
        # Ortak renk fonksiyonu — SceneRenderer._get_final_color ile aynı mantık
        self._refresh_colors()
        
        for e in dirty:
            e.needs_update = False

    def _refresh_colors(self):
        """
        Elementlerin mevcut is_selected durumuna göre renkleri yeniden üret.
        Hem main hem simple CBO'yu tek geçişte günceller.
        """
        if not self.elements:
            return
        
        stride_floats = 9 if self.has_center else 6
        
        # ---- Main CBO ----
        if self.cbo and glIsBuffer(self.cbo):
            cols = []
            for e in self.elements:
                if e.element_id not in self.elem_to_vcount:
                    continue
                vc = self.elem_to_vcount[e.element_id]
                if vc == 0:
                    continue
                color = _final_color_for(e)
                cols.append(np.tile(color, (vc, 1)).astype(np.float32))
            
            if cols:
                new_colors = np.concatenate(cols)
                glBindBuffer(GL_ARRAY_BUFFER, self.cbo)
                glBufferSubData(GL_ARRAY_BUFFER, 0, new_colors.nbytes, new_colors)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        # ---- Simple CBO ----
        if self.simple_cbo and glIsBuffer(self.simple_cbo):
            simple_cols = []
            for e in self.elements:
                if not e.is_visible:
                    continue
                sv, _ = self.build_simple(e)
                if sv is None or len(sv) == 0:
                    continue
                count = len(sv) // stride_floats
                color = _final_color_for(e)
                simple_cols.append(np.tile(color, (count, 1)).astype(np.float32))
            
            if simple_cols:
                new_colors = np.concatenate(simple_cols)
                glBindBuffer(GL_ARRAY_BUFFER, self.simple_cbo)
                
                # Boyut uyuşmazlığı olursa (element eklendi/silindi) yeniden yükle
                current_size = glGetBufferParameteriv(GL_ARRAY_BUFFER, GL_BUFFER_SIZE)
                if current_size == new_colors.nbytes:
                    glBufferSubData(GL_ARRAY_BUFFER, 0, new_colors.nbytes, new_colors)
                else:
                    glBufferData(GL_ARRAY_BUFFER, new_colors.nbytes, new_colors, GL_DYNAMIC_DRAW)
                
                glBindBuffer(GL_ARRAY_BUFFER, 0)
    # =============================================================
    # BOUNDS
    # =============================================================

    def get_bounds(self):
        return self.bounds_center.copy(), self.bounds_size

    # =============================================================
    # UPDATE
    # =============================================================

    def update(self, raw: List[T]):
        """
        Elementleri işle, GPU buffer'larını güncelle.
        Ana geometri + line geometri + simple geometri tek geçişte hazırlanır.
        """
        
        logger.debug("FrameRenderer.update: %d element geldi", len(raw))
        
        self.elements = [e for e in raw if e.is_visible]
        logger.debug(f"    → {len(self.elements)} görünür element")
        logger.debug("→ %d görünür element",len(self.elements))

        self.elem_to_idx.clear()
        self.elem_to_vcount.clear()
        self.elem_to_inst.clear()

        # --- Boş sahne -------------------------------------------------
        if not self.elements:
            self.vcount = 0
            self.icount = 0
            self.line_icount = 0
            self.inst_count = 0
            self._cleanup_main()
            self._cleanup_simple()
            return

        # --- Biriktiriciler -------------------------------------------
        verts, cols, ids, idxs, line_idxs = [], [], [], [], []
        simple_verts, simple_colors, simple_ids = [], [], []

        voff = ioff = line_ioff = 0

        self.bounds_min[:] = float("inf")
        self.bounds_max[:] = float("-inf")

        stride_floats = 9 if self.has_center else 6

        # --- Her element için -----------------------------------------
        for inst_idx, e in enumerate(self.elements):

            # ---------- Ana geometri ----------
            v, c, i = self.build(e)

            if len(v) > 0 and (len(v) % stride_floats) == 0:
                vc = len(v) // stride_floats
                ic = len(i)

                id_data = np.full(vc, e.unique_id, dtype=np.uint32)

                self.elem_to_idx[e.element_id] = (ioff, ic)
                self.elem_to_vcount[e.element_id] = vc
                self.elem_to_inst[e.element_id] = inst_idx

                pos = v.reshape(-1, stride_floats)[:, :3]
                self.bounds_min = np.minimum(self.bounds_min, pos.min(axis=0))
                self.bounds_max = np.maximum(self.bounds_max, pos.max(axis=0))

                verts.append(v)
                cols.append(c)
                ids.append(id_data)
                idxs.append(i + voff)

                # Line (frame için)
                li = self.build_lines(e)
                if len(li) > 0:
                    line_idxs.append(li + voff)
                    line_ioff += len(li)

                voff += vc
                ioff += ic

            # ---------- Basit mod ----------
            sv, sc = self.build_simple(e)

            if sv is not None and len(sv) > 0:
                if (len(sv) % stride_floats) == 0:
                    vc = len(sv) // stride_floats

                    simple_verts.append(sv)
                    simple_colors.append(sc)
                    simple_ids.append(
                        np.full(vc, e.unique_id, dtype=np.uint32)
                    )
                else:
                    logger.warning(
                        f"{self.__class__.__name__}.build_simple: "
                        f"vertex sayısı stride'a uymuyor "
                        f"({len(sv)} % {stride_floats} != 0)"
                    )

        # --- Bounds ----------------------------------------------------
        if voff > 0:
            self.bounds_center = (self.bounds_min + self.bounds_max) * 0.5
            self.bounds_size = (
                np.linalg.norm(self.bounds_max - self.bounds_min) or 1.0
            )
        else:
            self.bounds_center = np.zeros(3)
            self.bounds_size = 1.0

        # --- Sayaçlar --------------------------------------------------
        self.vcount = voff
        self.icount = ioff
        self.line_icount = line_ioff
        self.inst_count = len(self.elements)

        # --- Ana buffer upload ----------------------------------------
        if self.icount > 0 and verts:
            vertex_data = np.concatenate(verts)
            color_data = np.concatenate(cols)
            id_data = np.concatenate(ids)
            index_data = np.concatenate(idxs)

            if line_idxs:
                line_index_data = np.concatenate(line_idxs)
            else:
                line_index_data = np.array([], dtype=np.uint32)

            self._upload(
                vertex_data,
                color_data,
                id_data,
                index_data,
                line_index_data,
            )

        # --- Simple buffer upload -------------------------------------
        if simple_verts:
            sv_all = np.concatenate(simple_verts).astype(np.float32)
            sc_all = np.concatenate(simple_colors).astype(np.float32)
            sid_all = np.concatenate(simple_ids)

            self._upload_simple(sv_all, sc_all, sid_all)

            logger.debug(
                "%s: simple_vcount=%s, draw_mode=%s",
                self.__class__.__name__,
                self.simple_vcount,
                self.simple_draw_mode,
            )
        else:
            self._cleanup_simple()

    # =============================================================
    # UPLOAD (main)
    # =============================================================

    def _upload(self, v, c, ids, i, line_i):
        # Sadece ana buffer'ları temizle, simple buffer'a DOKUNMA
        self._cleanup_main()

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.cbo = glGenBuffers(1)
        self.id_vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        self.line_ebo = glGenBuffers(1) if len(line_i) > 0 else None

        glBindVertexArray(self.vao)

        # --- VBO ---
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)

        stride = self.vertex_stride

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))

        if self.has_center:
            glEnableVertexAttribArray(4)
            glVertexAttribPointer(4, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))

        # --- Color ---
        glBindBuffer(GL_ARRAY_BUFFER, self.cbo)
        glBufferData(GL_ARRAY_BUFFER, c.nbytes, c, GL_DYNAMIC_DRAW)

        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))

        # --- Pick ID ---
        glBindBuffer(GL_ARRAY_BUFFER, self.id_vbo)
        glBufferData(GL_ARRAY_BUFFER, ids.nbytes, ids, GL_STATIC_DRAW)

        glEnableVertexAttribArray(3)
        glVertexAttribIPointer(3, 1, GL_UNSIGNED_INT, 0, None)

        # --- Triangle EBO ---
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, i.nbytes, i, GL_STATIC_DRAW)

        # --- Line EBO ---
        if self.line_ebo is not None and len(line_i) > 0:
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.line_ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, line_i.nbytes, line_i, GL_STATIC_DRAW)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        self.id_buffer_initialized = True

    # =============================================================
    # UPLOAD (simple)
    # =============================================================

    def _upload_simple(
        self,
        v: np.ndarray,
        c: np.ndarray,
        ids: np.ndarray,
    ):
        self._cleanup_simple()

        if len(v) == 0:
            return

        self.simple_vao = glGenVertexArrays(1)
        self.simple_vbo = glGenBuffers(1)
        self.simple_cbo = glGenBuffers(1)
        self.simple_idbo = glGenBuffers(1)

        glBindVertexArray(self.simple_vao)

        # ---------------------------------------------------------
        # Vertex
        # ---------------------------------------------------------
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_vbo)
        glBufferData(
            GL_ARRAY_BUFFER,
            v.nbytes,
            v,
            GL_STATIC_DRAW,
        )

        stride = self.vertex_stride

        # Position
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(
            0, 3, GL_FLOAT, GL_FALSE,
            stride, ctypes.c_void_p(0)
        )

        # Vertex color
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(
            1, 3, GL_FLOAT, GL_FALSE,
            stride, ctypes.c_void_p(12)
        )

        # Center
        if self.has_center:
            glEnableVertexAttribArray(4)
            glVertexAttribPointer(
                4, 3, GL_FLOAT, GL_FALSE,
                stride, ctypes.c_void_p(24)
            )

        # ---------------------------------------------------------
        # Pick ID
        # ---------------------------------------------------------
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_idbo)
        glBufferData(
            GL_ARRAY_BUFFER,
            ids.nbytes,
            ids,
            GL_STATIC_DRAW,
        )

        glEnableVertexAttribArray(3)

        # uint attribute → glVertexAttribIPointer
        glVertexAttribIPointer(
            3,
            1,
            GL_UNSIGNED_INT,
            4,
            ctypes.c_void_p(0),
        )

        # ---------------------------------------------------------
        # Color buffer
        # ---------------------------------------------------------
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_cbo)
        glBufferData(
            GL_ARRAY_BUFFER,
            c.nbytes,
            c,
            GL_DYNAMIC_DRAW,
        )

        glEnableVertexAttribArray(2)
        glVertexAttribPointer(
            2,
            3,
            GL_FLOAT,
            GL_FALSE,
            3 * 4,
            ctypes.c_void_p(0),
        )

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

        # ---------------------------------------------------------
        # Vertex count
        # ---------------------------------------------------------
        stride_floats = 9 if self.has_center else 6
        self.simple_vcount = len(v) // stride_floats

    # =============================================================
    # SHADED RENDER
    # =============================================================

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        if not self.vao or self.icount == 0:
            return
        if model is None:
            model = glm.mat4(1.0)
        if self.shader is None:
            return

        self.shader.use()

        mode_loc = self.shader.get_loc("renderMode")
        if mode_loc != -1:
            glUniform1i(mode_loc, self.render_mode)
            
        glUniformMatrix4fv(self.shader.get_loc("mvp"), 1, GL_FALSE, glm.value_ptr(mvp))
        glUniformMatrix4fv(self.shader.get_loc("model"), 1, GL_FALSE, glm.value_ptr(model))

        normal_matrix = glm.transpose(glm.inverse(glm.mat3(model)))
        glUniformMatrix3fv(
            self.shader.get_loc("normalMatrix"), 1, GL_FALSE,
            glm.value_ptr(normal_matrix),
        )

        if view is not None:
            loc = self.shader.get_loc("view")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(view))

        if proj is not None:
            loc = self.shader.get_loc("projection")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(proj))

        cl = self.shader.get_loc("useVertexColor")
        if cl != -1:
            glUniform1i(cl, 1)


        rim_intensity_loc = self.shader.get_loc("rimIntensity")
        if rim_intensity_loc != -1:
            glUniform1f(rim_intensity_loc, 0.80)   # 1.2 → 0.20
        rim_power_loc = self.shader.get_loc("rimPower")
        if rim_power_loc != -1:
            glUniform1f(rim_power_loc, 3.0)   # 2.5 → 4.0 (daha ince rim)

        if cam_pos is not None:
            loc = self.shader.get_loc("lights.viewPos")
            if loc != -1:
                glUniform3f(loc, cam_pos.x, cam_pos.y, cam_pos.z)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(self.draw_mode(), self.icount, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # =============================================================
    # LINE RENDER
    # =============================================================

    def render_line(self, shader):
        if not self.vao or not self.line_ebo or self.line_icount == 0:
            return
        if shader is None:
            return

        shader.use()

        # alpha ve useVertexColor'ı ayarla
        a_loc = shader.get_loc("alpha")
        if a_loc != -1:
            glUniform1f(a_loc, 1.0)

        vc_loc = shader.get_loc("useVertexColor")
        if vc_loc != -1:
            glUniform1i(vc_loc, 0)

        oc_loc = shader.get_loc("objectColor")
        if oc_loc != -1:
            glUniform3f(oc_loc, 1.0, 1.0, 1.0)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.line_ebo)
        glDrawElements(GL_LINES, self.line_icount, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    # =============================================================
    # SIMPLE RENDER
    # =============================================================

    def render_simple(self, mvp, shader, color=None, alpha=1.0):
        if not self.simple_vao or self.simple_vcount == 0:
            return

        if shader is None:
            return

        shader.use()

        loc = shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(
                loc, 1, GL_FALSE,
                glm.value_ptr(mvp)
            )

        vc_loc = shader.get_loc("useVertexColor")
        if vc_loc != -1:
            glUniform1i(
                vc_loc,
                0 if color is not None else 1
            )

        if color is not None:
            oc_loc = shader.get_loc("objectColor")
            if oc_loc != -1:
                glUniform3f(
                    oc_loc,
                    float(color[0]),
                    float(color[1]),
                    float(color[2])
                )

        a_loc = shader.get_loc("alpha")
        if a_loc != -1:
            glUniform1f(a_loc, float(alpha))

        glBindVertexArray(self.simple_vao)

        glDrawArrays(
            self.simple_draw_mode,
            0,
            self.simple_vcount
        )

        glBindVertexArray(0)

    # =============================================================
    # COLORS
    # =============================================================

    def update_colors(self, elements, color_func):
        if not self.cbo or not elements:
            return

        cols = []
        for e in elements:
            if e.element_id not in self.elem_to_vcount:
                continue
            vc = self.elem_to_vcount[e.element_id]
            if vc == 0:
                continue
            cols.append(
                np.tile(color_func(e), (vc, 1)).astype(np.float32)
            )

        if cols:
            new_colors = np.concatenate(cols)
            glBindBuffer(GL_ARRAY_BUFFER, self.cbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, new_colors.nbytes, new_colors)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

    def update_simple_colors(self, elements, color_func):
        """
        Simple mod CBO'sunu güncelle.
        Element → renk eşlemesini yaparak simple_cbo'ya yazar.
        """
        if not self.simple_cbo or not glIsBuffer(self.simple_cbo):
            return
        if not self.elements:
            return
        
        stride_floats = 9 if self.has_center else 6
        
        simple_cols = []
        for e in self.elements:
            if not e.is_visible:
                continue
            sv, _ = self.build_simple(e)
            if sv is None or len(sv) == 0:
                continue
            count = len(sv) // stride_floats
            color = color_func(e)
            simple_cols.append(np.tile(np.array(color, dtype=np.float32), (count, 1)))
        
        if not simple_cols:
            return
        
        new_colors = np.concatenate(simple_cols).astype(np.float32)
        
        glBindBuffer(GL_ARRAY_BUFFER, self.simple_cbo)
        current_size = glGetBufferParameteriv(GL_ARRAY_BUFFER, GL_BUFFER_SIZE)
        if current_size == new_colors.nbytes:
            glBufferSubData(GL_ARRAY_BUFFER, 0, new_colors.nbytes, new_colors)
        else:
            glBufferData(GL_ARRAY_BUFFER, new_colors.nbytes, new_colors, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # =============================================================
    # GET
    # =============================================================

    def get(self, eid: str) -> Optional[T]:
        return next((e for e in self.elements if e.element_id == eid), None)

    # =============================================================
    # CLEANUP
    # =============================================================

    def _cleanup_main(self):
        for buf in [self.vbo, self.cbo, self.id_vbo, self.ebo, self.line_ebo]:
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])

        if self.vao and glIsVertexArray(self.vao):
            glDeleteVertexArrays(1, [int(self.vao)])

        self.vao = None
        self.vbo = None
        self.cbo = None
        self.id_vbo = None
        self.ebo = None
        self.line_ebo = None
        self.id_buffer_initialized = False

    def _cleanup_simple(self):
        for buf in [self.simple_vbo, self.simple_cbo]:
            if buf and glIsBuffer(buf):
                glDeleteBuffers(1, [int(buf)])

        if self.simple_vao and glIsVertexArray(self.simple_vao):
            glDeleteVertexArrays(1, [int(self.simple_vao)])

        if self.simple_idbo:
            glDeleteBuffers(1, [self.simple_idbo])
            self.simple_idbo = None
            
        self.simple_vao = None
        self.simple_vbo = None
        self.simple_cbo = None
        self.simple_vcount = 0

    def cleanup(self):
        self._cleanup_main()
        self._cleanup_simple()


# =================================================================
# FRAME
# =================================================================

class FrameRenderer(BaseRenderer[Frame]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = FrameBuilder()
        self.vertex_stride = 6 * 4
        self.has_center = False
        self.simple_draw_mode = GL_LINES

    def build(self, f):
        return self.builder.build(f)

    def build_lines(self, f):
        return self.builder.build_lines(f)

    def build_simple(self, f):
        v = self.builder.build_simple_lines(f)
        if len(v) == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32)
        color = [1.0, 1.0, 1.0] if f.is_selected else list(f.section.color)
        count = len(v) // 6
        c = np.tile(np.array(color, dtype=np.float32), (count, 1))
        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        self.shader.use()

        loc = self.shader.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 0)

        a = self.shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 0.8)

        super().render(mvp, model, cam_pos, view, proj)


# =================================================================
# AREA
# =================================================================

class AreaRenderer(BaseRenderer[Area]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = AreaBuilder()
        self.lighting = None
        self.vertex_stride = 6 * 4
        self.has_center = False
        self.simple_draw_mode = GL_TRIANGLES

    def build(self, a):
        return self.builder.build(a)

    def build_simple(self, a):
        v = self.builder.build_simple(a)

        if len(v) == 0:
            return (
                np.array([], dtype=np.float32),
                np.array([], dtype=np.float32),
            )

        color = (
            [1.0, 1.0, 0.0]
            if a.is_selected
            else [0.5, 0.8, 1.0]
        )

        count = len(v) // 6

        c = np.tile(
            np.array(color, dtype=np.float32),
            (count, 1)
        )

        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def set_lighting(self, l):
        self.lighting = l

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        self.shader.use()

        loc = self.shader.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 0)

        a = self.shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 0.4)

        mode_loc = self.shader.get_loc("renderMode")
        if mode_loc != -1:
            glUniform1i(mode_loc, self.render_mode)
        
        super().render(mvp, model, cam_pos, view, proj)


# =================================================================
# LINK
# =================================================================

class LinkRenderer(BaseRenderer[Link]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = LinkBuilder()
        self.vertex_stride = 6 * 4
        self.has_center = False
        self.simple_draw_mode = GL_LINES

    def build(self, l):
        v, c, i = self.builder.build(l)

        # Builder 9-float döndürüyorsa 6-float'a indir
        if len(v) > 0 and len(v) % 9 == 0:
            v_6 = []
            for j in range(0, len(v), 9):
                v_6.extend([v[j], v[j+1], v[j+2], v[j+3], v[j+4], v[j+5]])
            v = np.array(v_6, dtype=np.float32)

        return v, c, i

    def build_simple(self, l):
        v = self.builder.build_simple_lines(l)
        if len(v) == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32)
        color = [1.0, 0.0, 0.0] if l.is_selected else [0.0, 1.0, 0.0]
        count = len(v) // 6
        c = np.tile(np.array(color, dtype=np.float32), (count, 1))
        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        self.shader.use()

        loc = self.shader.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 0)

        super().render(mvp, model, cam_pos, view, proj)


# =================================================================
# NODE
# =================================================================

class NodeRenderer(BaseRenderer[Node]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = NodeBuilder()
        self.vertex_stride = 9 * 4
        self.has_center = True
        self.simple_draw_mode = GL_POINTS

    def build(self, n):
        return self.builder.build(n)

    def build_simple(self, n):
        v = self.builder.build_simple_points(n)
        color = [1.0, 1.0, 0.0] if n.is_selected else [1.0, 0.0, 0.0]
        c = np.array([color], dtype=np.float32)
        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        self.shader.use()

        loc = self.shader.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 1)

        if view is not None:
            v_loc = self.shader.get_loc("view")
            if v_loc != -1:
                glUniformMatrix4fv(v_loc, 1, GL_FALSE, glm.value_ptr(view))

        if proj is not None:
            p_loc = self.shader.get_loc("projection")
            if p_loc != -1:
                glUniformMatrix4fv(p_loc, 1, GL_FALSE, glm.value_ptr(proj))

        ps_loc = self.shader.get_loc("pointScale")
        if ps_loc != -1:
            glUniform1f(ps_loc, 0.01)

        a_loc = self.shader.get_loc("alpha")
        if a_loc != -1:
            glUniform1f(a_loc, 1.0)

        super().render(mvp, model, cam_pos, view, proj)

        if loc != -1:
            glUniform1i(loc, 0)

# =================================================================
# POLYGON
# =================================================================

class PolygonRenderer(BaseRenderer[Polygon]):

    def __init__(self, shader):
        super().__init__(shader)
        self.builder = PolygonBuilder()
        self.vertex_stride = 6 * 4
        self.has_center = False
        self.simple_draw_mode = GL_LINES

    def build(self, p):
        return self.builder.build(p)

    def build_lines(self, p):
        return self.builder.build_lines(p)

    def build_simple(self, p):
        v = self.builder.build_simple_lines(p)
        if len(v) == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32)
        color = [1.0, 0.5, 0.0] if p.is_selected else p.color
        count = len(v) // 6
        c = np.tile(np.array(color, dtype=np.float32), (count, 1))
        return v, c

    def draw_mode(self):
        return GL_TRIANGLES

    def render(self, mvp, model=None, cam_pos=None, view=None, proj=None):
        self.shader.use()

        loc = self.shader.get_loc("isConstantSize")
        if loc != -1:
            glUniform1i(loc, 0)

        a = self.shader.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 0.5)   # Yarı saydam dolgu

        super().render(mvp, model, cam_pos, view, proj)