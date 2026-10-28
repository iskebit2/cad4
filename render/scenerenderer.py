# render/scenerenderer.py
import math
from dataclasses import dataclass

import glm
import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger
from render.axes_renderer import LocalAxesRenderer
from render.base_renderer import (
    AreaRenderer,
    FrameRenderer,
    LinkRenderer,
    PolygonRenderer,
    _final_color_for,
)
from render.label_batch import LabelBatch
from render.light_ubo import LightUBO
from render.lightingsystem import LightingSystem
from render.load_renderer import LoadRenderer
from render.node_renderer import NodeRenderer
from render.pickpass import PickPass
from tools.font_atlas import FontAtlas
from tools.gizmo import GizmoAxes

logger = CadLogger.get(__name__)



@dataclass
class RenderStats:
    frame: int = 0
    node: int = 0
    area: int = 0
    tri: int = 0

class SceneRenderer:
    RENDER_MODES = ('shaded', 'line', 'simple', 'normal')
    def __init__(self, pick_s, standard_s, node_s, simple_s, overlay_s, axes_s, w=1024, h=768):
        self.pick_s = pick_s
        self.standard_shader = standard_s  # İsmi netleştirelim
        self.node_shader = node_s
        self.simple_shader = simple_s
        self.overlay_shader = overlay_s
        self.axes_shader = axes_s

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
        self.plane_draw_mgr = None

        self.show = {
                        'grid': True, 'axes': True, 'area': True,
                        'frame': True, 'link': True, 'node': True,
                        'polygon': True,
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
        #pass(f"[scenerenderer__INIT__] MRT FBO oluşturuldu: {w}x{h}")
        # PickPass'e ana FBO'yu bildir
        self.pick_pass.set_main_fbo(self.mrt_fbo)
        # Marquee için buffer'lar
        self.marquee_initialized = False
        self.marquee_vao = None
        self.marquee_vbo = None
        self.marquee_ebo_fill = None
        self.marquee_ebo_line = None

        self._marquee_ov_vao = None
        self._marquee_ov_vbo = None
        self._overlay_mvp_loc = overlay_s.get_loc("mvp") if overlay_s else -1
        self._overlay_color_loc = overlay_s.get_loc("color") if overlay_s else -1

        self.font_atlas = FontAtlas(
            ttf_path= None,# "C:/Windows/Fonts/consola.ttf",
            size=32,
            supersample=2,
        )
        self.label_batch = LabelBatch(self.font_atlas)
        self.label_batch.init_gl()
        
        self.axes_r = LocalAxesRenderer(self.axes_shader)
        self.axes_r.init_gl()

        self.load_renderer = LoadRenderer()

        self.selected_plane = None
        self._sel_plane_tri_vao = None
        self._sel_plane_tri_vbo = None
        self._sel_plane_line_vao = None
        self._sel_plane_line_vbo = None
        self._load_scale_override = 1.0

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
        # #pass("Marquee buffer'ları oluşturuldu")
    
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
            #pass(f"[scenerenderer_create_mrt_fbo] MRT FBO oluşturuldu: {w}x{h}")
            
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

    def set_node_point_size(self, px: float):
        """Simple modda node nokta boyutunu piksel cinsinden ayarla."""
        if self.node_r:
            self.node_r.set_point_size(px)

    def set_node_size(self, size: float, rebuild: bool = True):
        """
        Node sembol boyutunu ayarla.
        rebuild=True ise geometriyi yeniden üretir (scene gerekir).
        """
        if not self.node_r:
            return
        changed = self.node_r.set_node_size(size)
        if changed and rebuild and self.scene:
            # Sadece node renderer'ı yeniden build et — daha hızlı
            nodes = list(self.scene.nodes.values())
            for n in nodes:
                n.mark_dirty()
            self.node_r.update(nodes)
            # Renkleri yeniden uygula (update_colors zaten CBO'yu yeniler)
            self.node_r.update_colors(nodes, self._get_final_color)
            self.node_r.update_simple_colors(nodes, self._get_final_color)

    def set_marquee(self, m): 
        self.marquee = m

    def set_plane_draw_mgr(self, pdm):
        """PlaneDrawManager referansı (CadApp tarafından verilir)."""
        self.plane_draw_mgr = pdm

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
        #pass(f"[resize] çağrıldı... _create_mrt_fbo yeniden oluşturuldu: {w}x{h}")
        if self.pick_pass:
            self.pick_pass.set_main_fbo(self.mrt_fbo)
    
    def update_geo(self, scene=None, progress_cb=None):
        
        self._last_progress_value = 0.0
        if scene is None:
            scene = self.scene

        flt = getattr(scene, '_render_filter', None)

        def _f(d):
            if flt is None:
                return list(d.values())
            return [e for e in d.values() if e.unique_id in flt]

        frames = _f(scene.frames)
        nodes = _f(scene.nodes)
        areas = _f(scene.areas)
        links = _f(scene.links)
        polygons = _f(scene.polygons)
        

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
        _progress(done / total, "Frames ✓")

        _progress(done / total, f"Nodes ({len(nodes)})...")
        self.node_r.update(nodes)
        done += len(nodes) * W_NODE
        _progress(done / total, "Nodes ✓")

        _progress(done / total, f"Areas ({len(areas)})...")
        self.area_r.update(areas)
        done += len(areas) * W_AREA
        _progress(done / total, "Areas ✓")

        _progress(done / total, f"Links ({len(links)})...")
        self.link_r.update(links)
        done += len(links) * W_LINK
        _progress(done / total, "Links ✓")

        _progress(done / total, f"Polygons ({len(polygons)})...")
        self.polygon_r.update(polygons)
        done += len(polygons) * W_POLY
        _progress(done / total, "Polygons ✓")

        

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

        # ---- 6.5 Node boyutu ----
        if self.node_r and self.size > 0:
            # isConstantSize=1 ile uyumlu "size" = yaklaşık ekran oranı
            # (pointScale=0.002, size=1 → ~5-10 piksel)
            # Görünür olması için 20-40 arası
            desired = 20.0
            if self.node_r.set_node_size(desired):
                for n in nodes:
                    n.mark_dirty()
                self.node_r.update(nodes)
                self.node_r.update_colors(nodes, self._get_final_color)
                self.node_r.update_simple_colors(nodes, self._get_final_color)

        # ---- 7. Renkleri uygula (final_color_for ile) ----
        self.update_sel()

        _progress(1.00, "Tamamlandı")

        # ---- 8. Yükleri güncelle ----
        if hasattr(self, "load_renderer"):
            try:
                cam_scale = self._compute_cam_scale()
                self.load_renderer.update(scene, camera_scale=cam_scale, scene_size=self.size,)
            except Exception as e:
                logger.exception("Load renderer update hatası: %s", e)

    def update_element_color(self, element):
        """Tek bir elemanın rengini bularak sadece onun buffer'ını günceller."""
        if not element:
            return
        
        # Eleman tipine göre ilgili renderer'ı seç
        renderer = None
        el_type = getattr(element, 'element_type', '').lower()
        if el_type == 'frame': renderer = self.frame_r
        elif el_type == 'node': renderer = self.node_r
        elif el_type == 'area': renderer = self.area_r
        elif el_type == 'link': renderer = self.link_r
        elif el_type == 'polygon': renderer = self.polygon_r

        if renderer and hasattr(renderer, 'update_single_element_color'):
            renderer.update_single_element_color(element, self._get_final_color)
        else:
            # Fallback: Eğer alt renderer desteklemiyorsa genel update'e düş
            self.update_sel()
            
    def update_sel(self):
        """
        Seçim renklerini optimize edilmiş şekilde günceller.
        Tüm sahneyi körü körüne işlemek yerine, aktif renderers üzerinden 
        ve gereksiz liste kopyalamalarından kaçınarak çalışır.
        """
        if not self.scene:
            return
        
        # Sözlükleri tekrar tekrar list() ile kopyalamak yerine 
        # doğrudan .values() iteratörünü kullanarak bellek ve CPU yükünü azaltıyoruz.
        renderers_and_elements = (
            (self.frame_r, self.scene.frames.values()),
            (self.node_r, self.scene.nodes.values()),
            (self.area_r, self.scene.areas.values()),
            (self.link_r, self.scene.links.values()),
            (self.polygon_r, self.scene.polygons.values()),
            
        )
        
        get_color = self._get_final_color
        
        for renderer, elements in renderers_and_elements:
            if not renderer or renderer.icount <= 0:
                continue
            
            # Eğer renderer alt seviyede tüm array'i baştan yazıyorsa,
            # en azından Python tarafındaki iterasyon maliyetini minimuma indiriyoruz.
            renderer.update_colors(elements, get_color)
            
            if renderer.simple_vao is not None:
                renderer.update_simple_colors(elements, get_color)
                
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

    def toggle_local_axes(self):
        """Master toggle: tüm local eksenleri aç/kapa."""
        if not self.scene:
            return False
        self.scene.show_local_axes = not self.scene.show_local_axes
        logger.info(f"[Axes] show_local_axes = {self.scene.show_local_axes}")
        return self.scene.show_local_axes

    def toggle_local_axes_selected_only(self):
        """Sadece seçili elemanların eksenleri mi, hepsi mi."""
        if not self.scene:
            return False
        self.scene.show_local_axes_for_selected = not self.scene.show_local_axes_for_selected
        logger.info(f"[Axes] for_selected = {self.scene.show_local_axes_for_selected}")
        return self.scene.show_local_axes_for_selected

    def set_local_axes_scale(self, scale: float):
        """Axes boyut çarpanı."""
        if self.scene:
            self.scene.show_local_axes_scale = float(scale)
            
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

        logger.info("mode=%s show_node=%s node_r.icount=%d",
            self.render_mode, self.show.get('node'), self.node_r.icount if self.node_r else -1)
        
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

        # 4. GRID LABELS
        self._draw_grid_labels_3d(cam)

        # 4.5 LOCAL AXES
        if self.scene and getattr(self.scene, 'show_local_axes', False):
            self._draw_local_axes(cam)

        # 4.7 LOADS (yük görselleri)
        self._draw_loads(cam)

        # 4.8 Plane çizimi tekrar bak!
        if self.plane_draw_mgr and self.plane_draw_mgr.is_active:
            mvp_pdm = p * v * self.model_mat
            self.plane_draw_mgr.render_preview(mvp_pdm, self.overlay_shader)

        # 4.9 Seçili plane (statik)
        if self.selected_plane is not None:
            self._draw_selected_plane(mvp)
            
        # 5. MARQUEE - renkleri düzeltilmiş
        if self.marquee and self.marquee.is_active:
            self._draw_marquee()

    def _draw_loads(self, cam):
        """Frame yüklerini overlay olarak çiz."""
        if not self.scene:
            return
        if not self.load_renderer.enabled:
            return
        

        p = cam.get_projection_matrix()
        v = cam.get_view_matrix()
        mvp = p * v * self.model_mat

        # Yükleri her şeyin üstünde göster
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        try:
            self.load_renderer.render(mvp)
        except Exception as e:
            logger.exception("Load render hatası: %s", e)
        finally:
            # Depth ve blend'i eski haline döndür
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_BLEND)
            
    def _draw_local_axes(self, cam):
        
        
        p = cam.get_projection_matrix()
        v = cam.get_view_matrix()
        base_mvp = p * v
        
        scale = self.size * 0.025 * getattr(self.scene, 'show_local_axes_scale', 1.0)
        only_sel = getattr(self.scene, 'show_local_axes_for_selected', True)
        
        glDisable(GL_DEPTH_TEST)   # overlay gibi üstte çiz
        self.axes_shader.use()
        
        # --- Frame'ler ---
        for f in self.scene.frames.values():
            if not f.is_visible: continue
            if only_sel and not f.is_selected: continue
            if f.show_axes_override is False: continue
            
            R = f.get_local_axes()
            origin = f.get_midpoint()
            
            # column-major 3x3 → 4x4
            R3 = np.array([[R[0][0], R[1][0], R[2][0]],
                        [R[0][1], R[1][1], R[2][1]],
                        [R[0][2], R[1][2], R[2][2]]], dtype=np.float32)
            Rglm = glm.mat3(glm.vec3(*R3[:,0]), glm.vec3(*R3[:,1]), glm.vec3(*R3[:,2]))
            
            M = glm.translate(glm.mat4(1.0), glm.vec3(*origin)) * glm.mat4(Rglm)
            M = glm.scale(M, glm.vec3(scale))
            mvp = base_mvp * M
            
            loc = self.axes_shader.get_loc("u_mvp")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            glBindVertexArray(self.axes_r.vao)
            glDrawArrays(GL_LINES, 0, 6)     # shaft'lar
            glDrawArrays(GL_TRIANGLES, 6, 12) # heads (3 eksen × 4 vertex)
        
        # --- Polygon local axes ---
        for pg in self.scene.polygons.values():
            if not pg.is_visible:
                continue
            if only_sel and not pg.is_selected:
                continue
            if getattr(pg, "show_axes_override", None) is False:
                continue
            if len(pg.nodes) < 3:
                continue

            # Polygon düzlemi için ortonormal frame
            u, v_axis, n = pg.calculate_plane_axes(pg.nodes)

            # Rotasyon matrisi: kolonlar u, v, n (local → global)
            # glm.mat3 column-major: mat3(col0, col1, col2)
            R3 = glm.mat3(u, v_axis, n)

            origin = pg.centroid()   # ya da poly.nodes[0] coords — aşağıda seçenek var

            # Model matrisi: T(origin) · R · S(scale)
            M = glm.mat4(1.0)
            M = glm.translate(M, glm.vec3(*origin))
            M = M * glm.mat4(R3)
            M = glm.scale(M, glm.vec3(scale))

            mvp = base_mvp * M

            loc = self.axes_shader.get_loc("u_mvp")
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

            # Aynı VAO'yu kullan — Frame'lerle aynı ok geometrisi
            glBindVertexArray(self.axes_r.vao)
            glDrawArrays(GL_LINES, 0, 6)
            glDrawArrays(GL_TRIANGLES, 6, 12)
        
        glEnable(GL_DEPTH_TEST)
        glBindVertexArray(0)
        
    def _draw_grid_labels_3d(self, cam):
        if not self.show.get('grid', True):
            return
        if not self.grid or not self.label_batch:
            return

        view = cam.get_view_matrix()
        proj = cam.get_projection_matrix()
        cam_pos = (cam.position.x, cam.position.y, cam.position.z)
        fov_y_rad = math.radians(getattr(cam, "fov", 45.0))

        self.label_batch.begin(
            view=view,
            proj=proj,
            cam_pos=cam_pos,
            screen_h=self.h,
            fov_y_rad=fov_y_rad,
        )

        # ---- 1) GRID AKS ETİKETLERİ ----
        anchors = self.grid.get_label_anchors()
        if anchors:
            n_grid = len(anchors)
            grid_pos = np.empty((n_grid, 3), dtype=np.float32)
            grid_texts = [""] * n_grid
            grid_colors = np.empty((n_grid, 4), dtype=np.float32)

            for i, a in enumerate(anchors):
                grid_pos[i, 0], grid_pos[i, 1], grid_pos[i, 2] = a["pos"]
                grid_texts[i] = a["text"]
                r, g, b, alpha = self._axis_color(a["axis"])
                grid_colors[i] = (r, g, b, alpha)

            self.label_batch.add_many(
                positions=grid_pos,
                texts=grid_texts,
                colors=grid_colors,
                pixel_sizes=14.0,
                anchors="center",
            )

        # ---- 2) SEÇİLİ FRAME ETİKETLERİ ----
        sel_frames = [f for f in self.scene.frames.values() if f.is_selected]
        if sel_frames:
            n_f = len(sel_frames)
            f_pos = np.empty((n_f, 3), dtype=np.float32)
            f_off = np.empty((n_f, 3), dtype=np.float32)
            f_texts = [""] * n_f
            for i, f in enumerate(sel_frames):
                mid = ((f.node_i.x + f.node_j.x) * 0.5,
                        (f.node_i.y + f.node_j.y) * 0.5,
                        (f.node_i.z + f.node_j.z) * 0.5)
                f_pos[i] = mid #(f.node_i.x, f.node_i.y, f.node_i.z)
                f_off[i] = (50.0, 50.0, 50.0)
                f_texts[i] = f"{f.unique_id}"

                
            self.label_batch.add_many(
                positions=f_pos,
                texts=f_texts,
                colors=np.array([1.0, 1.0, 0.3, 1.0], dtype=np.float32),
                pixel_sizes=13.0,
                anchors="bottom-center",
                world_offsets=f_off,
                max_distances=50000.0,
            )

        # ---- 3) SEÇİLİ NODE ETİKETLERİ ----
        sel_nodes = [n for n in self.scene.nodes.values() if n.is_selected]
        if sel_nodes:
            n_n = len(sel_nodes)
            n_pos = np.empty((n_n, 3), dtype=np.float32)
            n_texts = [""] * n_n
            for i, n in enumerate(sel_nodes):
                n_pos[i] = (n.x, n.y, n.z)
                n_texts[i] = f"N{n.label}"

            self.label_batch.add_many(
                positions=n_pos,
                texts=n_texts,
                colors=np.array([0.3, 0.9, 1.0, 1.0], dtype=np.float32),
                pixel_sizes=12.0,
                anchors="top-center",
            )

        # ---- 4) TEK DRAW CALL ----
        self.label_batch.flush()

    def _axis_color(self, axis: str):
        if axis == "X": return (0.95, 0.35, 0.35, 1.0)
        if axis == "Y": return (0.35, 0.95, 0.45, 1.0)
        if axis == "Z": return (0.40, 0.65, 1.00, 1.0)
        return (1.0, 1.0, 1.0, 1.0)

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
        # glPointSize(1.0)
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
            self.node_r.render_simple(mvp, self.node_shader, alpha=1.0)
            # ── Restraint çizgileri ──
            if self.show.get('restraint', True):
                self.node_r.render_simple_restraint_lines(mvp, self.simple_shader, alpha=1.0)
        glEnable(GL_DEPTH_TEST)

        
        glEnable(GL_DEPTH_TEST)
    
    def get_bounds(self):
        return self.center, self.size
    
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
        # Aks listeleri GridSystem içinde yönetildiği için burada sadece yenileme tetiklenir
        self.grid.rebuild_all()
    
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
        for r in [self.frame_r, self.node_r, self.area_r, self.link_r,
              self.polygon_r, self.grid, self.pick_pass, self.snap,
              self.load_renderer]:   # ← ekle
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

    def apply_plane_filter(self, camera):
        if self.scene is None:
            return

        test = camera.is_element_visible_by_section

        for node in self.scene.nodes.values():
            node.is_visible = test((node.x, node.y, node.z))

        for frame in self.scene.frames.values():
            ni, nj = frame.node_i, frame.node_j
            mx = (ni.x + nj.x) * 0.5
            my = (ni.y + nj.y) * 0.5
            mz = (ni.z + nj.z) * 0.5
            frame.is_visible = test((mx, my, mz))

        for area in self.scene.areas.values():
            if not area.nodes:
                continue
            mx = sum(n.x for n in area.nodes) / len(area.nodes)
            my = sum(n.y for n in area.nodes) / len(area.nodes)
            mz = sum(n.z for n in area.nodes) / len(area.nodes)
            area.is_visible = test((mx, my, mz))

        for link in self.scene.links.values():
            ni, nj = link.node_i, link.node_j
            mx = (ni.x + nj.x) * 0.5
            my = (ni.y + nj.y) * 0.5
            mz = (ni.z + nj.z) * 0.5
            link.is_visible = test((mx, my, mz))

        for poly in self.scene.polygons.values():
            if not poly.nodes:
                continue
            mx = sum(n.x for n in poly.nodes) / len(poly.nodes)
            my = sum(n.y for n in poly.nodes) / len(poly.nodes)
            mz = sum(n.z for n in poly.nodes) / len(poly.nodes)
            poly.is_visible = test((mx, my, mz))

    def _compute_cam_scale(self):
        if not self.camera:
            return 1.0
        try:
            d = float(np.linalg.norm(np.array(self.camera.position) - np.array(self.center)))
            base = max(0.6, min(2.5, d / 10000.0))
            return base * getattr(self, '_load_scale_override', 1.0)
        except Exception:
            return getattr(self, '_load_scale_override', 1.0)

    def _draw_selected_plane(self, mvp):
        plane = self.selected_plane
        
        if plane is None or self.overlay_shader is None:
            return

        # VAO/VBO lazy init
        if self._sel_plane_tri_vao is None:
            self._sel_plane_tri_vao = glGenVertexArrays(1)
            self._sel_plane_tri_vbo = glGenBuffers(1)
            self._sel_plane_line_vao = glGenVertexArrays(1)
            self._sel_plane_line_vbo = glGenBuffers(1)

        shader = self.overlay_shader
        shader.use()
        if self._overlay_mvp_loc != -1:
            glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))
        if self._overlay_color_loc == -1:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)
        from OpenGL.GL import GL_FALSE as GLF
        from OpenGL.GL import glDepthMask
        glDepthMask(GLF)
        try:
            self._render_plane_solid(plane, shader)
        finally:
            from OpenGL.GL import GL_TRUE, glDepthMask
            glDepthMask(GL_TRUE)
            glDisable(GL_BLEND)

    def _render_plane_solid(self, plane, shader):
        """Verilen plane için 8-köşe kutu çiz."""
        import numpy as np
        
        # u/v aralıkları
        u0 = plane.u_min if plane.u_min is not None else -1000.0
        u1 = plane.u_max if plane.u_max is not None else 1000.0
        v0 = plane.v_min if plane.v_min is not None else -1000.0
        v1 = plane.v_max if plane.v_max is not None else 1000.0
        
        def corner(u, v, d):
            return plane.origin + u * plane.u + v * plane.v + d * plane.normal
        
        # 8 köşe
        b00 = corner(u0, v0, -plane.depth_minus)
        b10 = corner(u1, v0, -plane.depth_minus)
        b11 = corner(u1, v1, -plane.depth_minus)
        b01 = corner(u0, v1, -plane.depth_minus)
        t00 = corner(u0, v0, +plane.depth_plus)
        t10 = corner(u1, v0, +plane.depth_plus)
        t11 = corner(u1, v1, +plane.depth_plus)
        t01 = corner(u0, v1, +plane.depth_plus)
        
        # 6 yüz × 2 üçgen
        tris = []
        tris.extend([*t00, *t10, *t11, *t00, *t11, *t01])   # üst
        tris.extend([*b00, *b11, *b10, *b00, *b01, *b11])   # alt
        for a, b, c, d in [
            (b00, b10, t10, t00),
            (b10, b11, t11, t10),
            (b11, b01, t01, t11),
            (b01, b00, t00, t01),
        ]:
            tris.extend([*a, *b, *c, *a, *c, *d])
        
        arr = np.array(tris, dtype=np.float32)
        glBindVertexArray(self._sel_plane_tri_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._sel_plane_tri_vbo)
        glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3*4, None)
        glUniform4f(self._overlay_color_loc, 0.30, 0.60, 1.00, 0.15)   # mavi yarı saydam
        glDrawArrays(GL_TRIANGLES, 0, len(arr)//3)
        
        # Kenarlar
        edges = []
        for a, b in [(t00,t10),(t10,t11),(t11,t01),(t01,t00),
                    (b00,b10),(b10,b11),(b11,b01),(b01,b00),
                    (b00,t00),(b10,t10),(b11,t11),(b01,t01)]:
            edges.extend([*a, *b])
        edge_arr = np.array(edges, dtype=np.float32)
        glBindVertexArray(self._sel_plane_line_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._sel_plane_line_vbo)
        glBufferData(GL_ARRAY_BUFFER, edge_arr.nbytes, edge_arr, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3*4, None)
        glUniform4f(self._overlay_color_loc, 0.55, 0.80, 1.00, 0.90)   # açık mavi kenar
        glDrawArrays(GL_LINES, 0, len(edge_arr)//3)


    def set_render_mode(self, mode: str):
        if mode not in self.RENDER_MODES:
            raise ValueError(f"Geçersiz render modu: {mode}")
        self.render_mode = mode
        logger.info(f"Render modu: {mode}")

    def get_render_mode(self) -> str:
        return self.render_mode

    def set_show(self, key: str, value: bool):
        if key in self.show:
            self.show[key] = bool(value)

    def get_show(self) -> dict:
        return dict(self.show)

    def set_use_lights(self, enabled: bool):
        self.use_lights = bool(enabled)

    def set_loads_enabled(self, enabled: bool):
        if self.load_renderer:
            self.load_renderer.enabled = bool(enabled)

    def set_load_scale(self, scale: float):
        """Kamera-bazlı ölçeğe çarpan ekle."""
        self._load_scale_override = float(scale)
        if self.scene and self.load_renderer:
            cam_scale = self._compute_cam_scale() * self._load_scale_override
            self.load_renderer.update(self.scene, camera_scale=cam_scale)

    def _draw_marquee(self):
        if not self.marquee or not self.marquee.is_active:
            return
        coords = self.marquee.get_box_coords()
        if not coords:
            return
        x1, y1, x2, y2 = coords
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        cross = x2 < x1

        # VAO/VBO bir kez oluştur
        if self._marquee_ov_vao is None:
            self._marquee_ov_vao = glGenVertexArrays(1)
            self._marquee_ov_vbo = glGenBuffers(1)
            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glBindVertexArray(0)

        # State kaydet
        depth_was_on = glIsEnabled(GL_DEPTH_TEST) != 0
        blend_was_on = glIsEnabled(GL_BLEND) != 0
        lw_prev = glGetFloatv(GL_LINE_WIDTH)

        try:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            self.overlay_shader.use()

            proj = glm.ortho(0.0, float(self.w), float(self.h), 0.0, -1.0, 1.0)
            if self._overlay_mvp_loc != -1:
                glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(proj))
            if self._overlay_color_loc == -1:
                return

            mn_x, mx_x = min(x1, x2), max(x1, x2)
            mn_y, mx_y = min(y1, y2), max(y1, y2)
            verts = np.array([mn_x, mn_y, 0, mx_x, mn_y, 0,
                            mx_x, mx_y, 0, mn_x, mx_y, 0], dtype=np.float32)

            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)

            if cross:
                fill, border = (0.2,0.8,0.2,0.3), (0.2,1.0,0.2,0.9)
            else:
                fill, border = (0.2,0.5,0.9,0.3), (0.4,0.7,1.0,0.9)

            glUniform4f(self._overlay_color_loc, *fill)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

            glLineWidth(1.5)
            glUniform4f(self._overlay_color_loc, *border)
            glDrawArrays(GL_LINE_LOOP, 0, 4)
        finally:
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glLineWidth(float(lw_prev))
            if not blend_was_on:
                glDisable(GL_BLEND)
            if depth_was_on:
                glEnable(GL_DEPTH_TEST)