# domain/scene.py
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from data.enums import ObjType
from domain.bounds import Bounds3D
from domain.element import Area, Element, Frame, Link, Node
from domain.line import Line
from domain.polygon import Polygon


@dataclass
class PolygonAnalysisData:
    windplane: dict = field(default_factory=dict)
    uniform_to_frame_loads: list = field(default_factory=list)
    associated_frame_ids: list[int] = field(default_factory=list)
    assigned_loads: list = field(default_factory=list)
    transfer_target: str = "frames"
    transfer_dist_type: str = "one_way"
    is_load_area: bool = False


class MathModel:
    """Structural analysis entities, independent of presentation data."""

    def __init__(self):
        self.nodes: dict[int, Node] = {}
        self.frames: dict[int, Frame] = {}
        self.areas: dict[int, Area] = {}
        self.links: dict[int, Link] = {}
        self.polygons: dict[int, Polygon] = {}
        self.lines: dict[int, Line] = {}
        self.polygon_analysis: dict[int, PolygonAnalysisData] = {}
        self._bounds: Bounds3D | None = None
        self.units = "N, mm, C"
        self._is_dirty = True
        self._plane_associations_dirty = True
        self._render_filter: set | None = None

    def compute_bounds(self) -> Bounds3D | None:
        coords = [
            (node.x, node.y, node.z)
            for node in self.nodes.values()
            if getattr(node, "is_visible", True)
        ]
        for element in (*self.frames.values(), *self.links.values()):
            if not getattr(element, "is_visible", True):
                continue
            for node in (element.node_i, element.node_j):
                if node is not None:
                    coords.append((node.x, node.y, node.z))
        for area in self.areas.values():
            if getattr(area, "is_visible", True):
                coords.extend(
                    (node.x, node.y, node.z) for node in area.nodes
                )
        for polygon in self.polygons.values():
            if getattr(polygon, "is_visible", True):
                coords.extend(
                    (node.x, node.y, node.z) for node in polygon.nodes
                )
                for zones in polygon.zone_children_by_direction.values():
                    for zone in zones:
                        zone_coords = (
                            zone.get("coords", ())
                            if isinstance(zone, dict)
                            else getattr(zone, "coords", ())
                        )
                        coords.extend(
                            tuple(float(value) for value in point[:3])
                            for point in zone_coords
                            if len(point) >= 3
                        )
        for line in self.lines.values():
            if getattr(line, "visible", True):
                coords.extend(
                    (vertex.x, vertex.y, vertex.z) for vertex in line.vertices
                )
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
        self.clear_bounds()
        self.invalidate_plane_associations()

    def invalidate_plane_associations(self):
        self._plane_associations_dirty = True

    def mark_plane_associations_current(self):
        self._plane_associations_dirty = False

    def refresh_plane_associations(self, planes, force=False, scene=None):
        if not force and not self._plane_associations_dirty:
            return False
        plane_values = planes.values() if isinstance(planes, dict) else planes
        for plane in plane_values:
            plane.refresh_assoc(self, scene)
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

    def add_polygon(self, polygon: Polygon):
        self.polygons[polygon.unique_id] = polygon
        self.mark_dirty()

    def add_line(self, line: Line):
        self.lines[line.unique_id] = line
        self.mark_dirty()

    def can_remove(self, element: Element) -> tuple[bool, str]:
        if isinstance(element, Node) and element.connected:
            return False, f"Node'a bağlı {len(element.connected)} eleman"
        return True, ""

    def remove_element(self, element: Element | Polygon | Line) -> bool:
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
        if isinstance(element, (Polygon, Line)):
            self.mark_dirty()
            return
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
        for b in (
            self.frames, self.nodes, self.areas, self.links,
            self.polygons, self.lines,
        ):
            if unique_id in b: return b[unique_id]
        return None

    @property
    def all_elements(self):
        out = {}
        out.update(self.nodes)
        out.update(self.frames)
        out.update(self.areas)
        out.update(self.links)
        out.update(self.polygons)
        out.update(self.lines)
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
        bounds = self.bounds
        if bounds is None:
            return np.array([0.0, 0.0, 0.0]), 1.0
        return bounds.center, bounds.size or 1.0

    def _bucket(self, element: Element | Polygon | Line):
        if isinstance(element, Node): return self.nodes
        if isinstance(element, Frame): return self.frames
        if isinstance(element, Area): return self.areas
        if isinstance(element, Link): return self.links
        if isinstance(element, Polygon): return self.polygons
        if isinstance(element, Line): return self.lines
        return None

    def is_element_added(self, element: Element | Polygon | Line) -> bool:
        b = self._bucket(element)
        return b is not None and element.unique_id in b

    def add_element(self, element: Element | Polygon | Line) -> bool:
        if self.is_element_added(element): return False
        fn = {Node: self.add_node, Frame: self.add_frame,
              Area: self.add_area, Link: self.add_link,
              Polygon: self.add_polygon, Line: self.add_line}.get(type(element))
        if fn is None: return False
        fn(element)
        return True

    def __repr__(self):
        return (f"<MathModel nodes={len(self.nodes)} frames={len(self.frames)} "
                f"areas={len(self.areas)} links={len(self.links)} "
                f"polygons={len(self.polygons)} lines={len(self.lines)}>")

    def summary(self) -> str:
        n_mass = sum(1 for n in self.nodes.values() if n.has_mass())
        n_con = sum(1 for n in self.nodes.values() if n.constraint_name)
        n_spring = sum(
            1 for n in self.nodes.values()
            if any(abs(getattr(n, f"spring_{d}", 0.0)) > 1e-12
                   for d in ("u1", "u2", "u3", "r1", "r2", "r3"))
        )
        return (f"MathModel:\n"
                f"  Nodes: {len(self.nodes)}  (mass: {n_mass}, constraint: {n_con}, spring: {n_spring})\n"
                f"  Frames: {len(self.frames)}\n"
                f"  Areas: {len(self.areas)}\n"
                f"  Links: {len(self.links)}\n"
                f"  Polygons: {len(self.polygons)}\n"
                f"  Lines: {len(self.lines)}")