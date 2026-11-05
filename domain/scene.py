# domain/scene.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from data.enums import ObjType
from domain.element import Area, Element, Frame, Link, Node


@dataclass
class Bounds3D:
    min: np.ndarray
    max: np.ndarray

    @property
    def center(self): return 0.5 * (self.min + self.max)

    @property
    def size(self): return float(np.linalg.norm(self.max - self.min))

    @property
    def half_size(self): return 0.5 * (self.max - self.min)


class Scene:
    def __init__(self, project: Any = None):
        self.nodes: dict[int, Node] = {}
        self.frames: dict[int, Frame] = {}
        self.areas: dict[int, Area] = {}
        self.links: dict[int, Link] = {}
        self._bounds: Bounds3D | None = None
        self.project = project
        self.show_local_axes = False
        self.show_local_axes_for_selected = True
        self.show_local_axes_scale = 1.0
        self.units = "N, mm, C"
        self._is_dirty = True
        self._plane_associations_dirty = True
        self._render_filter: set | None = None

    def compute_bounds(self) -> Bounds3D | None:
        coords = [(n.x, n.y, n.z) for n in self.nodes.values() if getattr(n, "is_visible", True)]
        if not coords: return None
        arr = np.array(coords, dtype=float)
        return Bounds3D(min=arr.min(axis=0), max=arr.max(axis=0))

    @property
    def bounds(self):
        if self._bounds is None:
            self._bounds = self.compute_bounds()
        return self._bounds

    def refresh_bounds(self):
        self._bounds = self.compute_bounds()
        return self._bounds

    def clear_bounds(self):
        self._bounds = None

    def mark_dirty(self):
        self._is_dirty = True
        self.invalidate_plane_associations()

    def invalidate_plane_associations(self):
        self._plane_associations_dirty = True

    def mark_plane_associations_current(self):
        self._plane_associations_dirty = False

    def refresh_plane_associations(self, force=False) -> bool:
        if not force and not self._plane_associations_dirty:
            return False
        if self.project is None:
            self.mark_plane_associations_current()
            return False
        for plane in self.project.all_planes().values():
            plane.refresh_assoc(self)
        self.mark_plane_associations_current()
        return True

    def is_dirty(self):
        return self._is_dirty

    def clear_dirty(self):
        self._is_dirty = False

    def add_node(self, node: Node):
        self.nodes[node.unique_id] = node
        self.mark_dirty()

    def add_frame(self, frame: Frame):
        self.frames[frame.unique_id] = frame
        if frame.node_i: frame.node_i.add_connection(frame)
        if frame.node_j: frame.node_j.add_connection(frame)
        self.mark_dirty()

    def add_area(self, area: Area):
        self.areas[area.unique_id] = area
        for node in area.nodes:
            node.add_connection(area)
        self.mark_dirty()

    def add_link(self, link: Link):
        self.links[link.unique_id] = link
        if link.node_i: link.node_i.add_connection(link)
        if link.node_j: link.node_j.add_connection(link)
        self.mark_dirty()

    def can_remove(self, element: Element) -> tuple[bool, str]:
        if isinstance(element, Node) and element.connected:
            return False, f"Node'a bağlı {len(element.connected)} eleman"
        return True, ""

    def remove_element(self, element: Element) -> bool:
        ok, _ = self.can_remove(element)
        if not ok: return False
        bucket = self._bucket(element)
        if bucket is None or element.unique_id not in bucket: return False
        if isinstance(element, (Frame, Link)):
            for n in (element.node_i, element.node_j):
                if n:
                    n.connected = [(t, eid) for t, eid in n.connected if eid != element.unique_id]
        elif isinstance(element, Area):
            for n in element.nodes:
                n.connected = [(t, eid) for t, eid in n.connected if eid != element.unique_id]
        del bucket[element.unique_id]
        self.mark_dirty()
        return True

    def restore_element(self, element: Element):
        bucket = self._bucket(element)
        if bucket is None: return
        bucket[element.unique_id] = element
        t = ObjType.FRAME if isinstance(element, Frame) else (ObjType.LINK if isinstance(element, Link) else ObjType.AREA)
        nodes = ([element.node_i, element.node_j] if isinstance(element, (Frame, Link))
                 else element.nodes if isinstance(element, Area) else [])
        for n in nodes:
            if n and (t, element.unique_id) not in n.connected:
                n.connected.append((t, element.unique_id))
        self.mark_dirty()

    def mark_dirty_from_node(self, node):
        if node is None:
            return
        for t, eid in node.connected:
            name = {ObjType.FRAME: "frames", ObjType.AREA: "areas",
                    ObjType.LINK: "links"}.get(t)
            if name is None:
                continue
            bucket = getattr(self, name, None)
            if bucket and int(eid) in bucket:
                bucket[int(eid)].mark_dirty()
        self.mark_dirty()

    def get_element_by_label(self, label: str):
        for e in self.all_elements.values():
            if str(e.label) == str(label): return e
        return None

    def get_element_by_id(self, unique_id):
        for e in self.all_elements.values():
            if str(e.unique_id) == str(unique_id): return e
        return None

    def get_element_by_unique_id(self, unique_id: int):
        for b in (self.frames, self.nodes, self.areas, self.links):
            if unique_id in b: return b[unique_id]
        return None

    @property
    def all_elements(self):
        out = {}
        out.update(self.nodes)
        out.update(self.frames)
        out.update(self.areas)
        out.update(self.links)
        return out

    def get_selected(self):
        return [e for e in self.all_elements.values() if e.is_selected]

    def clear_selections(self) -> int:
        count = 0
        for e in self.all_elements.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        return count

    def get_bounds(self):
        pts = [n.coords for n in self.nodes.values()]
        for f in self.frames.values():
            if f.node_i and f.node_j:
                pts.extend([f.node_i.coords, f.node_j.coords])
        if not pts: return np.array([0.0, 0.0, 0.0]), 1.0
        a = np.array(pts)
        mn, mx = a.min(axis=0), a.max(axis=0)
        return (mn + mx) * 0.5, float(np.linalg.norm(mx - mn))

    def _bucket(self, element: Element):
        if isinstance(element, Node): return self.nodes
        if isinstance(element, Frame): return self.frames
        if isinstance(element, Area): return self.areas
        if isinstance(element, Link): return self.links
        return None

    def is_element_added(self, element: Element) -> bool:
        b = self._bucket(element)
        return b is not None and element.unique_id in b

    def add_element(self, element: Element) -> bool:
        if self.is_element_added(element): return False
        fn = {Node: self.add_node, Frame: self.add_frame,
              Area: self.add_area, Link: self.add_link}.get(type(element))
        if fn is None: return False
        fn(element)
        return True

    def __repr__(self):
        return (f"<Scene nodes={len(self.nodes)} frames={len(self.frames)} "
                f"areas={len(self.areas)} links={len(self.links)}>")

    def summary(self) -> str:
        n_mass = sum(1 for n in self.nodes.values() if n.has_mass())
        n_con = sum(1 for n in self.nodes.values() if n.constraint_name)
        n_spring = sum(
            1 for n in self.nodes.values()
            if any(abs(getattr(n, f"spring_{d}", 0.0)) > 1e-12
                   for d in ("u1", "u2", "u3", "r1", "r2", "r3"))
        )
        return (f"Scene:\n"
                f"  Nodes: {len(self.nodes)}  (mass: {n_mass}, constraint: {n_con}, spring: {n_spring})\n"
                f"  Frames: {len(self.frames)}\n"
                f"  Areas: {len(self.areas)}\n"
                f"  Links: {len(self.links)}")