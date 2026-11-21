from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from plane.plane_policy import SectionFilterMode
from render.base_renderer import (
    AreaRenderer,
    FrameRenderer,
    LinkRenderer,
    _final_color_for,
)
from render.gl_utils import mat4_data
from render.light_ubo import LightUBO
from render.lightingsystem import LightingSystem
from render.line_renderer import LineRenderer
from render.node_renderer import NodeRenderer
from render.pickpass import PickPass
from render.polygonrenderer import PolygonRenderer


@dataclass
class RenderStats:
    frame: int = 0
    node: int = 0
    area: int = 0
    link: int = 0
    tri: int = 0


class MathModelRenderer:
    RENDER_MODES = ("simple", "shaded")

    def __init__(
        self, pick_s, standard_s, node_s, simple_s, overlay_s, axes_s,
        w=1024, h=768, create_pick_pass=True,
    ):
        self.pick_s = pick_s
        self.standard_shader = standard_s
        self.node_shader = node_s
        self.simple_shader = simple_s
        self.overlay_shader = overlay_s
        self.axes_shader = axes_s

        self.math_model = None
        self.camera = None
        self._render_elements = {
            "frames": [], "nodes": [], "areas": [], "links": [],
            "polygons": [], "lines": [],
        }
        self.render_mode = "simple"
        self.projection: str = "3d"

        self.frame_r = FrameRenderer(self.standard_shader)
        self.area_r = AreaRenderer(self.standard_shader)
        self.link_r = LinkRenderer(self.standard_shader)
        self.node_r = NodeRenderer(self.standard_shader)
        self.polygon_r = PolygonRenderer(self.simple_shader or self.standard_shader)
        self.line_r = LineRenderer(self.simple_shader or self.standard_shader)

        self.pick_pass = PickPass() if create_pick_pass else None
        if self.pick_pass:
            self.pick_pass.set_viewport(w, h)

        self.lighting = LightingSystem()
        self.light_ubo = LightUBO()

        self.show = {
            "grid": True, "axes": True, "area": True,
            "frame": True, "link": True, "node": True,
            "polygon": True, "lines": True,
        }
        self.assoc_preview = None
        self.use_lights = True

        self.model_mat = glm.mat4(1.0)
        self.w = w
        self.h = h

        self.center = np.zeros(3)
        self.size = 1.0

    def set_cam(self, c):
        self.camera = c

    def set_math_model(self, math_model):
        self.math_model = math_model

    def set_lighting(self, lighting):
        self.lighting = lighting

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

    def resize(self, w, h):
        self.w = w
        self.h = h
        if self.pick_pass:
            self.pick_pass.set_viewport(w, h)

    def update_geo(
        self, scene=None, progress_cb=None, *, frames=None, nodes=None,
        areas=None, links=None, polygons=None, lines=None,
    ):
        if scene is None:
            scene = self.math_model
        if scene is None:
            return
        flt = getattr(scene, "_render_filter", None)

        def _f(d, prepared):
            elements = list(d.values()) if prepared is None else list(prepared)
            if flt is None:
                return elements
            return [e for e in elements if e.unique_id in flt]

        frames = _f(scene.frames, frames)
        nodes = _f(scene.nodes, nodes)
        areas = _f(scene.areas, areas)
        links = _f(scene.links, links)
        polygons = _f(scene.polygons, polygons)
        lines = _f(scene.lines, lines)

        self._render_elements = {
            "frames": frames, "nodes": nodes, "areas": areas, "links": links,
            "polygons": polygons, "lines": lines,
        }

        if self.pick_pass and hasattr(self.pick_pass, "clear_registry"):
            self.pick_pass.clear_registry()

        self.math_model = scene

        self.frame_r.update(frames)
        self.node_r.update(nodes)
        self.area_r.update(areas)
        self.link_r.update(links)
        self.polygon_r.update(polygons)
        self.line_r.update(lines)

        if self.pick_pass:
            for frame in frames:
                frame.pick_id = frame.unique_id
                self.pick_pass.register(
                    frame.pick_id, getattr(frame, "_geometry_source", frame),
                    self.frame_r,
                )
            for node in nodes:
                node.pick_id = node.unique_id
                self.pick_pass.register(node.pick_id, node, self.node_r)
            for area in areas:
                area.pick_id = area.unique_id
                self.pick_pass.register(
                    area.pick_id, getattr(area, "_geometry_source", area),
                    self.area_r,
                )
            for link in links:
                link.pick_id = link.unique_id
                self.pick_pass.register(
                    link.pick_id, getattr(link, "_geometry_source", link),
                    self.link_r,
                )
            for polygon in polygons:
                polygon.pick_id = polygon.unique_id
                self.pick_pass.register(
                    polygon.pick_id,
                    getattr(polygon, "_geometry_source", polygon),
                    self.polygon_r,
                )
            for line in lines:
                line.pick_id = line.unique_id
                self.pick_pass.register(
                    line.pick_id, getattr(line, "_geometry_source", line),
                    self.line_r,
                )

        self._update_bounds()
        self.update_sel()

    def update_polygons(self, polygons):
        items = list(polygons)
        self._render_elements["polygons"] = items
        if self.polygon_r:
            self.polygon_r.update(items)

    def update_lines(self, lines):
        items = list(lines)
        self._render_elements["lines"] = items
        if self.line_r:
            self.line_r.update(items)

    def update_element_color(self, element):
        if not element:
            return
        renderer = None
        el_type = getattr(element, "element_type", "").lower()
        if el_type == "frame":
            renderer = self.frame_r
        elif el_type == "node":
            renderer = self.node_r
        elif el_type == "area":
            renderer = self.area_r
        elif el_type == "link":
            renderer = self.link_r

        if renderer and hasattr(renderer, "update_single_element_color"):
            renderer.update_single_element_color(element, self._get_final_color)
        else:
            self.update_sel()

    def update_sel(self):
        if not self.math_model:
            return
        renderers_and_elements = (
            (self.frame_r, self._render_elements["frames"]),
            (self.node_r, self._render_elements["nodes"]),
            (self.area_r, self._render_elements["areas"]),
            (self.link_r, self._render_elements["links"]),
            (self.polygon_r, self._render_elements["polygons"]),
            (self.line_r, self._render_elements["lines"]),
        )
        for _, elements in renderers_and_elements:
            for element in elements:
                source = getattr(element, "_geometry_source", element)
                if source is not element:
                    element.is_selected = getattr(source, "is_selected", False)

        get_color = self._get_final_color
        for renderer, elements in renderers_and_elements:
            if not renderer:
                continue
            if renderer.cbo is not None:
                renderer.update_colors(elements, get_color)
            if renderer.simple_cbo is not None:
                renderer.update_simple_colors(elements, get_color)

    def _get_final_color(self, element):
        preview = self.assoc_preview
        if preview is not None and getattr(preview, "active", False):
            if getattr(element, "element_type", "") == "Frame":
                uid = getattr(element, "unique_id", None)
                if getattr(element, "is_selected", False):
                    return (1.0, 1.0, 0.4, 1.0)
                if uid in preview.associated:
                    return (0.30, 0.95, 0.30, 1.0)
                if uid in preview.excluded:
                    return (0.95, 0.35, 0.35, 1.0)
                return (0.45, 0.45, 0.45, 0.35)
        return _final_color_for(element)

    def toggle_render_mode(self):
        modes = ["simple", "shaded"]
        idx = modes.index(self.render_mode) if self.render_mode in modes else 0
        self.render_mode = modes[(idx + 1) % len(modes)]
        return self.render_mode

    def _apply_clip_uniforms(self, shader, plane):
        if shader is None:
            return
        active = (
            plane is not None
            and getattr(plane, "filter_mode", None) == SectionFilterMode.CLIP
        )
        shader.use()
        shader.set_int("u_clip_active", 1 if active else 0)
        if not active:
            return
        shader.set_vec3("u_plane_origin", *plane.origin)
        shader.set_vec3("u_plane_normal", *plane.normal)
        shader.set_vec3("u_plane_u", *plane.u)
        shader.set_vec3("u_plane_v", *plane.v)
        shader.set_float("u_u_min", plane.u_min if plane.u_min is not None else -1e30)
        shader.set_float("u_u_max", plane.u_max if plane.u_max is not None else 1e30)
        shader.set_float("u_v_min", plane.v_min if plane.v_min is not None else -1e30)
        shader.set_float("u_v_max", plane.v_max if plane.v_max is not None else 1e30)
        shader.set_float("u_depth_minus", plane.depth_minus)
        shader.set_float("u_depth_plus", plane.depth_plus)

    def render(self, cam, target_fbo=0, force_id_pass=False, plane=None, visible_ids=None):
        if not cam:
            return

        for shader in (self.standard_shader, self.simple_shader, self.node_shader, self.pick_s):
            self._apply_clip_uniforms(shader, plane)

        v = cam.get_view_matrix()
        p = cam.get_projection_matrix()
        mvp = p * v * self.model_mat
        cpos = glm.vec3(cam.position.x, cam.position.y, cam.position.z)

        if self.use_lights:
            self.light_ubo.update(self.lighting, (cpos.x, cpos.y, cpos.z))

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        mode = 1 if self.render_mode == "shaded" else 0
        for r in (self.frame_r, self.node_r, self.area_r, self.link_r):
            if r:
                r.render_mode = mode

        glDrawBuffer(GL_COLOR_ATTACHMENT0)

        if self.render_mode == "shaded":
            self._render_shaded(mvp, cpos, v, p, visible_ids)
        else:
            self._render_simple(mvp, visible_ids)

        if force_id_pass and self.pick_s is not None:
            self._render_id_pass(mvp, visible_ids)

        glDrawBuffer(GL_COLOR_ATTACHMENT0)

    def _render_shaded(self, mvp, cpos, v, p, visible_ids=None):
        self._render_polygon_lines(mvp, visible_ids)
        if self.show["area"] and self.area_r:
            self.area_r.render(mvp, self.model_mat, cpos, v, p, visible_ids=visible_ids)
        if self.show["frame"] and self.frame_r:
            self.frame_r.render(mvp, self.model_mat, cpos, v, p, visible_ids=visible_ids)
        if self.show["link"] and self.link_r:
            self.link_r.render(mvp, self.model_mat, cpos, v, p, visible_ids=visible_ids)
        if self.show["node"] and self.node_r:
            self.node_r.render(mvp, self.model_mat, cpos, v, p, visible_ids=visible_ids)

    def _render_simple(self, mvp, visible_ids=None):
        if not self.simple_shader:
            return
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)

        self._render_polygon_lines(mvp, visible_ids)

        if self.show["frame"] and self.frame_r:
            self.frame_r.render_simple(mvp, self.simple_shader, alpha=1.0, visible_ids=visible_ids)

        if self.show["area"] and self.area_r:
            glDepthMask(GL_FALSE)
            self.area_r.render_simple(mvp, self.simple_shader, alpha=0.35, visible_ids=visible_ids)
            glDepthMask(GL_TRUE)

        if self.show["link"] and self.link_r:
            self.link_r.render_simple(mvp, self.simple_shader, alpha=1.0, visible_ids=visible_ids)

        glDisable(GL_DEPTH_TEST)
        if self.show["node"] and self.node_r:
            self.node_r.render_simple(mvp, self.node_shader, alpha=1.0, visible_ids=visible_ids)
            if self.show.get("restraint", True):
                self.node_r.render_simple_restraint_lines(mvp, self.simple_shader, alpha=1.0)
        glEnable(GL_DEPTH_TEST)

    def _render_polygon_lines(self, mvp, visible_ids=None):
        shader = self.simple_shader or self.standard_shader
        if self.show["polygon"] and self.polygon_r:
            glDepthMask(GL_FALSE)
            self.polygon_r.render_simple(mvp, shader, alpha=0.5, visible_ids=visible_ids)
            glDepthMask(GL_TRUE)
        if self.show["lines"] and self.line_r:
            self.line_r.draw(mvp, visible_ids=visible_ids)

    def _render_id_pass(self, mvp, visible_ids=None):
        pick_s = self.pick_s
        if pick_s is None:
            return

        depth_test = glIsEnabled(GL_DEPTH_TEST)
        blend = glIsEnabled(GL_BLEND)
        depth_mask = bool(glGetBooleanv(GL_DEPTH_WRITEMASK))

        glDrawBuffer(GL_COLOR_ATTACHMENT1)
        glDepthMask(GL_TRUE)
        glClear(GL_DEPTH_BUFFER_BIT)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_BLEND)

        pick_s.use()
        loc = pick_s.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, mat4_data(mvp))

        if self.show["area"] and self.area_r:
            self.area_r.render_simple(mvp, pick_s, alpha=1.0, visible_ids=visible_ids)
        if self.show["frame"] and self.frame_r:
            self.frame_r.render_simple(mvp, pick_s, alpha=1.0, visible_ids=visible_ids)
        if self.show["link"] and self.link_r:
            self.link_r.render_simple(mvp, pick_s, alpha=1.0, visible_ids=visible_ids)
        if self.show["node"] and self.node_r:
            self.node_r.render_simple(mvp, pick_s, alpha=1.0, point_size=10.0, visible_ids=visible_ids)
        if self.show["polygon"] and self.polygon_r:
            self.polygon_r.render_pick(mvp, pick_s, visible_ids=visible_ids)
        if self.show["lines"] and self.line_r:
            self.line_r.render_pick(mvp, pick_s, visible_ids=visible_ids)

        glDepthMask(GL_TRUE if depth_mask else GL_FALSE)
        if depth_test:
            glEnable(GL_DEPTH_TEST)
        else:
            glDisable(GL_DEPTH_TEST)
        if blend:
            glEnable(GL_BLEND)
        else:
            glDisable(GL_BLEND)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

    def get_bounds(self):
        return self.center, self.size

    def get_element_from_id(self, pick_id):
        return self.pick_pass.get_element(pick_id) if self.pick_pass else None

    def update_dirty(self):
        for renderer in (
            self.frame_r, self.node_r, self.area_r, self.link_r,
            self.polygon_r, self.line_r,
        ):
            if renderer:
                renderer.update_dirty()

    def _update_bounds(self):
        bounds = self.math_model.bounds if self.math_model else None
        if bounds is None:
            self.center = np.zeros(3)
            self.size = 1.0
            return
        self.center = bounds.center.copy()
        self.size = bounds.size or 1.0

    def cleanup(self):
        for r in (
            self.frame_r, self.node_r, self.area_r, self.link_r,
            self.polygon_r, self.line_r, self.pick_pass,
        ):
            if r and hasattr(r, "cleanup"):
                r.cleanup()

    def set_render_mode(self, mode: str):
        if mode not in self.RENDER_MODES:
            raise ValueError(f"Geçersiz render modu: {mode}")
        self.render_mode = mode

    def get_render_mode(self) -> str:
        return self.render_mode

    def set_assoc_preview(self, preview):
        self.assoc_preview = preview
        if not self.math_model:
            return
        frames = self._render_elements.get("frames") or []
        if self.frame_r and frames:
            self.frame_r.update_colors(frames, self._get_final_color)
            if self.frame_r.simple_vao is not None:
                self.frame_r.update_simple_colors(frames, self._get_final_color)

    def set_show(self, key: str, value: bool):
        if key in self.show:
            self.show[key] = bool(value)

    def get_show(self) -> dict:
        return dict(self.show)

    def set_use_lights(self, enabled: bool):
        self.use_lights = bool(enabled)

    def set_restraint_size(self, size: float) -> bool:
        if self.node_r:
            changed = self.node_r.builder.set_restraint_size(size)
            if changed and self.node_r.elements:
                self.node_r.update(list(self.node_r.elements))
            return changed
        return False