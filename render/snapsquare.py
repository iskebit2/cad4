from __future__ import annotations

import numpy as np
from pyglm import glm

from domain.vertex import Vertex


class SnapSquareRenderer:

    SNAP_RADIUS_PX = 6.5

    def find_snap(self, engine, x, y, magnetic=False, cam=None, viewport_size=None,
                  plane=None, visible_ids=None):
        if magnetic:
            finders = (
                (self._find_node, "node"),
                (self._find_grid_snap, "grid"),
            )
        else:
            finders = (
                (self._find_node, "node"),
                (self._find_grid_snap, "grid"),
                (self._find_frame, "frame"),
                (self._find_link, "link"),
                (self._find_line, "line"),
                (self._find_area, "area"),
                (self._find_polygon, "polygon"),
            )

        for finder, kind in finders:
            result, resolved_kind = finder(
                engine, x, y,
                cam=cam,
                viewport_size=viewport_size,
                plane=plane,
                visible_ids=visible_ids,
                default_kind=kind,
            )
            if result is not None:
                is_snap = resolved_kind in ("node", "grid", "midpoint")
                return result, is_snap, resolved_kind
        return None, False, "default"

    @staticmethod
    def _is_visible_in_viewport(el, visible_ids) -> bool:
        if not getattr(el, "is_visible", True):
            return False
        if visible_ids is not None and getattr(el, "unique_id", None) not in visible_ids:
            return False
        return True

    @staticmethod
    def _project_pt_with_size(mvp, x, y, z, w, h):
        v4 = mvp * glm.vec4(x, y, z, 1.0)
        if abs(v4.w) < 1e-12:
            return None
        ndc_x = v4.x / v4.w
        ndc_y = v4.y / v4.w
        ndc_z = v4.z / v4.w
        if ndc_z < -1.0 or ndc_z > 1.0:
            return None
        return (ndc_x + 1.0) * 0.5 * w, (1.0 - ndc_y) * 0.5 * h

    @staticmethod
    def _dist_to_segment(p, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom < 1e-12:
            return (px - ax) ** 2 + (py - ay) ** 2, 0.0
        t = ((px - ax) * dx + (py - ay) * dy) / denom
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return (px - cx) ** 2 + (py - cy) ** 2, t

    def _find_node(self, engine, x, y, cam=None, viewport_size=None,
                   plane=None, visible_ids=None, default_kind="node"):
        scene = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not scene or not target_cam:
            return None, default_kind

        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        mvp = target_cam.get_projection_matrix() @ target_cam.get_view_matrix()

        best_node, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for node in scene.nodes.values():
            if not self._is_visible_in_viewport(node, visible_ids):
                continue
            p = self._project_pt_with_size(mvp, node.x, node.y, node.z, w, h)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_node = node
        if best_node is None:
            return None, default_kind
        return self._vertex_from_node(best_node), default_kind

    def _find_grid_snap(self, engine, x, y, cam=None, viewport_size=None,
                        plane=None, visible_ids=None, default_kind="grid"):
        target_cam = cam if cam is not None else engine.cam
        if target_cam is None:
            return None, default_kind

        project = getattr(engine, "project", None)
        grid = getattr(project, "grid", None) if project else None
        if grid is None:
            return None, default_kind

        candidates = self._grid_candidates_for_plane(grid, plane)
        if not candidates:
            return None, default_kind

        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        mvp = target_cam.get_projection_matrix() @ target_cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for c in candidates:
            cx, cy, cz = (c.x, c.y, c.z) if hasattr(c, "x") else (float(c[0]), float(c[1]), float(c[2]))
            p = self._project_pt_with_size(mvp, cx, cy, cz, w, h)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = (cx, cy, cz)
        if best is None:
            return None, default_kind
        return Vertex(best[0], best[1], best[2]), default_kind

    @staticmethod
    def _grid_candidates_for_plane(grid, plane) -> list:
        if plane is None:
            return grid.snap_points() or []

        n = np.asarray(plane.normal, dtype=float)
        abs_n = np.abs(n)
        max_ax = int(np.argmax(abs_n))
        if abs_n[max_ax] > 0.999:
            axis_name = ("x", "y", "z")[max_ax]
            level = float(np.dot(n, plane.origin))
            pts = grid.snap_points_on_plane(axis_name, level) or []
            if pts:
                return [p for p in pts if plane.bounds_contains_uv(*plane.to_2d(p))]

        xs = sorted(set(getattr(grid, "x_coords", []) or []))
        ys = sorted(set(getattr(grid, "y_coords", []) or []))
        zs = sorted(set(getattr(grid, "z_coords", []) or [0.0]))
        if not xs or not ys:
            return []

        depth_tol = max(plane.depth_minus, plane.depth_plus, 1e-3)
        projected = []
        seen = set()
        for gx in xs:
            for gy in ys:
                for gz in zs:
                    pt = (gx, gy, gz)
                    if abs(plane.distance(pt)) > depth_tol:
                        continue
                    p_on = plane.project(pt)
                    u, v = plane.to_2d(p_on)
                    if not plane.bounds_contains_uv(u, v):
                        continue
                    key = (round(float(p_on[0]), 4), round(float(p_on[1]), 4), round(float(p_on[2]), 4))
                    if key not in seen:
                        seen.add(key)
                        projected.append((float(p_on[0]), float(p_on[1]), float(p_on[2])))
        return projected

    def _find_segment_collection(self, items, get_endpoints, x, y, target_cam, w, h,
                                 visible_ids, default_kind):
        mvp = target_cam.get_projection_matrix() @ target_cam.get_view_matrix()
        best, best_d2, best_kind = None, self.SNAP_RADIUS_PX ** 2, default_kind
        for item in items:
            if not self._is_visible_in_viewport(item, visible_ids):
                continue
            a, b = get_endpoints(item)
            if a is None or b is None:
                continue
            p0 = self._project_pt_with_size(mvp, a.x, a.y, a.z, w, h)
            p1 = self._project_pt_with_size(mvp, b.x, b.y, b.z, w, h)
            if p0 is None or p1 is None:
                continue
            d2, t = self._dist_to_segment((x, y), p0, p1)
            if d2 < best_d2:
                best_d2 = d2
                if abs(t - 0.5) < 0.08:
                    t = 0.5
                    best_kind = "midpoint"
                else:
                    best_kind = default_kind
                wx = a.x + t * (b.x - a.x)
                wy = a.y + t * (b.y - a.y)
                wz = a.z + t * (b.z - a.z)
                best = Vertex(wx, wy, wz, label=getattr(item, "label", ""))
        return best, best_kind

    def _find_frame(self, engine, x, y, cam=None, viewport_size=None,
                    plane=None, visible_ids=None, default_kind="frame"):
        math_model = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not math_model or not target_cam:
            return None, default_kind
        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        return self._find_segment_collection(
            math_model.frames.values(),
            lambda f: (f.node_i, f.node_j),
            x, y, target_cam, w, h, visible_ids, default_kind,
        )

    def _find_link(self, engine, x, y, cam=None, viewport_size=None,
                   plane=None, visible_ids=None, default_kind="link"):
        math_model = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not math_model or not target_cam:
            return None, default_kind
        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        return self._find_segment_collection(
            getattr(math_model, "links", {}).values(),
            lambda lk: (lk.node_i, lk.node_j),
            x, y, target_cam, w, h, visible_ids, default_kind,
        )

    def _find_line(self, engine, x, y, cam=None, viewport_size=None,
                   plane=None, visible_ids=None, default_kind="line"):
        math_model = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not math_model or not target_cam:
            return None, default_kind
        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        return self._find_segment_collection(
            getattr(math_model, "lines", {}).values(),
            lambda ln: (ln.v1, ln.v2),
            x, y, target_cam, w, h, visible_ids, default_kind,
        )

    def _find_area(self, engine, x, y, cam=None, viewport_size=None,
                   plane=None, visible_ids=None, default_kind="area"):
        math_model = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not math_model or not target_cam:
            return None, default_kind
        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        mvp = target_cam.get_projection_matrix() @ target_cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for area in getattr(math_model, "areas", {}).values():
            if not self._is_visible_in_viewport(area, visible_ids):
                continue
            nodes = getattr(area, "nodes", [])
            if not nodes:
                continue
            cx = sum(n.x for n in nodes) / len(nodes)
            cy = sum(n.y for n in nodes) / len(nodes)
            cz = sum(n.z for n in nodes) / len(nodes)
            p = self._project_pt_with_size(mvp, cx, cy, cz, w, h)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = Vertex(cx, cy, cz)
        return best, default_kind

    def _find_polygon(self, engine, x, y, cam=None, viewport_size=None,
                      plane=None, visible_ids=None, default_kind="polygon"):
        math_model = engine.math_model
        target_cam = cam if cam is not None else engine.cam
        if not math_model or not target_cam:
            return None, default_kind
        w = viewport_size[0] if viewport_size else engine.w
        h = viewport_size[1] if viewport_size else engine.h
        mvp = target_cam.get_projection_matrix() @ target_cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for poly in math_model.polygons.values():
            if not self._is_visible_in_viewport(poly, visible_ids):
                continue
            cx, cy, cz = poly.centroid()
            p = self._project_pt_with_size(mvp, cx, cy, cz, w, h)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = Vertex(cx, cy, cz)
        return best, default_kind

    @staticmethod
    def _vertex_from_node(node) -> Vertex:
        return Vertex(
            node.x, node.y, node.z,
            label=getattr(node, "label", ""),
            source_node_id=getattr(node, "unique_id", None),
        )

    def cleanup(self):
        pass