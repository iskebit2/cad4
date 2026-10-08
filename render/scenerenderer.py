# render/scenerenderer.py
from OpenGL.GL import *
import numpy as np
import glm
from typing import Optional, Any, List, Dict
from dataclasses import dataclass

from render.light_ubo import LightUBO
from render.lightingsystem import LightingSystem
from tools.gizmo import GizmoAxes
from tools.gridsystem import GridSystem
from domain.scene import Scene
from render.base_renderer import PolygonRenderer, _final_color_for, BaseRenderer, FrameRenderer, NodeRenderer, AreaRenderer, LinkRenderer
from render.pickpass import PickPass

from logging_config import CadLogger
logger = CadLogger.get(__name__)

@dataclass
class RenderStats:
    frame: int = 0
    node: int = 0
    area: int = 0
    tri: int = 0

class SceneRenderer:
    def __init__(self, pick_s, standard_s, node_s, simple_s, overlay_s, w=1024, h=768):
        self.pick_s = pick_s
        self.standard_shader = standard_s  # İsmi netleştirelim
        self.node_shader = node_s
        self.simple_shader = simple_s
        self.overlay_shader = overlay_s
        self.scene = self.camera = self.engine = None
        
        # Render modu: 'shaded' veya 'wireframe'
        self.render_mode = 'simple'
        
        # Renderer'ları oluştur
        self.frame_r = FrameRenderer(self.standard_shader)
        self.area_r = AreaRenderer(self.standard_shader)
        self.link_r = LinkRenderer(self.standard_shader)
        self.node_r = NodeRenderer(self.standard_shader)
        self.polygon_r = PolygonRenderer(self.standard_shader)
        

        
        # PickPass - MRT'den ID okumak için
        self.pick_pass = PickPass()
        self.pick_pass.set_viewport(w, h)
        
        self.lighting = LightingSystem()
        self.light_ubo = LightUBO()
        
        self.gizmo = self.grid = self.marquee = None
        self.snap = None
        self.show = {
                        'grid': True, 'axes': True, 'area': True,
                        'frame': True, 'link': True, 'node': True,
                        'polygon': True,     # ← YENİ
                    }
        self.use_lights = True
        
        self.model_mat = glm.mat4(1.0)
        self.anim_time = self.anim_dur = 0
        self.animating = False
        self.dt = 0
        
        self.stats = RenderStats()
        self.center = np.zeros(3)
        self.size = 1.0
        self.w = w
        self.h = h
        
        # MRT FBO'su
        self.mrt_fbo = None
        self.mrt_color_texture = None
        self.mrt_id_texture = None
        self.mrt_depth_rbo = None
        self._create_mrt_fbo(w, h)
        
        # PickPass'e ana FBO'yu bildir
        self.pick_pass.set_main_fbo(self.mrt_fbo)
        # Marquee için buffer'lar
        self.marquee_initialized = False
        self.marquee_vao = None
        self.marquee_vbo = None
        self.marquee_ebo_fill = None
        self.marquee_ebo_line = None


    def _init_marquee_buffers(self):
        """Marquee için kalıcı buffer'ları oluştur"""
        if self.marquee_initialized:
            return
        
        # VAO ve VBO oluştur
        self.marquee_vao = glGenVertexArrays(1)
        self.marquee_vbo = glGenBuffers(1)
        self.marquee_ebo_fill = glGenBuffers(1)
        self.marquee_ebo_line = glGenBuffers(1)
        
        # İndeks buffer'larını doldur
        fill_indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)
        line_indices = np.array([0, 1, 2, 3], dtype=np.uint32)
        
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.marquee_ebo_fill)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, fill_indices.nbytes, fill_indices, GL_STATIC_DRAW)
        
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.marquee_ebo_line)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, line_indices.nbytes, line_indices, GL_STATIC_DRAW)
        
        # VAO'yu yapılandır
        glBindVertexArray(self.marquee_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.marquee_vbo)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        
        self.marquee_initialized = True
        # logger.debug("Marquee buffer'ları oluşturuldu")
    
    def _create_mrt_fbo(self, w, h):
        """MRT FBO'su oluştur"""
        try:
            self.mrt_fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self.mrt_fbo)
            
            # Color texture
            self.mrt_color_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.mrt_color_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.mrt_color_texture, 0)
            
            # ID texture
            self.mrt_id_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.mrt_id_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, w, h, 0, GL_RED_INTEGER, GL_UNSIGNED_INT, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, self.mrt_id_texture, 0)
            
            # Depth buffer
            self.mrt_depth_rbo = glGenRenderbuffers(1)
            glBindRenderbuffer(GL_RENDERBUFFER, self.mrt_depth_rbo)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.mrt_depth_rbo)
            
            # Draw buffers
            glDrawBuffers(2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])
            
            status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
            if status != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"MRT FBO tamamlanamadı: {status}")
            
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            logger.info(f"MRT FBO oluşturuldu: {w}x{h}")
            
        except Exception as e:
            logger.error(f"MRT FBO oluşturma hatası: {e}")
            self._cleanup_mrt()
    
    def _cleanup_mrt(self):
        """MRT kaynaklarını temizle"""
        for obj in [self.mrt_fbo, self.mrt_color_texture, self.mrt_id_texture, self.mrt_depth_rbo]:
            if obj and glIsFramebuffer(obj):
                glDeleteFramebuffers(1, [obj])
            elif obj and glIsTexture(obj):
                glDeleteTextures(1, [obj])
            elif obj and glIsRenderbuffer(obj):
                glDeleteRenderbuffers(1, [obj])
        
        self.mrt_fbo = self.mrt_color_texture = self.mrt_id_texture = self.mrt_depth_rbo = None
    
    def set_cam(self, c): 
        self.camera = c
        self.gizmo = GizmoAxes(c)
    
    def set_grid(self, g): 
        self.grid = g
    
    def set_scene(self, s): 
        self.scene = s
    
    def set_snap(self, s):
        self.snap = s

    def set_marquee(self, m): 
        self.marquee = m
    
    def set_engine(self, e):
        self.engine = e
        self.w = self.engine.w
        self.h = self.engine.h
        self.resize(self.w, self.h)
    
    def set_dt(self, dt): 
        self.dt = dt
    
    def resize(self, w, h):
        self.w = w
        self.h = h
        if self.pick_pass:
            self.pick_pass.set_viewport(w, h)
        
        # MRT FBO'sunu yeniden boyutlandır
        self._cleanup_mrt()
        self._create_mrt_fbo(w, h)
        if self.pick_pass:
            self.pick_pass.set_main_fbo(self.mrt_fbo)
    
    def update_geo(self, scene=None, progress_cb=None):
        """
        Sahne geometrisini GPU'ya yükle.
        
        Parameters
        ----------
        scene : Scene, optional
        progress_cb : callable, optional
            İlerleme callback'i. `progress_cb(value, message)` çağrılır.
            `value` 0..1 arası, `message` açıklama.
        """
        self._last_progress_value = 0.0
        if scene is None:
            scene = self.scene

        # ---- 0. PickPass sıfırla ----
        if self.pick_pass and hasattr(self.pick_pass, 'clear_registry'):
            self.pick_pass.clear_registry()

        def _progress(value, msg=""):
            if progress_cb:
                try:
                    progress_cb(value, msg)
                except Exception as e:
                    logger.warning(f"progress_cb hatası: {e}")

        # ---- 1. Elementleri al ----
        _progress(0.00, "Hazırlanıyor...")
        frames = list(scene.frames.values())
        nodes = list(scene.nodes.values())
        areas = list(scene.areas.values())
        links = list(scene.links.values())
        polygons = list(scene.polygons.values())

        self.scene = scene

        # ---- 2. pick_id ata ----
        for frame in frames: frame.pick_id = frame.unique_id
        for node in nodes:   node.pick_id = node.unique_id
        for area in areas:   area.pick_id = area.unique_id
        for link in links:   link.pick_id = link.unique_id
        for pg in polygons:  pg.pick_id = pg.unique_id

        # ---- 3. Ağırlıklı adım ilerlemesi ----
        # Yaklaşık süre tahmini için ağırlıklar (ampirik)
        W_FRAME = 20
        W_NODE = 4
        W_AREA = 12
        W_LINK = 4
        W_POLY = 1

        total = (
            len(frames) * W_FRAME +
            len(nodes)  * W_NODE +
            len(areas)  * W_AREA +
            len(links)  * W_LINK +
            len(polygons) * W_POLY
        ) or 1  # sıfır bölmeyi önle

        done = 0

        # ---- 4. Renderer'ları güncelle ----
        _progress(0.02, f"Frames ({len(frames)})...")
        self.frame_r.update(frames)
        done += len(frames) * W_FRAME
        _progress(done / total, f"Frames ✓")

        _progress(done / total, f"Nodes ({len(nodes)})...")
        self.node_r.update(nodes)
        done += len(nodes) * W_NODE
        _progress(done / total, f"Nodes ✓")

        _progress(done / total, f"Areas ({len(areas)})...")
        self.area_r.update(areas)
        done += len(areas) * W_AREA
        _progress(done / total, f"Areas ✓")

        _progress(done / total, f"Links ({len(links)})...")
        self.link_r.update(links)
        done += len(links) * W_LINK
        _progress(done / total, f"Links ✓")

        _progress(done / total, f"Polygons ({len(polygons)})...")
        self.polygon_r.update(polygons)
        done += len(polygons) * W_POLY
        _progress(done / total, f"Polygons ✓")

        # Outline'ları bir kez üret
        outline_parts = []
        for pg in polygons:
            if pg.is_visible:
                v = self.polygon_r.builder.build_simple_lines(pg)
                if len(v) > 0:
                    outline_parts.append(v)
        if outline_parts:
            self.polygon_r._upload_outline(np.concatenate(outline_parts).astype(np.float32))
        else:
            self.polygon_r._cleanup_outline()
            
        # ---- 5. PickPass'e kaydet ----
        _progress(min(done / total + 0.01, 0.96), "Picking...")   # ← geriye gitmesin
        
        for frame in frames:
            self.pick_pass.register(frame.pick_id, frame, self.frame_r)
        for node in nodes:
            self.pick_pass.register(node.pick_id, node, self.node_r)
        for area in areas:
            self.pick_pass.register(area.pick_id, area, self.area_r)
        for link in links:
            self.pick_pass.register(link.pick_id, link, self.link_r)
        for pg in polygons:
            self.pick_pass.register(pg.pick_id, pg, self.polygon_r)

        # ---- 6. Bounds ----
        _progress(0.98, "Sınırlar hesaplanıyor...")
        self._update_bounds()

        _progress(1.00, "Tamamlandı")
    
    def update_sel(self):
        """Seçim renklerini güncelle - hem main hem simple CBO'ları"""
        if not self.scene:
            return
        
        renderers_and_elements = [
            (self.frame_r, list(self.scene.frames.values())),
            (self.node_r, list(self.scene.nodes.values())),
            (self.area_r, list(self.scene.areas.values())),
            (self.link_r, list(self.scene.links.values())),
            (self.polygon_r, list(self.scene.polygons.values())),   # ← YENİ
        ]
        
        for renderer, elements in renderers_and_elements:
            if renderer and renderer.icount > 0:
                renderer.update_colors(elements, self._get_final_color)
            if renderer and renderer.simple_vao is not None:
                renderer.update_simple_colors(elements, self._get_final_color)
                
    def _get_final_color(self, element):
        """Ortak _final_color_for'a delege et (tek kaynak)"""
        
        return _final_color_for(element) 
    
    def _default_color(self, element):
        """Element tipine göre varsayılan renk"""
        if hasattr(element, 'color'):
            return element.color
        
        # Element tipine göre renk
        if hasattr(element, 'section'):  # Frame
            return element.section.color if hasattr(element.section, 'color') else [0.7, 0.7, 0.7]
        elif hasattr(element, 'thickness'):  # Area
            return [0.5, 0.8, 1.0]
        elif hasattr(element, 'propname'):  # Link
            return [0.0, 1.0, 0.0]
        else:  # Node
            return [1.0, 1.0, 1.0]
        
    def toggle_render_mode(self):
        modes = ['shaded', 'line', 'simple', 'normal']
        idx = modes.index(self.render_mode) if self.render_mode in modes else 0
        self.render_mode = modes[(idx + 1) % len(modes)]
        logger.info(f"Render modu: {self.render_mode}")
        return self.render_mode
            
    def render(self, cam, target_fbo=0): # <-- target_fbo varsayılan 0 eklendi
        if not cam:
            return
        
        glBindFramebuffer(GL_FRAMEBUFFER, self.mrt_fbo)
        glClearColor(0.15, 0.15, 0.15, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        v = cam.get_view_matrix()
        p = cam.get_projection_matrix()
        mvp = p * v * self.model_mat
        cpos = glm.vec3(cam.position.x, cam.position.y, cam.position.z)
        
        if self.use_lights:
            self.light_ubo.update(self.lighting, (cpos.x, cpos.y, cpos.z))
        
        #Grid ve axes
        if self.show['grid'] and self.grid:
            self.grid.draw(mvp)
        if self.show['axes'] and self.gizmo:
            self.gizmo.render()
        
        # 1. MRT FBO'suna render et
        clear_id = np.array([0], dtype=np.uint32)
        glClearBufferuiv(GL_COLOR, 1, clear_id)
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        mode = 0 if self.render_mode == 'normal' else 1
        for r in [self.frame_r, self.node_r, self.area_r, self.link_r, self.polygon_r]:
            if r:
                r.render_mode = mode

        # Elementleri çiz
        if self.render_mode in ('shaded', 'normal'):
            if self.show['area'] and self.area_r:
                self.area_r.render(mvp, self.model_mat, cpos, v, p)
            if self.show['frame'] and self.frame_r:
                self.frame_r.render(mvp, self.model_mat, cpos, v, p)
            if self.show['link'] and self.link_r:
                self.link_r.render(mvp, self.model_mat, cpos, v, p)
            if self.show['node'] and self.node_r:
                self.node_r.render(mvp, self.model_mat, cpos, v, p)
            if self.show['polygon'] and self.polygon_r:
                self.polygon_r.render(mvp, self.model_mat, cpos, v, p)
        
        elif self.render_mode == 'line':
            self._render_line(mvp, v, p)
        
        elif self.render_mode == 'simple':
            self._render_simple(mvp, v, p)
        
        # 2. MRT'den Hedef FBO'ya (Qt'nin FBO'suna) Blit et

        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.mrt_fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, target_fbo) # <-- 0 yerine target_fbo!
        glReadBuffer(GL_COLOR_ATTACHMENT0)
        glBlitFramebuffer(
            0, 0, self.w, self.h,
            0, 0, self.w, self.h,
            GL_COLOR_BUFFER_BIT,
            GL_NEAREST
        )
        
        # 3. Framebuffer'ları hedef FBO'ya geri bağla
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, target_fbo) # <-- 0 yerine target_fbo!
        glBindFramebuffer(GL_FRAMEBUFFER, target_fbo)       # <-- 0 yerine target_fbo!
        
        # 4. MARQUEE - renkleri düzeltilmiş
        if self.marquee and self.marquee.is_active:
            self._draw_marquee()

    def _render_wireframe(self, mvp, view, proj):
        """Wireframe (GL_LINES/GL_POINTS) render et"""
        if not self.simple_shader:
            return
            
        self.simple_shader.use()
        glUniformMatrix4fv(self.simple_shader.get_loc("mvp"), 1, GL_FALSE, glm.value_ptr(mvp))
        
        # Her renderer'ın wireframe çizimini çağır
        if self.show['frame'] and self.frame_r:
            self.frame_r.render_wireframe(self.simple_shader)
        if self.show['link'] and self.link_r:
            self.link_r.render_wireframe(self.simple_shader)
        if self.show['node'] and self.node_r:
            self.node_r.render_wireframe(self.simple_shader)
        if self.show['area'] and self.area_r:
            self.area_r.render_wireframe(self.simple_shader)



    def _render_line(self, mvp, view, proj):
        """Gerçek geometrik kenarları çiz."""

        if not self.simple_shader:
            return

        self.simple_shader.use()

        mvp_loc = self.simple_shader.get_loc("mvp")

        if mvp_loc != -1:
            glUniformMatrix4fv(
                mvp_loc,
                1,
                GL_FALSE,
                glm.value_ptr(mvp)
            )

        # Frame
        if self.show['frame'] and self.frame_r:
            self.frame_r.render_line(self.simple_shader)

    def _render_simple(self, mvp, view, proj):
        if not self.simple_shader:
            return
        glPointSize(4.0)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # 1. FRAME (depth test açık)
        glEnable(GL_DEPTH_TEST)
        if self.show['frame'] and self.frame_r:
            self.frame_r.render_simple(mvp, self.simple_shader, alpha=1.0)

        # 2. AREA (transparan)
        if self.show['area'] and self.area_r:
            glDepthMask(GL_FALSE)
            self.area_r.render_simple(mvp, self.simple_shader, alpha=0.35)
            glDepthMask(GL_TRUE)

        # 3. POLYGON (transparan + outline) — NODE'LARDAN ÖNCE
        if self.show['polygon'] and self.polygon_r:
            glDepthMask(GL_FALSE)
            self.polygon_r.render_simple(mvp, self.simple_shader, alpha=0.50)
            self.polygon_r.render_lines_white(mvp, self.simple_shader)
            glDepthMask(GL_TRUE)

        # 4. LINK
        if self.show['link'] and self.link_r:
            self.link_r.render_simple(mvp, self.simple_shader, alpha=1.0)

        # 5. NODE (en üstte)
        glDisable(GL_DEPTH_TEST)
        if self.show['node'] and self.node_r:
            self.node_r.render_simple(mvp, self.simple_shader, alpha=1.0)
        glEnable(GL_DEPTH_TEST)
    
    def get_bounds(self):
        return self.center, self.size
    
    def _draw_marquee(self):

        """Marquee overlay çizimi - sağa mavi, sola yeşil"""
        if not self.marquee or not self.marquee.is_active:
            return
        
        coords = self.marquee.get_box_coords()
        if not coords:
            return
        
        x1, y1, x2, y2 = coords
        
        # Çok küçükse çizme
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return
        
        # Yönü belirle (sağa doğru mu sola doğru mu)
        cross = x2 < x1  # Sola doğru sürükleme
        
        # OpenGL state
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Shader'ı kullan
        self.overlay_shader.use()
        
        w, h = self.engine.w, self.engine.h
        proj = glm.ortho(0.0, float(w), float(h), 0.0, -1.0, 1.0)
        mvp_overlay = proj * glm.mat4(1.0)
        glUniformMatrix4fv(self.overlay_shader.get_loc("mvp"), 1, GL_FALSE, glm.value_ptr(mvp_overlay))
        
        color_loc = self.overlay_shader.get_loc("color")
        
        # Koordinatları düzelt (çizim için)
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        
        vertices = np.array([
            min_x, min_y, 0,
            max_x, min_y, 0,
            max_x, max_y, 0,
            min_x, max_y, 0
        ], dtype=np.float32)
        
        # Geçici VAO/VBO
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STREAM_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        
        if cross:
            # Sola doğru - yeşil
            fill_color = (0.2, 0.8, 0.2, 0.3)    # Yarı saydam yeşil
            border_color = (0.2, 1.0, 0.2, 0.8)  # Parlak yeşil
        else:
            # Sağa doğru - mavi
            fill_color = (0.2, 0.5, 0.9, 0.3)    # Yarı saydam mavi
            border_color = (0.4, 0.7, 1.0, 0.8)  # Parlak mavi
        
        # Fill
        glUniform4f(color_loc, *fill_color)
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        
        # Border
        glUniform4f(color_loc, *border_color)
        glDrawArrays(GL_LINE_LOOP, 0, 4)
        
        # Temizlik
        glDeleteVertexArrays(1, [vao])
        glDeleteBuffers(1, [vbo])

    def pick_async(self, x, y):
        """Asenkron picking başlat - MRT ID buffer'dan okur"""
        if not self.pick_pass:
            return False
        return self.pick_pass.pick_async(x, y)
    
    def check_pick(self):
        """Pick sonucunu kontrol et"""
        if not self.pick_pass:
            return None, None, None
        return self.pick_pass.check_pick()
    
    def get_element_from_id(self, pick_id):
        """Pick ID'den elementi bul"""
        return self.pick_pass.get_element(pick_id) if self.pick_pass else None
    

    def update_dirty(self):
        """Tüm renderer'lardaki dirty elementleri güncelle"""
        for renderer in [self.frame_r, self.node_r, self.area_r, self.link_r, self.polygon_r]:
            if renderer:
                renderer.update_dirty()
    
    def _update_bounds_from_nodes(self):
        if not self.scene or not self.scene.nodes:
            self.center = np.zeros(3)
            self.size = 1.0
            return

        coords = np.array([[n.x, n.y, n.z] for n in self.scene.nodes.values() if n.is_visible])

        if coords.size == 0:
            self.center = np.zeros(3)
            self.size = 1.0
            return

        self.bounds_min = coords.min(axis=0)
        self.bounds_max = coords.max(axis=0)

        self.center = (self.bounds_min + self.bounds_max) * 0.5
        self.size = np.linalg.norm(self.bounds_max - self.bounds_min) or 1.0
        
    def _update_bounds(self):
        bounds_center = np.zeros(3)
        bounds_size = 1.0
        count = 0
        
        # Tüm renderer'lardan bounds topla
        for renderer in [self.frame_r, self.node_r, self.area_r, self.link_r, self.polygon_r]:
            if renderer and renderer.icount > 0:
                c, s = renderer.get_bounds()
                bounds_center += c
                bounds_size = max(bounds_size, s)
                count += 1
        
        if count > 0:
            self.center = bounds_center / count
            self.size = bounds_size
        
        if self.scene:
            self._update_grid()
    
    def _update_grid(self):
        if not self.scene or not self.grid:
            return
        
        minv = np.array([float('inf')] * 3)
        maxv = np.array([float('-inf')] * 3)
        
        for f in self.scene.frames.values():
            for node in [f.node_i, f.node_j]:
                minv = np.minimum(minv, [node.x, node.y, node.z])
                maxv = np.maximum(maxv, [node.x, node.y, node.z])
        
        for n in self.scene.nodes.values():
            minv = np.minimum(minv, [n.x, n.y, n.z])
            maxv = np.maximum(maxv, [n.x, n.y, n.z])
        
        size = max(maxv[0] - minv[0], maxv[1] - minv[1], 10.0)
        cx, cy = minv[0] + size/2, minv[1] + size/2
        self.grid.update(glm.vec3(cx, cy, minv[2]), size)
    
    def start_anim(self, d=2.0):
        self.anim_time = 0
        self.anim_dur = d
        self.animating = True
        self.model_mat = glm.mat4(1.0)
    
    def _update_anim(self, dt):
        if not self.animating:
            return
        
        c = glm.vec3(*self.center)
        self.anim_time += dt
        t = min(self.anim_time / self.anim_dur, 1.0)
        ease = 1 - (1 - t) ** 3
        
        T1 = glm.translate(glm.mat4(1.0), -c)
        T2 = glm.translate(glm.mat4(1.0), c)
        Rz = glm.rotate(glm.mat4(1.0), ease * glm.two_pi(), glm.vec3(0, 0, 1))
        self.model_mat = T2 * Rz * T1
        
        if t >= 1.0:
            self.animating = False

    def cleanup(self):
        for r in [self.frame_r, self.node_r, self.area_r, self.link_r, self.polygon_r, self.grid, self.pick_pass, self.snap]:
            if r and hasattr(r, 'cleanup'):
                r.cleanup()
        
        # Marquee buffer'larını temizle
        
        for buf in [self.marquee_vao, 
                    self.marquee_vbo, 
                    self.marquee_ebo_fill, 
                    self.marquee_ebo_line]:
            if buf and glIsVertexArray(buf):
                glDeleteVertexArrays(1, [buf])
            elif buf and glIsBuffer(buf):
                glDeleteBuffers(1, [buf])
        
        if self.lighting and hasattr(self.lighting, 'cleanup'):
            self.lighting.cleanup()
        
        self._cleanup_mrt()