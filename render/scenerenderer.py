# render/presentationrenderer.py

from __future__ import annotations
import time

import math

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from render.axes_renderer import LocalAxesRenderer
from render.global_axis_renderer import GlobalAxisRenderer
from render.grid_renderer import GridRenderer, BubbleRenderer
from render.label_batch import LabelBatch
from render.line_renderer import LineRenderer
from render.load_renderer import LoadRenderer
from render.polygonrenderer import PolygonRenderer
from tools.font_atlas import FontAtlas

from logging_config import CadLogger
logger = CadLogger.get(__name__)

class SceneRenderer:

    def __init__(self, standard_shader, axes_shader, overlay_shader,
                 simple_shader, grid_shader, math_model_renderer=None):
        self.math_model_renderer = math_model_renderer
        self.scene = None
        self.math_model = None
        self.standard_shader = standard_shader
        self.axes_shader = axes_shader
        self.overlay_shader = overlay_shader
        self.simple_shader = simple_shader
        self._projection = "3d"
        self._scene_polygons = []
        self._scene_lines = []

        self.global_axis = GlobalAxisRenderer(axes_shader)
        self.global_axis.init_gl()

        self.grid = GridRenderer(grid_shader)
        self.bubble = BubbleRenderer(grid_shader)

        self.polygon = PolygonRenderer(simple_shader or standard_shader)
        self.lines = LineRenderer(simple_shader or standard_shader)
        self.loads = LoadRenderer()
        self.axes = LocalAxesRenderer(axes_shader)
        self.axes.init_gl()

        self.font = FontAtlas(None, size=32, supersample=2)
        self.labels = LabelBatch(self.font)
        self.labels.init_gl()

        self.zone_vao = None
        self.zone_vbo = None
        self.zone_vcount = 0
        self.zone_outline_vao = None
        self.zone_outline_vbo = None
        self.zone_outline_vcount = 0
        
        self.show = {
            "polygon": True,
            "lines": True,
            "zones": False,
            "loads": False,
            "local_axes": False,
            "grid_labels": True,
            "selected_labels": True,
        }

    def __getattr__(self, name):
        model_renderer = self.__dict__.get("math_model_renderer")
        if model_renderer is not None:
            return getattr(model_renderer, name)
        raise AttributeError(name)

    @property
    def pick_pass(self):
        return self.math_model_renderer.pick_pass if self.math_model_renderer else None

    @property
    def load_renderer(self):
        return self.loads

    def set_math_model_renderer(self, renderer):
        self.math_model_renderer = renderer

    def set_cam(self, camera):
        if self.math_model_renderer:
            self.math_model_renderer.set_cam(camera)

    def set_engine(self, engine):
        self.engine = engine
        if self.math_model_renderer:
            self.math_model_renderer.set_engine(engine)

    def set_loads_enabled(self, enabled):
        self.loads.enabled = bool(enabled)

    def set_load_scale(self, scale):
        self.loads.profile_scale = float(scale)

    def _compute_cam_scale(self):
        bounds = [
            item for item in (
                self.scene.bounds if self.scene else None,
                self.math_model.bounds if self.math_model else None,
            ) if item is not None
        ]
        if not bounds:
            return 1.0
        minimum = np.min([item.min for item in bounds], axis=0)
        maximum = np.max([item.max for item in bounds], axis=0)
        return float(np.linalg.norm(maximum - minimum)) or 1.0

    def set_snap(self, snap):
        if self.math_model_renderer:
            self.math_model_renderer.set_snap(snap)

    def resize(self, width, height):
        if self.math_model_renderer:
            self.math_model_renderer.resize(width, height)

    def update_geo(
        self, math_model, scene=None, progress_cb=None, polygons=None, lines=None,
        grid_axes=None, frames=None, nodes=None, areas=None, links=None,
    ):
        self.math_model = math_model
        if self.math_model_renderer:
            self.math_model_renderer.update_geo(
                math_model,
                progress_cb,
                frames=frames,
                nodes=nodes,
                areas=areas,
                links=links,
            )
        if scene is not None:
            self.set_scene_data(
                scene, polygons=polygons, lines=lines, grid_axes=grid_axes,
            )

    def set_scene_data(self, scene, polygons=None, lines=None, grid_axes=None):
        t_start = time.perf_counter()
        self.scene = scene
        if self.math_model_renderer:
            self.math_model_renderer.set_lighting(scene.lighting)
        polygons = list(scene.polygons.values()) if polygons is None else polygons
        lines = list(scene.lines.values()) if lines is None else lines
        self._scene_polygons = list(polygons)
        self._scene_lines = list(lines)
        grid = getattr(scene, "grid", None)
        if self.grid.grid is not grid:
            self.grid.set_grid(grid)
        if grid_axes is not None:
            self.grid.set_axes(grid_axes)

        t = time.perf_counter()
        self.update_polygons(polygons)
        logger.debug("[SceneRender.set_scene_data] update_polygons: %.1f ms", (time.perf_counter() - t) * 1000)

        t = time.perf_counter()
        self.update_lines(lines)
        logger.debug("[SceneRender.set_scene_data] update_lines: %.1f ms", (time.perf_counter() - t) * 1000)
        logger.debug("[SceneRender.set_scene_data] TOTAL: %.1f ms", (time.perf_counter() - t_start) * 1000)

        if self.pick_pass:
            for polygon in polygons:
                polygon.pick_id = polygon.unique_id
                source = getattr(polygon, "_geometry_source", polygon)
                self.pick_pass.register(polygon.pick_id, source, self.polygon)
            for line in lines:
                line.pick_id = line.unique_id
                source = getattr(line, "_geometry_source", line)
                self.pick_pass.register(line.pick_id, source, self.lines)

    def render_math_model(self, camera, target_fbo=0):
        if self.math_model_renderer:
            self.math_model_renderer.render(camera, target_fbo)

    def render_scene_visuals(
        self, camera, model, scene, math_model, width, height, show,
        active_wind_vector=None,
    ):
        t_start = time.perf_counter()
        self._bind_grid(scene)
        mvp = camera.get_projection_matrix() * camera.get_view_matrix() * model
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if show.get("grid", True) and self.grid.grid:
            t = time.perf_counter()
            glDepthMask(GL_FALSE)
            self.grid.draw(mvp)
            glDepthMask(GL_TRUE)
            logger.debug("[SceneRender] grid: %.2f ms", (time.perf_counter() - t) * 1000)
        if show.get("polygon", True):
            t = time.perf_counter()
            glDepthMask(GL_FALSE)
            self.polygon.render_simple(
                mvp, self.simple_shader or self.standard_shader, alpha=0.5,
            )
            self.polygon.render_lines_white(
                mvp, self.simple_shader or self.standard_shader,
            )
            glDepthMask(GL_TRUE)
            logger.debug("[SceneRender] polygon: %.2f ms", (time.perf_counter() - t) * 1000)
        if show.get("lines", True):
            t = time.perf_counter()
            self.lines.draw(mvp)
            logger.debug("[SceneRender] lines: %.2f ms", (time.perf_counter() - t) * 1000)
        if show.get("zones", True):
            t = time.perf_counter()
            self._draw_zones(mvp)
            logger.debug("[SceneRender] zones: %.2f ms", (time.perf_counter() - t) * 1000)
        if show.get("loads", True) and self.loads.enabled:
            t = time.perf_counter()
            glDisable(GL_DEPTH_TEST)
            self.loads.render(mvp)
            glEnable(GL_DEPTH_TEST)
        if show.get("local_axes", False):
            t = time.perf_counter()
            self._draw_local_axes(camera, scene, math_model)
        if show.get("global_axis", True):
            t = time.perf_counter()
            self._draw_global_axis(camera, width, height)
        if show.get("labels", True):
            t = time.perf_counter()
            self._draw_labels(camera, scene, math_model, height)
            logger.debug("[SceneRender] labels: %.2f ms", (time.perf_counter() - t) * 1000)
        if active_wind_vector is not None:
            self._draw_wind_vector(mvp, active_wind_vector, scene)

        if time.perf_counter() - t_start > 0.016:
            logger.debug("[SceneRender] SLOW TOTAL: %.1f ms", (time.perf_counter() - t_start) * 1000)

    def render(self, camera, target_fbo=0):
        self.render_math_model(camera, target_fbo)

    def update_sel(self):
        if self.math_model_renderer:
            self.math_model_renderer.update_sel()
        for element in (*self._scene_polygons, *self._scene_lines):
            source = getattr(element, "_geometry_source", element)
            if source is not element:
                element.is_selected = getattr(source, "is_selected", False)
        if self.scene:
            self.update_polygons(self._scene_polygons)
            self.update_lines(self._scene_lines)

    def update_dirty(self):
        if self.math_model_renderer:
            self.math_model_renderer.update_dirty()

    def render_presentation_pick(self, cam, model, pick_shader):
        mvp = cam.get_projection_matrix() * cam.get_view_matrix() * model
        if self.show.get("polygon", True) and self.polygon:
            self.polygon.render_pick(mvp, pick_shader)
        if self.show.get("lines", True) and hasattr(self.lines, "render_pick"):
            self.lines.render_pick(mvp, pick_shader)

    # ------------------------------------------------------------------
    def update_polygons(self, polygons):
        self.polygon.update(polygons)
        parts = []
        for pg in polygons:
            if getattr(pg, "is_visible", True):
                v = self.polygon.builder.build_lines(pg)
                if len(v):
                    parts.append(v)
        if parts:
            self.polygon._upload_outline(np.concatenate(parts).astype(np.float32))
        else:
            self.polygon._cleanup_outline()
        self._update_zones(polygons)

    def _update_zones(self, polygons):
        t_start = time.perf_counter()
        # 1. GEÇİŞ: tüm zone cpe değerlerini topla (global min/max için)
        all_cpe = []
        for pg in polygons:
            if not getattr(pg, "is_visible", True):
                continue
            zone_dict = getattr(pg, "zone_children_by_direction", None) or {}
            direction = getattr(pg, "show_zones_direction", None)
            if direction is None or direction not in zone_dict:
                continue
            for zone in zone_dict.get(direction, []):
                v = self._zone_scalar(zone)
                if v is not None:
                    all_cpe.append(v)

        if not all_cpe:
            self._cleanup_zone_verts()
            self._cleanup_zone_outline()
            return

        cpe_min = min(all_cpe)
        cpe_max = max(all_cpe)
        # Simetrik aralık: emme ve basınç aynı ölçekte görünsün
        span = max(abs(cpe_min), abs(cpe_max), 1e-6)
        cpe_lo, cpe_hi = -span, span

        # 2. GEÇİŞ: üçgen + outline üret
        verts = []
        outline = []
        for pg in polygons:
            if not getattr(pg, "is_visible", True):
                continue
            zone_dict = getattr(pg, "zone_children_by_direction", None) or {}
            direction = getattr(pg, "show_zones_direction", None)
            if direction is None or direction not in zone_dict:
                continue
            for zone in zone_dict.get(direction, []):
                coords = zone.get("coords") or []
                if len(coords) < 3:
                    continue
                color = self._zone_color(zone, cpe_lo, cpe_hi)

                # Üçgen fan (mevcut mantık)
                for i in range(1, len(coords) - 1):
                    for c in (coords[0], coords[i], coords[i + 1]):
                        verts += [c[0], c[1], c[2], *color[:3]]

                # Outline: kenar çiftleri
                n = len(coords)
                for i in range(n):
                    a = coords[i]
                    b = coords[(i + 1) % n]
                    outline += [a[0], a[1], a[2], b[0], b[1], b[2]]

        if verts:
            self._upload_zone_verts(np.array(verts, np.float32))
        else:
            self._cleanup_zone_verts()

        if outline:
            self._upload_zone_outline(np.array(outline, np.float32))
        else:
            self._cleanup_zone_outline()

        logger.debug("[SceneRender._update_zones] TOTAL: %.1f ms (%d verts)", (time.perf_counter() - t_start) * 1000, len(verts) // 6 if verts else 0)

    def _zone_scalar(self, zone):
        """Zone'un temsili Cpe değeri (override öncelikli)."""
        cpez = zone.get("cpe10_override") or zone.get("cpe10", (0.0, 0.0))
        if isinstance(cpez, (list, tuple)):
            vals = [float(x) for x in cpez if x is not None]
            if not vals:
                return None
            # Basınç/emme ayrımı için mutlak değerce büyük olanı seç
            return max(vals, key=abs)
        try:
            return float(cpez)
        except (TypeError, ValueError):
            return None

    def _zone_color(self, zone, cpe_lo, cpe_hi):
        v = self._zone_scalar(zone)
        if v is None:
            return (0.5, 0.5, 0.5)

        # -span..+span → 0..1 normalize
        span = max(abs(cpe_lo), abs(cpe_hi), 1e-6)
        t = 0.5 + 0.5 * (v / span)          # 0 = en negatif (emme), 1 = en pozitif (basınç)
        t = max(0.0, min(1.0, t))

        # Soğuk→sıcak sürekli skala (blue → cyan → yeşil → sarı → kırmızı)
        if t < 0.25:
            # derin mavi → cyan
            k = t / 0.25
            return (0.10 + 0.20 * k, 0.40 + 0.50 * k, 0.95)
        elif t < 0.5:
            # cyan → yeşil
            k = (t - 0.25) / 0.25
            return (0.30 - 0.10 * k, 0.90, 0.95 - 0.55 * k)
        elif t < 0.75:
            # yeşil → sarı
            k = (t - 0.5) / 0.25
            return (0.20 + 0.75 * k, 0.90, 0.40 - 0.30 * k)
        else:
            # sarı → kırmızı
            k = (t - 0.75) / 0.25
            return (0.95, 0.90 - 0.75 * k, 0.10)

    def _upload_zone_outline(self, verts):
        if self.zone_outline_vao is None:
            self.zone_outline_vao = glGenVertexArrays(1)
            self.zone_outline_vbo = glGenBuffers(1)
        glBindVertexArray(self.zone_outline_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.zone_outline_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        stride = 6 * 4  # 3 pos + 3 renk (renk yoksa 3*4 kullan)
        # Outline için sadece pozisyon yeterli; renk istemiyorsan stride 3*4 yap
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.zone_outline_vcount = len(verts) // 3

    def _cleanup_zone_outline(self):
        if self.zone_outline_vbo:
            glDeleteBuffers(1, [self.zone_outline_vbo])
            self.zone_outline_vbo = None
        if self.zone_outline_vao:
            glDeleteVertexArrays(1, [self.zone_outline_vao])
            self.zone_outline_vao = None
        self.zone_outline_vcount = 0
        
    def refresh_zones(self, polygons):
        self._update_zones(polygons)

    def update_loads(self, math_model, camera_scale=1.0, scene_size=1.0):
        if self.loads.enabled:
            self.loads.update(math_model, camera_scale=camera_scale, scene_size=scene_size)

    def set_projection(self, projection):
        self._projection = projection

    def render_presentation_pick(self, cam, model, pick_shader):
        mvp = cam.get_projection_matrix() * cam.get_view_matrix() * model
        if self.show.get("polygon", True) and self.polygon:
            self.polygon.render_pick(mvp, pick_shader)
        if self.show.get("lines", True) and hasattr(self.lines, "render_pick"):
            self.lines.render_pick(mvp, pick_shader)

    def _bind_grid(self, scene):
        g = getattr(scene, "grid", None)
        if self.grid.grid is not g:
            self.grid.set_grid(g)

    # ------------------------------------------------------------------
    def _draw_lines(self, mvp):
        if not self.show.get("lines", True):
            return
        self.lines.draw(mvp)
        
    def _draw_polygons(self, mvp):
        if not self.show["polygon"]:
            return
        sh = self.simple_shader or self.standard_shader
        glDepthMask(GL_FALSE)
        self.polygon.render_simple(mvp, sh, alpha=0.50)
        self.polygon.render_lines_white(mvp, sh)
        glDepthMask(GL_TRUE)

    def _draw_loads(self, mvp):
        if not (self.show["loads"] and self.loads.enabled):
            return
        glDisable(GL_DEPTH_TEST)
        self.loads.render(mvp)
        glEnable(GL_DEPTH_TEST)

    def _draw_global_axis(self, cam, w, h):
        self.global_axis.begin_frame(cam, w, h, projection=self._projection)
        self.global_axis.render()

    def _draw_local_axes(self, cam, scene, math_model):
        if not getattr(scene, "show_local_axes", False) or math_model is None:
            return
        base = cam.get_projection_matrix() * cam.get_view_matrix()
        scale = 0.025 * getattr(scene, "show_local_axes_scale", 1.0)
        only_sel = getattr(scene, "show_local_axes_for_selected", True)

        glDisable(GL_DEPTH_TEST)
        self.axes_shader.use()
        loc = self.axes_shader.get_loc("u_mvp")

        for f in math_model.frames.values():
            if not f.is_visible or (only_sel and not f.is_selected):
                continue
            if f.show_axes_override is False:
                continue
            R = f.get_local_axes()
            R3 = np.array([[R[0][0], R[1][0], R[2][0]],
                           [R[0][1], R[1][1], R[2][1]],
                           [R[0][2], R[1][2], R[2][2]]], dtype=np.float32)
            M = (glm.translate(glm.mat4(1.0), glm.vec3(*f.get_midpoint()))
                 * glm.mat4(glm.mat3(*[glm.vec3(*R3[:, i]) for i in range(3)])))
            mvp = base * glm.scale(M, glm.vec3(scale))
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            glBindVertexArray(self.axes.vao)
            glDrawArrays(GL_LINES, 0, 6)
            glDrawArrays(GL_TRIANGLES, 6, 12)

        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    # ------------------------------------------------------------------
    def _draw_labels(self, cam, scene, math_model, screen_h):
        if self.show["grid_labels"]:
            self._grid_labels(cam)
        if self.show["selected_labels"]:
            self._frame_labels(cam, math_model, screen_h)

    def _grid_labels(self, cam):
        dg = self.grid.grid
        if not dg or not dg.show_labels:
            return
        anchors = [a for a in self.grid.get_label_anchors() if a["text"]]
        if not anchors:
            return

        mvp = cam.get_projection_matrix() * cam.get_view_matrix()
        overflow = dg.label_overflow

        self.bubble.begin()
        info = []
        for a in anchors:
            info.append(self.bubble.add(
                anchor=a["anchor"],
                direction=a["direction_world"],
                normal=a["plane_normal"],
                text_width=a["text_world_width"],
                color=(*a["color"][:3], 1.0),
                leader_len=overflow,
            ))
        self.bubble.flush(mvp)

        self.labels.begin(mode="world", mvp=mvp)
        for a, i in zip(anchors, info):
            encoded = a["text"].encode("latin-1", "replace")
            advances = self.labels.lut["advance"][np.frombuffer(encoded, dtype=np.uint8)]
            size_world = (
                a["text_world_width"] * self.font.size / float(advances.sum())
            )
            self.labels.add(
                world_pos=i["center"],
                text=a["text"],
                color=(*a["color"][:3], 1.0),
                size_world=size_world,
                anchor="center",
                u_axis=i["u_axis"],
                v_axis=i["v_axis"],
            )
        self.labels.flush(disable_depth=True)

    def _frame_labels(self, cam, math_model, screen_h):
        frames = [f for f in math_model.frames.values() if f.is_selected]
        if not frames:
            return
        n = len(frames)
        pos = np.empty((n, 3), dtype=np.float32)
        off = np.tile(np.array([20.0, 20.0, 20.0], dtype=np.float32), (n, 1))
        texts = [""] * n
        for i, f in enumerate(frames):
            pos[i] = ((f.node_i.x + f.node_j.x) * 0.5,
                      (f.node_i.y + f.node_j.y) * 0.5,
                      (f.node_i.z + f.node_j.z) * 0.5)
            texts[i] = f"F{f.unique_id}"

        self.labels.begin(
            view=cam.get_view_matrix(),
            proj=cam.get_projection_matrix(),
            cam_pos=(cam.position.x, cam.position.y, cam.position.z),
            screen_h=screen_h,
            fov_y_rad=math.radians(getattr(cam, "fov", 45.0)),
            mode="billboard",
        )
        self.labels.add_many(
            positions=pos, texts=texts,
            colors=np.array([1.0, 1.0, 0.3, 1.0], dtype=np.float32),
            pixel_sizes=13.0, anchors="bottom-center", world_offsets=off,
        )
        self.labels.flush()

    def _upload_zone_verts(self, verts):
        if self.zone_vao is None:
            self.zone_vao = glGenVertexArrays(1)
            self.zone_vbo = glGenBuffers(1)
        glBindVertexArray(self.zone_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.zone_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        stride = 6 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.zone_vcount = len(verts) // 6

    def _cleanup_zone_verts(self):
        if self.zone_vbo:
            glDeleteBuffers(1, [self.zone_vbo])
            self.zone_vbo = None
        if self.zone_vao:
            glDeleteVertexArrays(1, [self.zone_vao])
            self.zone_vao = None
        self.zone_vcount = 0

    def _draw_zones(self, mvp):
        if not (self.show.get("zones") and self.zone_vao and self.zone_vcount):
            return
        sh = self.simple_shader or self.standard_shader
        if not sh:
            return
        sh.use()
        for name in ("u_mvp", "mvp", "MVP"):
            loc = sh.get_loc(name)
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
                break
        vc = sh.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 1)
        a = sh.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 0.95)

        # --- DOLGU ---
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-2.0, -2.0)
        glBindVertexArray(self.zone_vao)
        glDrawArrays(GL_TRIANGLES, 0, self.zone_vcount)
        glBindVertexArray(0)
        glDisable(GL_POLYGON_OFFSET_FILL)

        # --- OUTLINE ---
        if self.zone_outline_vao and self.zone_outline_vcount:
            for name in ("u_mvp", "mvp", "MVP"):
                loc = sh.get_loc(name)
                if loc != -1:
                    glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
                    break
            vc = sh.get_loc("useVertexColor")
            if vc != -1:
                glUniform1i(vc, 0)
            oc = sh.get_loc("objectColor")
            if oc != -1:
                glUniform3f(oc, 0.05, 0.05, 0.05)
            a = sh.get_loc("alpha")
            if a != -1:
                glUniform1f(a, 1.0)

            glEnable(GL_POLYGON_OFFSET_LINE)
            glPolygonOffset(-1.0, -1.0)
            glLineWidth(1.0)
            glBindVertexArray(self.zone_outline_vao)
            glDrawArrays(GL_LINES, 0, self.zone_outline_vcount)
            glBindVertexArray(0)
            glDisable(GL_POLYGON_OFFSET_LINE)

    def update_lines(self, lines):
        self.lines.update(lines)

    def _draw_wind_vector(self, mvp, vec, scene):
        if not vec:
            return
        sh = self.simple_shader or self.standard_shader
        if not sh:
            return

        center = np.zeros(3, dtype=np.float32)
        size = 1000.0  # Doğru ölçek (1000.0 yerine makul bir boyut)
        if scene:
            b = scene.bounds
            if b:
                center = b.center
                size = max(5.0, b.size * 0.4)

        v_dir = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(v_dir)
        if norm < 1e-6:
            return
        v_dir /= norm

        start = center - v_dir * (size * 1.5)
        end = center + v_dir * (0.5)

        sh.use()
        loc = sh.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        vc = sh.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 0)
        oc = sh.get_loc("objectColor")
        if oc != -1:
            glUniform3f(oc, 1.0, 0.3, 0.2)
        a = sh.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 1.0)

        glLineWidth(5.0)

        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(np.dot(v_dir, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        right = np.cross(v_dir, up)
        right /= np.linalg.norm(right)
        up_dir = np.cross(right, v_dir)
        up_dir /= np.linalg.norm(up_dir)

        arrow_head_len = size * 0.25
        arrow_head_width = size * 0.1
        head_base = end - v_dir * arrow_head_len

        lines = [
            start[0], start[1], start[2],
            end[0], end[1], end[2],
            end[0], end[1], end[2],
            head_base[0] + right[0] * arrow_head_width, head_base[1] + right[1] * arrow_head_width, head_base[2] + right[2] * arrow_head_width,
            end[0], end[1], end[2],
            head_base[0] - right[0] * arrow_head_width, head_base[1] - right[1] * arrow_head_width, head_base[2] - right[2] * arrow_head_width,
            end[0], end[1], end[2],
            head_base[0] + up_dir[0] * arrow_head_width, head_base[1] + up_dir[1] * arrow_head_width, head_base[2] + up_dir[2] * arrow_head_width,
            end[0], end[1], end[2],
            head_base[0] - up_dir[0] * arrow_head_width, head_base[1] - up_dir[1] * arrow_head_width, head_base[2] - up_dir[2] * arrow_head_width,
        ]

        verts = np.array(lines, dtype=np.float32)

        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))

        glDisable(GL_DEPTH_TEST)
        glDrawArrays(GL_LINES, 0, len(verts) // 3)
        glEnable(GL_DEPTH_TEST)

        glBindVertexArray(0)
        glDeleteBuffers(1, [vbo])
        glDeleteVertexArrays(1, [vao])
        glLineWidth(1.0)

    # ------------------------------------------------------------------
    def cleanup(self):
        self._cleanup_zone_verts()
        self._cleanup_zone_outline()
        if self.math_model_renderer:
            self.math_model_renderer.cleanup()
        for r in (
            self.polygon, self.lines, self.loads, self.axes, self.bubble,
            self.labels,
        ):
            if hasattr(r, "cleanup"):
                r.cleanup()