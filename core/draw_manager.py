# core/draw_manager.py
import ctypes

import glm
import numpy as np
from logging_config import CadLogger
import time

from domain.element import Polygon
from OpenGL.GL import (
    GL_DEPTH_TEST, glDisable, glDisableVertexAttribArray, glEnable, glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glUniform1f, glUniform1i, glUniform4f, glVertexAttrib3f, glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawArrays, glDeleteVertexArrays, glDeleteBuffers,
    glGetUniformLocation, glUniformMatrix4fv, glUniform3f,
    GL_ARRAY_BUFFER, GL_STREAM_DRAW, GL_FLOAT, GL_FALSE,
    GL_LINE_STRIP, GL_TRIANGLE_FAN, GL_LINES,
)

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class DrawManager:
    """
    Sadece polygon çizimi için state machine.
    
    Akış:
      1. start() → mod aktif
      2. Node üzerine tıkla → points'e ekle
      3. İlk noktaya tekrar tıkla veya C/Enter → close() → Polygon oluştur
      4. ESC → cancel()
    """
    
    SNAP_RADIUS_PX = 15   # Node yakınlık eşiği (piksel)
    
    def __init__(self, engine):
        self.engine = engine
        

        self.is_active = False
        self.points = []          # seçilen Node objeleri
        self.hover_node = None    # fare şu an hangi node üstünde
        self.mouse_world_pos = None   # fare dünya koordinatı (preview için)
        
        # Preview buffer (lazy init)
        self.preview_vao = None
        self.preview_vbo = None
        
        # Throttle
        self._last_move_time = 0.0
    
    # =========================================================
    # BAŞLAT / İPTAL / BİTİR
    # =========================================================
    
    def start(self):
        self.is_active = True
        self.points.clear()
        self.hover_node = None
        self.mouse_world_pos = None
        logger.info("[Draw] Polygon modu aktif")
    
    def cancel(self):
        self.is_active = False
        self.points.clear()
        self.hover_node = None
        self.mouse_world_pos = None
        logger.info("[Draw] Polygon çizimi iptal edildi")
    
    def close(self):
        """C tuşu veya ilk noktaya tıkla — poligonu kapat ve oluştur."""
        if len(self.points) < 3:
            logger.warning(f"[Draw] En az 3 nokta gerekli (şu an {len(self.points)}), iptal")
            self.cancel()
            return
        
        polygon = Polygon(list(self.points), label="")
        
        # Scene'e ekle
        scene = self.engine.scene
        scene.add_polygon(polygon)
        
        # Renderer'ı güncelle (yeni buffer'lar üretir)
        self.engine.renderer.update_geo(scene)
        
        # Yeni poligonu seç
        self.engine.sel_mgr.select(polygon)
        
        logger.info(f"[Draw] Polygon oluşturuldu: {len(self.points)} köşe, id={polygon.unique_id}")
        self.cancel()
    
    # =========================================================
    # MOUSE
    # =========================================================
    
    def on_mouse_move(self, x, y):
        if not self.is_active:
            return
        
        # Throttle (30 FPS)
        now = time.time()
        if now - self._last_move_time < 0.033:
            return
        self._last_move_time = now
        
        self.hover_node = self._find_node_at(x, y)
        
        # Fare dünya koordinatı (grid düzlemi üzerinde)
        self.mouse_world_pos = self._screen_to_world_xy(x, y)

        
    
    def on_mouse_click(self, x, y) -> bool:
        """Return True if consumed."""
        if not self.is_active:
            return False
        
        node = self._find_node_at(x, y)
        logger.debug(f"[CLICK] tıklama ({x}, {y}) → node={node}")
        if node:
            logger.debug(f"[CLICK] node label={node.label}, coords=({node.x},{node.y},{node.z})")
        else:
            # En yakın 5 node'u yazdır
            self._debug_nearest_nodes(x, y)

        if node is None:
            return True  # Node yoksa tık yutulur (başka bir şey yapma)
        
        # İlk noktaya tıklandı mı? → kapat
        if len(self.points) >= 3 and node is self.points[0]:
            self.close()
            return True
        
        # Aynı node'a ardışık tıklama → yok say
        if self.points and node is self.points[-1]:
            return True
        
        self.points.append(node)
        logger.debug(f"[Draw] Nokta eklendi: {node.label} ({len(self.points)} toplam)")
        return True

    def _debug_nearest_nodes(self, x, y, count=5):
        """En yakın node'ları log'la (debug için)."""
        cam = self.engine.cam
        w, h = self.engine.w, self.engine.h
        
        if not cam or not self.engine.scene:
            return
        
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        
        distances = []
        for node in self.engine.scene.nodes.values():
            if not node.is_visible:
                continue
            
            clip = mvp * glm.vec4(node.x, node.y, node.z, 1.0)
            if clip.w <= 0:
                continue
            
            ndc = glm.vec3(clip) / clip.w
            px = (ndc.x + 1.0) * w / 2.0
            py = (1.0 - ndc.y) * h / 2.0
            
            dx = px - x
            dy = py - y
            dist_sq = dx * dx + dy * dy
            distances.append((dist_sq ** 0.5, node.label, px, py))
        
        distances.sort()
        logger.debug(f"[CLICK] En yakın {count} node:")
        for d, label, px, py in distances[:count]:
            logger.debug(f"  {label}: {d:.1f}px mesafe, ekran=({px:.0f},{py:.0f})")
            
    # =========================================================
    # YARDIMCI — NODE BULMA
    # =========================================================
    
    def _find_node_at(self, x, y):
        """
        Ekran koordinatına en yakın node'u bul (piksel toleransı).
        """
        cam = self.engine.cam
        w, h = self.engine.w, self.engine.h
        
        if not cam or not self.engine.scene:
            return None
        
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        
        best_node = None
        best_dist_sq = self.SNAP_RADIUS_PX ** 2
        
        for node in self.engine.scene.nodes.values():
            if not node.is_visible:
                continue
            
            clip = mvp * glm.vec4(node.x, node.y, node.z, 1.0)
            if clip.w <= 0:
                continue
            
            ndc = glm.vec3(clip) / clip.w
            px = (ndc.x + 1.0) * w / 2.0
            py = (1.0 - ndc.y) * h / 2.0
            
            dx = px - x
            dy = py - y
            dist_sq = dx * dx + dy * dy
            
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_node = node
        
        return best_node
    
    def _screen_to_world_xy(self, x, y):
        """
        Ekran koordinatını Z=0 düzlemindeki dünya koordinatına çevir.
        """
        cam = self.engine.cam
        w, h = self.engine.w, self.engine.h
        
        if not cam:
            return None
        
        v = cam.get_view_matrix()
        p = cam.get_projection_matrix()
        
        nx = 2 * x / w - 1
        ny = 1 - 2 * y / h
        
        inv = glm.inverse(p * v)
        
        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        
        direction = glm.normalize(far - near)

        

        if abs(direction.z) > 1e-6:
            t = -near.z / direction.z
            if t > 0:
                result = near + direction * t
                
                return result
            
        
        return None
    
    # =========================================================
    # PREVIEW RENDER
    # =========================================================
    
    def _init_preview_buffers(self):
        if self.preview_vao is not None:
            return
        
        self.preview_vao = glGenVertexArrays(1)
        self.preview_vbo = glGenBuffers(1)

    def render_preview(self, mvp, shader):
        """
        Polygon çizim önizlemesi.
        
        Katmanlar (alttan üste):
        1. Mor yarı saydam dolgu (3+ nokta)
        2. Sarı çizgi dizisi (2+ nokta, noktalar arası)
        3. Beyaz aktif çizgi (son nokta → fare)
        4. Yeşil kapanış ipucu (3+ nokta, son → ilk)
        
        Depth test kapalı çizilir (overlay), çıkışta geri açılır.
        """
        # ---- Erken çıkışlar ----
        if not self.is_active:
            return
        if not self.points:
            return
        if shader is None:
            return

        # ---- Lazy buffer init ----
        self._init_preview_buffers()

        # ---- Depth overlay modu ----
        glDisable(GL_DEPTH_TEST)
        try:
            # ---- Shader ve MVP ----
            shader.use()

            mvp_loc = shader.get_loc("mvp")
            if mvp_loc != -1:
                glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))

            color_loc = shader.get_loc("uColor")
            if color_loc == -1:
                return   # shader'da uColor yok — çizim yapma

            # ---- VAO / VBO ----
            glBindVertexArray(self.preview_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.preview_vbo)

            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, None)

            # ---- Yardımcı: vertex dizisi oluştur ----
            def _flatten(points):
                """Liste glm.vec3 / objelerini tek array'e çevir."""
                out = []
                for p in points:
                    out.extend((p.x, p.y, p.z))
                return np.asarray(out, dtype=np.float32)

            def _draw(verts, mode, count, color):
                glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
                glUniform4f(color_loc, *color)
                glDrawArrays(mode, 0, count)

            n = len(self.points)

            # ---- 1) Mor yarı saydam dolgu (3+ nokta) ----
            if n >= 3:
                verts = _flatten(self.points)
                _draw(verts, GL_TRIANGLE_FAN, n, (0.8, 0.3, 0.8, 0.35))

            # ---- 2) Sarı çizgi dizisi (2+ nokta) ----
            if n >= 2:
                verts = _flatten(self.points)
                _draw(verts, GL_LINE_STRIP, n, (1.0, 1.0, 0.0, 1.0))

            # ---- 3) Beyaz aktif çizgi (son nokta → fare) ----
            if self.mouse_world_pos is not None:
                last = self.points[-1]
                m = self.mouse_world_pos
                verts = np.asarray(
                    (last.x, last.y, last.z, m.x, m.y, m.z),
                    dtype=np.float32,
                )
                _draw(verts, GL_LINES, 2, (1.0, 1.0, 1.0, 0.85))

            # ---- 4) Yeşil kapanış ipucu (3+ nokta, son → ilk) ----
            if n >= 3:
                first = self.points[0]
                last = self.points[-1]
                verts = np.asarray(
                    (last.x, last.y, last.z, first.x, first.y, first.z),
                    dtype=np.float32,
                )
                _draw(verts, GL_LINES, 2, (0.5, 1.0, 0.5, 0.7))

            # ---- Temizlik ----
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

        finally:
            glEnable(GL_DEPTH_TEST)
                                
    # =========================================================
    # CLEANUP
    # =========================================================
    
    def cleanup(self):
        if self.preview_vbo:
            glDeleteBuffers(1, [int(self.preview_vbo)])
            self.preview_vbo = None
        if self.preview_vao:
            glDeleteVertexArrays(1, [int(self.preview_vao)])
            self.preview_vao = None