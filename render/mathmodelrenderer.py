# render/scenerenderer.py
import math
from dataclasses import dataclass

from pyglm import glm
import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger
from render.base_renderer import (
    AreaRenderer,
    FrameRenderer,
    LinkRenderer,
    _final_color_for,
)
from render.light_ubo import LightUBO
from render.lightingsystem import LightingSystem
from render.node_renderer import NodeRenderer
from render.pickpass import PickPass
from render.gl_utils import mat4_data


logger = CadLogger.get(__name__)

@dataclass
class RenderStats:
    frame: int = 0
    node: int = 0
    area: int = 0
    link: int = 0
    tri: int = 0

class MathModelRenderer:
    RENDER_MODES = ('shaded', 'line', 'simple', 'normal')
    
    def __init__(self, pick_s, standard_s, node_s, simple_s, overlay_s, axes_s, w=1024, h=768):
        self.pick_s = pick_s
        self.standard_shader = standard_s
        self.node_shader = node_s
        self.simple_shader = simple_s
        self.overlay_shader = overlay_s
        self.axes_shader = axes_s

        self.math_model = None
        self.camera = self.engine = None
        self.render_mode = 'simple'

        # Projeksiyon (3D ↔ 2D görünüm)
        self.projection: str = "3d"
        self._saved_render_mode: str = "shaded"
        
        # --- YALNIZCA KALICI GEOMETRİ RENDERER'LARI ---
        self.frame_r = FrameRenderer(self.standard_shader)
        self.area_r = AreaRenderer(self.standard_shader)
        self.link_r = LinkRenderer(self.standard_shader)
        self.node_r = NodeRenderer(self.standard_shader)

        # PickPass - MRT'den ID okumak için
        self.pick_pass = PickPass()
        self.pick_pass.set_viewport(w, h)
        
        self.lighting = LightingSystem()
        self.light_ubo = LightUBO()
        
        self.snap = None

        self.show = {
            'grid': True, 'axes': True, 'area': True,
            'frame': True, 'link': True, 'node': True,
        }
        self.use_lights = True
        
        self.model_mat = glm.mat4(1.0)
        self.w = w
        self.h = h
        
        self.center = np.zeros(3)
        self.size = 1.0

    def set_cam(self, c): self.camera = c
    def set_grid(self, g): self.grid = g
    def set_math_model(self, math_model): self.math_model = math_model
    def set_snap(self, s): self.snap = s
    def set_lighting(self, lighting): self.lighting = lighting

    def set_node_point_size(self, px: float):
        if self.node_r:
            self.node_r.set_point_size(px)

    def set_node_size(self, size: float, rebuild: bool = True):
        if not self.node_r:
            return
        changed = self.node_r.set_node_size(size)
        if changed and rebuild and self.math_model:
            nodes = list(self.math_model.nodes.values())
            for n in nodes:
                n.mark_dirty()
            self.node_r.update(nodes)
            self.node_r.update_colors(nodes, self._get_final_color)
            self.node_r.update_simple_colors(nodes, self._get_final_color)

    def set_engine(self, e):
        self.engine = e
        self.w = self.engine.w
        self.h = self.engine.h
        self.resize(self.w, self.h)
        # Engine.mrt'yi PickPass'e bağla:
        if self.pick_pass and self.engine.mrt:
            self.pick_pass.set_main_fbo(self.engine.mrt.fbo)
    
    def resize(self, w, h):
        self.w = w
        self.h = h
        if self.pick_pass:
            self.pick_pass.set_viewport(w, h)

    def update_geo(self, scene=None, progress_cb=None):
        if scene is None:
            scene = self.math_model

        flt = getattr(scene, '_render_filter', None)
        use_section = self.camera is not None and self.camera.section_active

        def _f(d):
            if flt is None and not use_section:
                return list(d.values())
            result = []
            for e in d.values():
                if flt is not None and e.unique_id not in flt:
                    continue
                if use_section and not self._element_in_section(e):
                    continue
                result.append(e)
            return result

        frames = _f(scene.frames)
        nodes = _f(scene.nodes)
        areas = _f(scene.areas)
        links = _f(scene.links)

        if self.pick_pass and hasattr(self.pick_pass, 'clear_registry'):
            self.pick_pass.clear_registry()

        def _progress(value, msg=""):
            if progress_cb:
                try: progress_cb(value, msg)
                except Exception: pass

        _progress(0.00, "Geometri güncelleniyor...")
        self.math_model = scene

        for frame in frames: frame.pick_id = frame.unique_id
        for node in nodes:   node.pick_id = node.unique_id
        for area in areas:   area.pick_id = area.unique_id
        for link in links:   link.pick_id = link.unique_id

        self.frame_r.update(frames)
        self.node_r.update(nodes)
        self.area_r.update(areas)
        self.link_r.update(links)

        for frame in frames: self.pick_pass.register(frame.pick_id, frame, self.frame_r)
        for node in nodes:   self.pick_pass.register(node.pick_id, node, self.node_r)
        for area in areas:   self.pick_pass.register(area.pick_id, area, self.area_r)
        for link in links:   self.pick_pass.register(link.pick_id, link, self.link_r)

        self._update_bounds()
        self.update_sel()
        _progress(1.00, "Tamamlandı")

    def update_element_color(self, element):
        if not element: return
        renderer = None
        el_type = getattr(element, 'element_type', '').lower()
        if el_type == 'frame': renderer = self.frame_r
        elif el_type == 'node': renderer = self.node_r
        elif el_type == 'area': renderer = self.area_r
        elif el_type == 'link': renderer = self.link_r

        if renderer and hasattr(renderer, 'update_single_element_color'):
            renderer.update_single_element_color(element, self._get_final_color)
        else:
            self.update_sel()
            
    def update_sel(self):
        if not self.math_model: return
        renderers_and_elements = (
            (self.frame_r, self.math_model.frames.values()),
            (self.node_r, self.math_model.nodes.values()),
            (self.area_r, self.math_model.areas.values()),
            (self.link_r, self.math_model.links.values()),
        )
        get_color = self._get_final_color
        for renderer, elements in renderers_and_elements:
            if not renderer or renderer.icount <= 0: continue
            renderer.update_colors(elements, get_color)
            if renderer.simple_vao is not None:
                renderer.update_simple_colors(elements, get_color)
                
    def _get_final_color(self, element):
        return _final_color_for(element) 

    def toggle_projection(self) -> bool:
        if self.camera is None: return False
        if self.projection == "plane_2d":
            self.camera.restore_view()
            self.render_mode = self._saved_render_mode
            self.projection = "3d"
            return True

        self._saved_render_mode = self.render_mode
        self.camera.save_view()
        self.camera.set_top_view()
        self.render_mode = "simple"
        self.projection = "plane_2d"
        return True
    
    def toggle_render_mode(self):
        modes = ['shaded', 'line', 'simple', 'normal']
        idx = modes.index(self.render_mode) if self.render_mode in modes else 0
        self.render_mode = modes[(idx + 1) % len(modes)]
        return self.render_mode

    def render(self, cam, target_fbo=0):
        if not cam:
            return

        v = cam.get_view_matrix()
        p = cam.get_projection_matrix()
        mvp = p * v * self.model_mat
        cpos = glm.vec3(cam.position.x, cam.position.y, cam.position.z)

        if self.use_lights:
            self.light_ubo.update(self.lighting, (cpos.x, cpos.y, cpos.z))

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        mode = 0 if self.render_mode == "normal" else 1
        for r in (self.frame_r, self.node_r, self.area_r, self.link_r):
            if r:
                r.render_mode = mode

        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        if self.render_mode in ("shaded", "normal"):
            self._render_shaded(mvp, cpos, v, p)
        elif self.render_mode == "line":
            self._render_line(mvp)
        elif self.render_mode == "simple":
            self._render_simple(mvp)

        self._render_id_pass(mvp)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

    # ------------------------------------------------------------------
    def _render_shaded(self, mvp, cpos, v, p):
        if self.show["area"] and self.area_r:
            self.area_r.render(mvp, self.model_mat, cpos, v, p)
        if self.show["frame"] and self.frame_r:
            self.frame_r.render(mvp, self.model_mat, cpos, v, p)
        if self.show["link"] and self.link_r:
            self.link_r.render(mvp, self.model_mat, cpos, v, p)
        if self.show["node"] and self.node_r:
            self.node_r.render(mvp, self.model_mat, cpos, v, p)

    def _render_line(self, mvp):
        if not (self.simple_shader and self.show["frame"] and self.frame_r):
            return
        self.simple_shader.use()
        loc = self.simple_shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        self.frame_r.render_line(self.simple_shader)

    def _render_simple(self, mvp):
        if not self.simple_shader:
            return
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)

        if self.show["frame"] and self.frame_r:
            self.frame_r.render_simple(mvp, self.simple_shader, alpha=1.0)

        if self.show["area"] and self.area_r:
            glDepthMask(GL_FALSE)
            self.area_r.render_simple(mvp, self.simple_shader, alpha=0.35)
            glDepthMask(GL_TRUE)

        if self.show["link"] and self.link_r:
            self.link_r.render_simple(mvp, self.simple_shader, alpha=1.0)

        glDisable(GL_DEPTH_TEST)
        if self.show["node"] and self.node_r:
            self.node_r.render_simple(mvp, self.node_shader, alpha=1.0)
            if self.show.get("restraint", True):
                self.node_r.render_simple_restraint_lines(mvp, self.simple_shader, alpha=1.0)
        glEnable(GL_DEPTH_TEST)

    def _render_id_pass(self, mvp):
        if not (self.engine and self.engine.pick_s and self.engine.mrt):
            return

        depth_test = glIsEnabled(GL_DEPTH_TEST)
        blend = glIsEnabled(GL_BLEND)
        depth_mask = bool(glGetBooleanv(GL_DEPTH_WRITEMASK))

        glDrawBuffer(GL_COLOR_ATTACHMENT1)
        glDepthMask(GL_TRUE)
        glClear(GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_BLEND)

        pick_s = self.engine.pick_s
        pick_s.use()
        loc = pick_s.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, mat4_data(mvp))

        if self.show["area"] and self.area_r:
            self.area_r.render_simple(mvp, pick_s, alpha=1.0)
        if self.show["frame"] and self.frame_r:
            self.frame_r.render_simple(mvp, pick_s, alpha=1.0)
        if self.show["link"] and self.link_r:
            self.link_r.render_simple(mvp, pick_s, alpha=1.0)
        if self.show["node"] and self.node_r:
            self.node_r.render_simple(mvp, pick_s, alpha=1.0, point_size=10.0)

        glDepthMask(GL_TRUE if depth_mask else GL_FALSE)
        if depth_test:
            glEnable(GL_DEPTH_TEST)
        else:
            glDisable(GL_DEPTH_TEST)
        if blend:
            glEnable(GL_BLEND)
        else:
            glDisable(GL_BLEND)

    def get_bounds(self):
        return self.center, self.size
    
    def pick_async(self, x, y):
        return self.pick_pass.pick_async(x, y) if self.pick_pass else False
    
    def check_pick(self):
        return self.pick_pass.check_pick() if self.pick_pass else (None, None, None)
    
    def get_element_from_id(self, pick_id):
        return self.pick_pass.get_element(pick_id) if self.pick_pass else None

    def update_dirty(self):
        for renderer in [self.frame_r, self.node_r, self.area_r, self.link_r]:
            if renderer: renderer.update_dirty()
    
    def _update_bounds(self):
        bounds = self.math_model.bounds if self.math_model else None
        if bounds is None:
            self.center = np.zeros(3)
            self.size = 1.0
            return
        self.center = bounds.center.copy()
        self.size = bounds.size or 1.0

    def cleanup(self):
        for r in [self.frame_r, self.node_r, self.area_r, self.link_r, self.pick_pass]:
            if r and hasattr(r, 'cleanup'): r.cleanup()

    def set_render_mode(self, mode: str):
        if mode not in self.RENDER_MODES:
            raise ValueError(f"Geçersiz render modu: {mode}")
        self.render_mode = mode

    def get_render_mode(self) -> str:
        return self.render_mode

    def set_show(self, key: str, value: bool):
        if key in self.show:
            self.show[key] = bool(value)

    def get_show(self) -> dict:
        return dict(self.show)

    def set_use_lights(self, enabled: bool):
        self.use_lights = bool(enabled)

    def _element_in_section(self, el) -> bool:
        for pt in self._element_points(el):
            if self.camera.is_element_visible_by_section(pt):
                return True
        return False
    
    def set_restraint_size(self, size: float) -> bool:
            if self.node_r:
                changed = self.node_r.builder.set_restraint_size(size)
                if changed and self.node_r.elements:
                    self.node_r.update(list(self.node_r.elements))
                return changed
            return False
    
    @staticmethod
    def _element_points(el):
        kind = getattr(el, "element_type", "").lower()
        if kind == "node":
            return [(el.x, el.y, el.z)]
        if kind in ("frame", "link"):
            ni = getattr(el, "node_i", None)
            nj = getattr(el, "node_j", None)
            if ni is None or nj is None:
                return []
            return [(ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z)]
        if kind == "area":
            return [(n.x, n.y, n.z) for n in getattr(el, "nodes", [])]
        return []