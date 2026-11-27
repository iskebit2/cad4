# render/presentation_renderer.py
from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from render.axes_renderer import LocalAxesRenderer
from render.global_axis_renderer import GlobalAxisRenderer
from render.grid_renderer import GridRenderer, BubbleRenderer
from render.label_batch import LabelBatch
from render.load_renderer import LoadRenderer
from tools.font_atlas import FontAtlas
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class PresentationRenderer:

    def __init__(self, standard_shader, axes_shader, overlay_shader,
                 simple_shader, grid_shader, math_model_renderer=None):
        self.math_model_renderer = math_model_renderer
        self.scene = None
        self.math_model = None
        self.standard_shader = standard_shader
        self.axes_shader = axes_shader
        self.overlay_shader = overlay_shader
        self.simple_shader = simple_shader
        self.engine = None
        self._projection = "3d"
        self._scene_polygons = []
        self._scene_lines = []

        self.global_axis = GlobalAxisRenderer(axes_shader)
        self.global_axis.init_gl()

        self.grid = GridRenderer(grid_shader)
        self.bubble = BubbleRenderer(grid_shader)

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

        self.show: dict[str, bool] = {}

    @property
    def polygon(self):
        return self.math_model_renderer.polygon_r if self.math_model_renderer else None

    @property
    def lines(self):
        return self.math_model_renderer.line_r if self.math_model_renderer else None

    @property
    def pick_pass(self):
        return self.math_model_renderer.pick_pass if self.math_model_renderer else None

    @property
    def load_renderer(self):
        return self.loads

    def set_engine(self, engine):
        self.engine = engine
        self.show = engine.show

    def set_loads_enabled(self, enabled):
        self.loads.enabled = bool(enabled)

    def set_load_scale(self, scale):
        self.loads.profile_scale = float(scale)

    def set_projection(self, projection):
        self._projection = projection

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

    def set_scene_data(self, scene, polygons=None, lines=None, grid_axes=None):
        self.scene = scene
        if self.math_model_renderer:
            self.math_model_renderer.set_lighting(scene.lighting)
        polygons = (
            list(self.math_model.polygons.values())
            if polygons is None and self.math_model else polygons or []
        )
        lines = (
            list(self.math_model.lines.values())
            if lines is None and self.math_model else lines or []
        )
        self._scene_polygons = list(polygons)
        self._scene_lines = list(lines)
        grid = getattr(scene, "grid", None)
        if self.grid.grid is not grid:
            self.grid.set_grid(grid)
        if grid_axes is not None:
            self.grid.set_axes(grid_axes)
        self.refresh_zones(polygons)

    def render_scene_visuals(
        self, camera, model, scene, math_model, width, height, show,
        active_wind_vector=None,
    ):
        self.show = show
        self._bind_grid(scene)
        mvp = camera.get_projection_matrix() * camera.get_view_matrix() * model
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if show.get("grid", False) and self.grid.grid:
            glDepthMask(GL_FALSE)
            self.grid.draw(mvp)
            glDepthMask(GL_TRUE)

        if show.get("wind_vector", False) and active_wind_vector is not None:
            self._draw_wind_vector(mvp, active_wind_vector, scene, math_model)

        if show.get("zones", False):
            self._draw_zones(mvp)

        if show.get("loads", False):
            glDisable(GL_DEPTH_TEST)
            self.loads.render(mvp)
            glEnable(GL_DEPTH_TEST)

        if show.get("local_axes", False):
            self._draw_local_axes(camera, scene, math_model)

        if show.get("global_axis", False):
            self._draw_global_axis(camera, width, height)

        if show.get("labels", False):
            self._draw_labels(camera, scene, math_model, height)

    def update_polygons(self, polygons):
        self._update_zones(polygons)

    def update_loads(self, math_model, camera_scale=1.0, scene_size=1.0, unit_system=None, wind_results=None):
        self.loads.update(math_model, camera_scale=camera_scale, scene_size=scene_size)

    def _bind_grid(self, scene):
        g = getattr(scene, "grid", None)
        if self.grid.grid is not g:
            self.grid.set_grid(g)

    def refresh_zones(self, polygons):
        self._update_zones(polygons)

    def _update_zones(self, polygons):
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
        span = max(abs(cpe_min), abs(cpe_max), 1e-6)
        cpe_lo, cpe_hi = -span, span

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
                for i in range(1, len(coords) - 1):
                    for c in (coords[0], coords[i], coords[i + 1]):
                        verts += [c[0], c[1], c[2], *color[:3]]
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

    def _zone_scalar(self, zone):
        cpez = zone.get("cpe10_override") or zone.get("cpe10", (0.0, 0.0))
        if isinstance(cpez, (list, tuple)):
            vals = [float(x) for x in cpez if x is not None]
            if not vals:
                return None
            return max(vals, key=abs)
        return float(cpez)

    def _zone_color(self, zone, cpe_lo, cpe_hi):
        v = self._zone_scalar(zone)
        if v is None:
            return (0.5, 0.5, 0.5)
        span = max(abs(cpe_lo), abs(cpe_hi), 1e-6)
        t = 0.5 + 0.5 * (v / span)
        t = max(0.0, min(1.0, t))
        if t < 0.25:
            k = t / 0.25
            return (0.10 + 0.20 * k, 0.40 + 0.50 * k, 0.95)
        if t < 0.5:
            k = (t - 0.25) / 0.25
            return (0.30 - 0.10 * k, 0.90, 0.95 - 0.55 * k)
        if t < 0.75:
            k = (t - 0.5) / 0.25
            return (0.20 + 0.75 * k, 0.90, 0.40 - 0.30 * k)
        k = (t - 0.75) / 0.25
        return (0.95, 0.90 - 0.75 * k, 0.10)

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

    def _upload_zone_outline(self, verts):
        if self.zone_outline_vao is None:
            self.zone_outline_vao = glGenVertexArrays(1)
            self.zone_outline_vbo = glGenBuffers(1)
        glBindVertexArray(self.zone_outline_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.zone_outline_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.zone_outline_vcount = len(verts) // 3

    def _cleanup_zone_verts(self):
        if self.zone_vbo:
            glDeleteBuffers(1, [self.zone_vbo])
            self.zone_vbo = None
        if self.zone_vao:
            glDeleteVertexArrays(1, [self.zone_vao])
            self.zone_vao = None
        self.zone_vcount = 0

    def _cleanup_zone_outline(self):
        if self.zone_outline_vbo:
            glDeleteBuffers(1, [self.zone_outline_vbo])
            self.zone_outline_vbo = None
        if self.zone_outline_vao:
            glDeleteVertexArrays(1, [self.zone_outline_vao])
            self.zone_outline_vao = None
        self.zone_outline_vcount = 0

    def _draw_zones(self, mvp):
        if not (self.show.get("zones", False) and self.zone_vao and self.zone_vcount):
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

        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-2.0, -2.0)
        glBindVertexArray(self.zone_vao)
        glDrawArrays(GL_TRIANGLES, 0, self.zone_vcount)
        glBindVertexArray(0)
        glDisable(GL_POLYGON_OFFSET_FILL)

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

    def _draw_global_axis(self, cam, w, h):
        self.global_axis.begin_frame(cam, w, h, projection=self._projection)
        self.global_axis.render()

    def _draw_local_axes(self, cam, scene, math_model):
        if math_model is None:
            return

        base = cam.get_projection_matrix() * cam.get_view_matrix()
        cam_scale = self._compute_cam_scale()
        user_scale = float(getattr(scene, "show_local_axes_scale", 1.0))
        scale = max(cam_scale * 0.03 * user_scale, 1e-3)
        only_sel = bool(getattr(scene, "show_local_axes_for_selected", False))

        self.axes_shader.use()
        loc = self.axes_shader.get_loc("u_mvp")

        glDisable(GL_DEPTH_TEST)
        glBindVertexArray(self.axes.vao)

        def _emit(rot: glm.mat3, origin) -> None:
            M = glm.mat4(rot)
            M[3] = glm.vec4(float(origin[0]), float(origin[1]), float(origin[2]), 1.0)
            mvp = base * glm.scale(M, glm.vec3(scale))
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            glDrawArrays(GL_LINES, 0, 6)
            glDrawArrays(GL_TRIANGLES, 6, 9)

        for f in math_model.frames.values():
            if not f.is_visible or f.show_axes_override is False:
                continue
            if only_sel and not f.is_selected:
                continue
            _emit(f.get_local_axes(), f.get_midpoint())

        for a in math_model.areas.values():
            if not a.is_visible or a.show_axes_override is False:
                continue
            if only_sel and not a.is_selected:
                continue
            if len(a.nodes) < 3:
                continue
            center, u, v, n = a.get_plane_frame()
            _emit(glm.mat3(u, v, n), center)

        for p in math_model.polygons.values():
            if not p.is_visible or p.show_axes_override is False:
                continue
            if only_sel and not p.is_selected:
                continue
            if not p.is_valid():
                continue
            center, u, v, n = p.get_plane_frame()
            _emit(glm.mat3(u, v, n), center)

        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def _draw_labels(self, cam, scene, math_model, screen_h):
        if self.show.get("grid_labels", False):
            self._grid_labels(cam)
        if self.show.get("selected_labels", False):
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
            safe_text = self._ascii_safe(a["text"])
            encoded = safe_text.encode("latin-1", "replace")
            advances = self.labels.lut["advance"][np.frombuffer(encoded, dtype=np.uint8)]
            size_world = a["text_world_width"] * self.font.size / float(advances.sum())
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
            texts[i] = self._ascii_safe(f"F{f.unique_id}")

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

    def _draw_wind_vector(self, mvp, vec, scene, math_model=None):
        if not vec:
            return
        sh = self.simple_shader or self.standard_shader
        if not sh:
            return

        bounds = [
            item for item in (
                scene.bounds if scene else None,
                math_model.bounds if math_model else None,
            ) if item is not None
        ]
        if not bounds:
            return

        minimum = np.min([item.min for item in bounds], axis=0).astype(np.float32)
        maximum = np.max([item.max for item in bounds], axis=0).astype(np.float32)
        size_xyz = maximum - minimum
        diag = float(np.linalg.norm(size_xyz))

        if diag < 1e-6:
            return

        arrow_len = diag * 0.35

        start = np.array([
            (minimum[0] + maximum[0]) * 0.5,
            (minimum[1] + maximum[1]) * 0.5,
            maximum[2],
        ], dtype=np.float32)

        v_dir = np.array(vec, dtype=np.float32)
        norm = float(np.linalg.norm(v_dir))
        if norm < 1e-6:
            return
        v_dir /= norm

        end = start + v_dir * arrow_len
        head_len = arrow_len * 0.18
        head_width = arrow_len * 0.06
        head_base = end - v_dir * head_len

        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(float(np.dot(v_dir, up))) > 0.99:
            up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        right = np.cross(v_dir, up)
        right /= np.linalg.norm(right)
        up_dir = np.cross(right, v_dir)
        up_dir /= np.linalg.norm(up_dir)

        lines = np.array([
            start[0], start[1], start[2], end[0], end[1], end[2],
            end[0], end[1], end[2],
            head_base[0] + right[0] * head_width,
            head_base[1] + right[1] * head_width,
            head_base[2] + right[2] * head_width,
            end[0], end[1], end[2],
            head_base[0] - right[0] * head_width,
            head_base[1] - right[1] * head_width,
            head_base[2] - right[2] * head_width,
            end[0], end[1], end[2],
            head_base[0] + up_dir[0] * head_width,
            head_base[1] + up_dir[1] * head_width,
            head_base[2] + up_dir[2] * head_width,
            end[0], end[1], end[2],
            head_base[0] - up_dir[0] * head_width,
            head_base[1] - up_dir[1] * head_width,
            head_base[2] - up_dir[2] * head_width,
        ], dtype=np.float32)

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
        glLineWidth(3.0)

        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, lines.nbytes, lines, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))
        glDisable(GL_DEPTH_TEST)
        glDrawArrays(GL_LINES, 0, len(lines) // 3)
        glEnable(GL_DEPTH_TEST)
        glBindVertexArray(0)
        glDeleteBuffers(1, [vbo])
        glDeleteVertexArrays(1, [vao])
        glLineWidth(1.0)

    @staticmethod
    def _ascii_safe(text: str) -> str:
        return (
            text.replace("²", "^2")
                .replace("³", "^3")
                .replace("·", "*")
                .replace("×", "x")
                .replace("→", "->")
                .replace("←", "<-")
                .replace("±", "+/-")
                .replace("°", "deg")
                .replace("Δ", "Delta")
                .replace("µ", "u")
                .replace("–", "-")
                .replace("—", "-")
        )

    def cleanup(self):
        self._cleanup_zone_verts()
        self._cleanup_zone_outline()
        for r in (self.loads, self.axes, self.bubble, self.labels):
            if hasattr(r, "cleanup"):
                r.cleanup()