# core/plane_draw_manager.py
"""
PlaneDrawManager — 3 nokta ile 3D'de plane (düzlem) kurma.

Akış:
    AŞAMA 0 (p0 bekle)  → tıkla node → AŞAMA 1
    AŞAMA 1 (p1 bekle)  → tıkla node → AŞAMA 2, U = p1 - p0
    AŞAMA 2 (p2 bekle)  → tıkla node → AŞAMA 3, V = p2 - p0 (U'ya dik)
    AŞAMA 3 (depth+)    → mouse yukarı/aşağı depth_plus değişir
                          tıkla → AŞAMA 4
    AŞAMA 4 (depth-)    → mouse aşağı/yukarı depth_minus değişir
                          tıkla → onayla (plane oluştur)

Görsel:
    - U, V çizgileri (sarı)
    - Dikdörtgen düzlem (yarı saydam mavi)
    - Solid extrude kutu (yarı saydam turkuaz) — depth aşamasında
    - Hover node (yeşil halka)

Kontroller:
    - Space: depth'i default'a al (500/500)
    - ESC: aşamalı iptal (bir önceki aşamaya)
    - Enter: onayla (sadece depth aşamalarında)
"""

from __future__ import annotations

import math
import time
from typing import Optional, List, Tuple

import glm
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_FLOAT, GL_FALSE, GL_STREAM_DRAW,
    glBindBuffer, glBindVertexArray, glBufferData,
    glDeleteBuffers, glDeleteVertexArrays, glDrawArrays,
    glDisable, glEnable, glUniform4f, glUniformMatrix4fv,
    glVertexAttribPointer, glEnableVertexAttribArray,
    glGenBuffers, glGenVertexArrays,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_TRIANGLES, GL_LINES, GL_LINE_STRIP,
    glBlendFunc,
)
import glfw

from domain.plane import Plane
from domain.element import Node

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class PlaneDrawManager:
    """3 nokta ile plane oluşturma — görsel önizleme dahil."""

    # Aşamalar
    STAGE_P0    = 0
    STAGE_P1    = 1
    STAGE_P2    = 2
    STAGE_DEPTH_PLUS  = 3
    STAGE_DEPTH_MINUS = 4

    SNAP_RADIUS_PX = 15.0
    DEFAULT_DEPTH  = 500.0
    MIN_V_LENGTH   = 10.0
    MIN_U_LENGTH   = 10.0

    # Depth hassasiyeti: sahne_boyu * |dy_px| / 500
    DEPTH_K_FACTOR = 1.0 / 500.0

    def __init__(self, engine):
        self.engine = engine

        self.is_active = False
        self.stage = self.STAGE_P0

        # Seçilen noktalar
        self.p0: Optional[Node] = None
        self.p1: Optional[Node] = None
        self.p2: Optional[Node] = None

        # Hover node
        self.hover_node: Optional[Node] = None

        # Depth
        self.depth_plus = self.DEFAULT_DEPTH
        self.depth_minus = self.DEFAULT_DEPTH

        # Mouse tracking
        self._last_mouse_y = None

        # Preview buffers (lazy)
        self._tri_vao = None
        self._tri_vbo = None
        self._line_vao = None
        self._line_vbo = None

        # Tamamlanan plane (dışarıdan okunur)
        self.completed_plane: Optional[Plane] = None

    # =========================================================
    # START / CANCEL
    # =========================================================
    def start(self):
        logger.info(f"[PDM] engine.cam={hasattr(self.engine, 'cam')} "
                f"engine.scene={hasattr(self.engine, 'scene')} "
                f"engine.w={getattr(self.engine, 'w', '?')} "
                f"engine.h={getattr(self.engine, 'h', '?')}")
        logger.info(f"[PDM] nodes={len(self.engine.scene.nodes) if hasattr(self.engine, 'scene') and self.engine.scene else 0}")
        logger.info("[PlaneDraw] Mod aktif")
        self.is_active = True
        self.stage = self.STAGE_P0
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
        self._last_mouse_y = None
        self.completed_plane = None
        logger.info("[PlaneDraw] Mod aktif")

    def cancel(self):
        self.is_active = False
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self._last_mouse_y = None
        logger.info("[PlaneDraw] İptal")

    def _step_back(self):
        """ESC — bir önceki aşamaya dön."""
        if self.stage == self.STAGE_DEPTH_PLUS:
            self.stage = self.STAGE_P2
            self.p2 = None
            self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
        elif self.stage == self.STAGE_DEPTH_MINUS:
            self.stage = self.STAGE_DEPTH_PLUS
            self.depth_minus = self.DEFAULT_DEPTH
        elif self.stage == self.STAGE_P2:
            self.stage = self.STAGE_P1
            self.p1 = None
        elif self.stage == self.STAGE_P1:
            self.stage = self.STAGE_P0
            self.p0 = None
        elif self.stage == self.STAGE_P0:
            self.cancel()
            return
        self._last_mouse_y = None

    # =========================================================
    # GEOMETRİ — U, V, N hesabı
    # =========================================================
    def _u_vec(self):
        if self.p0 is None or self.p1 is None:
            return None
        return np.array([self.p1.x - self.p0.x,
                         self.p1.y - self.p0.y,
                         self.p1.z - self.p0.z], dtype=float)

    def _v_perp(self):
        """V'nin U'ya dik bileşeni (V_perp)."""
        if self.p0 is None or self.p2 is None:
            return None
        u = self._u_vec()
        if u is None:
            return None
        v_raw = np.array([self.p2.x - self.p0.x,
                          self.p2.y - self.p0.y,
                          self.p2.z - self.p0.z], dtype=float)
        u_len = np.linalg.norm(u)
        if u_len < 1e-9:
            return None
        u_hat = u / u_len
        v_perp = v_raw - u_hat * float(np.dot(v_raw, u_hat))
        return v_perp

    def _normal(self):
        """U × V_perp yönünde birim normal."""
        u = self._u_vec()
        v = self._v_perp()
        if u is None or v is None:
            return None
        n = np.cross(u, v)
        n_len = np.linalg.norm(n)
        if n_len < 1e-9:
            return None
        return n / n_len

    def _dims(self):
        """Uzunluklar: (u_len, v_len)."""
        u = self._u_vec()
        v = self._v_perp()
        if u is None or v is None:
            return None
        return float(np.linalg.norm(u)), float(np.linalg.norm(v))

    # =========================================================
    # MOUSE
    # =========================================================
    def on_mouse_move(self, x, y):
        if not self.is_active:
            return

        # Node snap sadece ilk 3 noktada
        if self.stage in (self.STAGE_P0, self.STAGE_P1, self.STAGE_P2):
            self.hover_node = self._find_node_at(x, y)
            
        else:
            self.hover_node = None

        # Depth fazı
        if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
            if self._last_mouse_y is not None:
                dy = self._last_mouse_y - y  # yukarı = pozitif
                k = self._depth_sensitivity()
                if self.stage == self.STAGE_DEPTH_PLUS:
                    # mouse yukarı = büyür, aşağı = küçülür
                    self.depth_plus = max(0.0, self.depth_plus + dy * k)
                else:
                    # mouse aşağı = büyür, yukarı = küçülür
                    self.depth_minus = max(0.0, self.depth_minus - dy * k)
            self._last_mouse_y = y

    def on_mouse_click(self, x, y) -> bool:

        if not self.is_active:
            return False

        # --- 3 nokta seçimi ---
        if self.stage in (self.STAGE_P0, self.STAGE_P1, self.STAGE_P2):
            node = self._find_node_at(x, y)
            if node is None:
                return False  # Node yoksa yut

            if self.stage == self.STAGE_P0:
                self.p0 = node
                self.stage = self.STAGE_P1
                logger.info(f"[PDM] p0 = {node.label}, stage → 1")
                return True

            if self.stage == self.STAGE_P1:
                if node is self.p0:
                    return True

                # Doğrudan node ile U hesabı (p1 henüz set edilmedi)
                u = np.array([node.x - self.p0.x,
                            node.y - self.p0.y,
                            node.z - self.p0.z], dtype=float)
                u_len = float(np.linalg.norm(u))
                logger.info(f"[PDM] p0={self.p0.label}, aday p1={node.label}, U={u_len:.1f}mm")

                if u_len < self.MIN_U_LENGTH:
                    logger.warning(f"[PDM] U çok kısa ({u_len:.1f} < {self.MIN_U_LENGTH})")
                    return True

                self.p1 = node
                self.stage = self.STAGE_P2
                logger.info(f"[PDM] p1 = {node.label}, stage → 2")
                return True

            if self.stage == self.STAGE_P2:
                if node is self.p0 or node is self.p1:
                    return True

                old_p2 = self.p2
                self.p2 = node
                v = self._v_perp()
                v_len = float(np.linalg.norm(v)) if v is not None else 0.0
                logger.info(f"[PDM] aday p2={node.label}, V_perp={v_len:.1f}mm")

                if v is None or v_len < self.MIN_V_LENGTH:
                    logger.warning(f"[PDM] V çok kısa ({v_len:.1f} < {self.MIN_V_LENGTH}), reddet")
                    self.p2 = old_p2
                    return True

                self.stage = self.STAGE_DEPTH_PLUS
                self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
                self._last_mouse_y = y
                logger.info(f"[PDM] p2 = {node.label}, stage → DEPTH_PLUS, default depth={self.DEFAULT_DEPTH}")
                return True

        # --- Depth plus ---
        if self.stage == self.STAGE_DEPTH_PLUS:
            self.stage = self.STAGE_DEPTH_MINUS
            self._last_mouse_y = y
            return True

        # --- Depth minus → onayla ---
        if self.stage == self.STAGE_DEPTH_MINUS:
            self._confirm()
            return True

        return False

    # =========================================================
    # KEYBOARD
    # =========================================================
    def on_key_press(self, key) -> bool:
        """True döndürürse tuş yutulur."""
        if not self.is_active:
            return False

        if key == glfw.KEY_ESCAPE:
            self._step_back()
            return True

        if key == glfw.KEY_SPACE:
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
                return True

        if key == glfw.KEY_ENTER:
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self._confirm()
                return True

        return False

    def _confirm(self):
        """Plane oluştur ve scene'e ekle."""
        if self.p0 is None or self.p1 is None or self.p2 is None:
            self.cancel()
            return

        dims = self._dims()
        if dims is None:
            logger.warning("[PlaneDraw] Geçersiz geometri, iptal")
            self.cancel()
            return

        u_len, v_len = dims
        if u_len < self.MIN_U_LENGTH or v_len < self.MIN_V_LENGTH:
            logger.warning(f"[PlaneDraw] Uzunluklar çok kısa (u={u_len:.1f}, v={v_len:.1f})")
            self.cancel()
            return

        u = self._u_vec()
        v = self._v_perp()
        n = self._normal()
        if u is None or v is None or n is None:
            self.cancel()
            return

        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        u_hat = u / u_len
        v_hat = v / v_len

        # origin: p0 + u/2 + v/2 (merkez)
        origin = p0 + u_hat * (u_len * 0.5) + v_hat * (v_len * 0.5)

        # Projedeki tüm plane isimleri
        project = getattr(self.engine.scene, "project", None) if self.engine.scene else None
        name = f"Plane_{len(project.planes) + 1 if project else 1}"

        plane = Plane(
            origin=origin,
            normal=n,
            u=u_hat,
            v=v_hat,
            name=name,
            u_min=-u_len * 0.5,
            u_max=u_len * 0.5,
            v_min=-v_len * 0.5,
            v_max=v_len * 0.5,
            depth_minus=self.depth_minus,
            depth_plus=self.depth_plus,
        )

        # Assoc hesapla
        if self.engine.scene is not None:
            try:
                plane.refresh_assoc(self.engine.scene)
            except Exception:
                logger.exception("[PlaneDraw] assoc hesabı hatası")

        # Projeye ekle
        if project is not None:
            project.planes[name] = plane
            logger.info(f"[PlaneDraw] '{name}' projeye eklendi")

        self.completed_plane = plane
        logger.info(
            f"[PlaneDraw] Oluşturuldu: {name} "
            f"u=±{u_len*0.5:.0f} v=±{v_len*0.5:.0f} "
            f"depth=[-{self.depth_minus:.0f},+{self.depth_plus:.0f}]"
        )
        self._finish()

    # =========================================================
    # YARDIMCI
    # =========================================================
    def _find_node_at(self, x, y):
        cam = self.engine.cam
        w, h = self.engine.w, self.engine.h
        if not cam or not self.engine.scene:
            logger.warning(f"[FIND] cam={cam}, scene={self.engine.scene}")
            return None

        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best_node = None
        best_dist_sq = self.SNAP_RADIUS_PX ** 2
        nearest = None

        for node in self.engine.scene.nodes.values():
            if not node.is_visible:
                continue
            clip = mvp * glm.vec4(node.x, node.y, node.z, 1.0)
            if clip.w <= 0:
                continue
            ndc = glm.vec3(clip) / clip.w
            px = (ndc.x + 1.0) * w / 2.0
            py = (1.0 - ndc.y) * h / 2.0
            dsq = (px - x) ** 2 + (py - y) ** 2
            if nearest is None or dsq < nearest[0]:
                nearest = (dsq, px, py, node.label)
            if dsq < best_dist_sq:
                best_dist_sq = dsq
                best_node = node

        # if nearest:
        #     pass(f"[FIND] en yakın: {nearest[3]} "
        #                 f"ekran=({nearest[1]:.0f},{nearest[2]:.0f}) "
        #                 f"mesafe={nearest[0]**0.5:.1f}px")
        # else:
        #     logger.warning("[FIND] hiç node yok (visible=False?)")

        return best_node

    def _depth_sensitivity(self):
        """1px dikey = kaç mm depth."""
        if not self.engine.scene:
            return 10.0
        try:
            center, size = self.engine.scene.get_bounds()
            return max(1.0, float(size) * self.DEPTH_K_FACTOR)
        except Exception:
            return 10.0

    # =========================================================
    # RENDER
    # =========================================================
    def render_preview(self, mvp, shader):
        """3D önizleme — overlay_shader uyumlu (mvp + color)."""
        if not self.is_active:
            return
        if shader is None:
            return
        if self.p0 is None:
            return

        self._ensure_buffers()

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)
        from OpenGL.GL import glDepthMask, GL_FALSE as GLF
        glDepthMask(GLF)

        try:
            shader.use()
            # Sadece 'mvp' (uMVP yok)
            loc_mvp = shader.get_loc("mvp")
            if loc_mvp == -1:
                loc_mvp = shader.get_loc("uMVP")   # güvenlik fallback
            if loc_mvp != -1:
                glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, glm.value_ptr(mvp))

            # Sadece 'color' (uColor yok)
            loc_color = shader.get_loc("color")
            if loc_color == -1:
                loc_color = shader.get_loc("uColor")   # güvenlik fallback
            if loc_color == -1:
                logger.warning("[PlaneDraw] shader'da 'color' veya 'uColor' yok")
                return

            # --- Çizim ---
            self._draw_lines(shader, loc_color, mvp)
            if self.p2 is not None:
                self._draw_plane_quad(shader, loc_color)
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self._draw_solid_box(shader, loc_color)
            if self.hover_node is not None:
                self._draw_hover_node(shader, loc_color)

        finally:
            from OpenGL.GL import glDepthMask, GL_TRUE
            glDepthMask(GL_TRUE)
            glDisable(GL_BLEND)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

    # ----------------------------------------------------------
    def _ensure_buffers(self):
        if self._tri_vao is None:
            self._tri_vao = glGenVertexArrays(1)
            self._tri_vbo = glGenBuffers(1)
        if self._line_vao is None:
            self._line_vao = glGenVertexArrays(1)
            self._line_vbo = glGenBuffers(1)

    def _upload_and_draw(self, vao, vbo, verts, mode, count, color, loc_color, width=1.0):
        if len(verts) == 0:
            return
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, None)
        glUniform4f(loc_color, *color)
        from OpenGL.GL import glLineWidth
        glLineWidth(width)
        glDrawArrays(mode, 0, count)

    # ----------------------------------------------------------
    def _draw_lines(self, shader, loc_color, mvp):
        """U ve V çizgileri + p0/p1/p2 nokta halkaları."""
        lines = []

        p0_xyz = None
        p1_xyz = None
        if self.p0 is not None:
            p0_xyz = (self.p0.x, self.p0.y, self.p0.z)
        if self.p1 is not None:
            p1_xyz = (self.p1.x, self.p1.y, self.p1.z)

        # U çizgisi
        if p0_xyz and p1_xyz:
            lines.extend((*p0_xyz, *p1_xyz))

        # V çizgisi (p0 → p2 veya fare)
        if self.stage == self.STAGE_P2 and self.hover_node is not None:
            # Fare node üzerindeyse ona, yoksa "preview v" yok (hover_node yoksa çizme)
            v_end = (self.hover_node.x, self.hover_node.y, self.hover_node.z)
            if p0_xyz:
                lines.extend((*p0_xyz, *v_end))
        elif self.p2 is not None and p0_xyz:
            v_end = (self.p2.x, self.p2.y, self.p2.z)
            lines.extend((*p0_xyz, *v_end))

        if lines:
            arr = np.asarray(lines, dtype=np.float32)
            self._upload_and_draw(self._line_vao, self._line_vbo, arr,
                                  GL_LINES, len(arr) // 3,
                                  (1.0, 0.85, 0.20, 1.0), loc_color, 2.0)

    def _draw_plane_quad(self, shader, loc_color):
        """U ve V'nin gerdiği paralelkenar — yarı saydam mavi."""
        u = self._u_vec()
        v = self._v_perp()
        if u is None or v is None:
            return
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        c0 = p0
        c1 = p0 + u
        c2 = p0 + u + v
        c3 = p0 + v
        # İki üçgen
        tris = np.array([
            *c0, *c1, *c2,
            *c0, *c2, *c3,
        ], dtype=np.float32)
        self._upload_and_draw(self._tri_vao, self._tri_vbo, tris,
                              GL_TRIANGLES, 6,
                              (0.30, 0.60, 0.90, 0.20), loc_color)

        # Kenarlar (daha koyu mavi)
        edges = np.array([
            *c0, *c1,
            *c1, *c2,
            *c2, *c3,
            *c3, *c0,
        ], dtype=np.float32)
        self._upload_and_draw(self._line_vao, self._line_vbo, edges,
                              GL_LINES, 8,
                              (0.50, 0.80, 1.00, 0.90), loc_color, 1.5)

    def _draw_solid_box(self, shader, loc_color):
        """Extrude kutu — yarı saydam turkuaz + kenarlar."""
        u = self._u_vec()
        v = self._v_perp()
        n = self._normal()
        if u is None or v is None or n is None:
            return
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])

        # 8 köşe: alt (depth_minus) ve üst (depth_plus)
        top = [
            p0 + n * self.depth_plus,
            p0 + u + n * self.depth_plus,
            p0 + u + v + n * self.depth_plus,
            p0 + v + n * self.depth_plus,
        ]
        bot = [
            p0 - n * self.depth_minus,
            p0 + u - n * self.depth_minus,
            p0 + u + v - n * self.depth_minus,
            p0 + v - n * self.depth_minus,
        ]

        # 6 yüz × 2 üçgen = 12 üçgen = 36 vertex
        tris = []
        # Üst
        tris.extend([*top[0], *top[1], *top[2], *top[0], *top[2], *top[3]])
        # Alt
        tris.extend([*bot[0], *bot[2], *bot[1], *bot[0], *bot[3], *bot[2]])
        # 4 yan yüz
        for i in range(4):
            j = (i + 1) % 4
            tris.extend([*bot[i], *bot[j], *top[j],
                         *bot[i], *top[j], *top[i]])
        arr = np.array(tris, dtype=np.float32)
        self._upload_and_draw(self._tri_vao, self._tri_vbo, arr,
                              GL_TRIANGLES, len(arr) // 3,
                              (0.20, 0.80, 0.85, 0.18), loc_color)

        # Kenar çizgileri (beyaz)
        edges = []
        # üst çerçeve
        for i in range(4):
            j = (i + 1) % 4
            edges.extend([*top[i], *top[j]])
        # alt çerçeve
        for i in range(4):
            j = (i + 1) % 4
            edges.extend([*bot[i], *bot[j]])
        # dikey kenarlar
        for i in range(4):
            edges.extend([*bot[i], *top[i]])
        edge_arr = np.array(edges, dtype=np.float32)
        self._upload_and_draw(self._line_vao, self._line_vbo, edge_arr,
                              GL_LINES, len(edge_arr) // 3,
                              (1.0, 1.0, 1.0, 0.85), loc_color, 1.2)

    def _draw_hover_node(self, shader, loc_color):
        """Yeşil halka — hover node."""
        n = self.hover_node
        if n is None:
            return
        # Basit nokta değil, halka çiz — kamera hizası için karmaşık
        # Şimdilik sadece küçük bir kare (ekran uzayında değil, dünya uzayında)
        # İleride iyileştirilebilir; şimdilik p1/p2 seçiminde görsel geri bildirim
        p = np.array([n.x, n.y, n.z], dtype=np.float32)
        # 3 eksende küçük çarpı
        s = 20.0  # dünya birimi
        lines = np.array([
            p[0]-s, p[1], p[2],  p[0]+s, p[1], p[2],
            p[0], p[1]-s, p[2],  p[0], p[1]+s, p[2],
            p[0], p[1], p[2]-s,  p[0], p[1], p[2]+s,
        ], dtype=np.float32)
        self._upload_and_draw(self._line_vao, self._line_vbo, lines,
                              GL_LINES, 6,
                              (0.20, 1.0, 0.30, 1.0), loc_color, 2.0)

    def _finish(self):
        self.is_active = False
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self._last_mouse_y = None
        logger.info("[PlaneDraw] Tamamlandı")
        
    # =========================================================
    # CLEANUP
    # =========================================================
    def cleanup(self):
        for vbo in (self._tri_vbo, self._line_vbo):
            if vbo:
                glDeleteBuffers(1, [int(vbo)])
        for vao in (self._tri_vao, self._line_vao):
            if vao:
                glDeleteVertexArrays(1, [int(vao)])
        self._tri_vao = self._tri_vbo = None
        self._line_vao = self._line_vbo = None