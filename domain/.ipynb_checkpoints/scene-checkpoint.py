# domain/scene.py
from typing import Dict, Optional, List, Any
import numpy as np
from data.enums import ObjType
from domain.element import Node, Frame, Area, Link, Element, Polygon


class Scene:
    def __init__(self, project: Any = None):
        self.nodes: Dict[int, Node] = {}
        self.frames: Dict[int, Frame] = {}
        self.areas: Dict[int, Area] = {}
        self.links: Dict[int, Link] = {}
        self.polygons: Dict[int, Polygon] = {}
        self.project = project  # Üst proje referansı
        
        self.show_local_axes = False
        self.show_local_axes_for_selected = True
        self.show_local_axes_scale = 1.0
        self.units = "N, mm, C"
        self._is_dirty: bool = True

    def mark_dirty(self):
        self._is_dirty = True

    def is_dirty(self) -> bool:
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

    def can_remove(self, element: Element) -> tuple[bool, str]:
        if isinstance(element, Node) and element.connected:
            return False, f"Node'a bağlı {len(element.connected)} eleman var."
        return True, ""

    def remove_element(self, element: Element) -> bool:
        ok, _ = self.can_remove(element)
        if not ok:
            return False
        
        bucket = self._bucket(element)
        if bucket is None or element.unique_id not in bucket:
            return False

        if isinstance(element, (Frame, Link)):
            for n in (element.node_i, element.node_j):
                if n:
                    n.connected = [(t, eid) for (t, eid) in n.connected if eid != element.unique_id]
        elif isinstance(element, Area):
            for n in element.nodes:
                n.connected = [(t, eid) for (t, eid) in n.connected if eid != element.unique_id]

        del bucket[element.unique_id]
        self.mark_dirty()
        return True

    def restore_element(self, element: Element):
        bucket = self._bucket(element)
        if bucket is not None:
            bucket[element.unique_id] = element
            if isinstance(element, (Frame, Link)):
                for n in (element.node_i, element.node_j):
                    if n and (ObjType.FRAME if isinstance(element, Frame) else ObjType.LINK, element.unique_id) not in n.connected:
                        n.connected.append((ObjType.FRAME if isinstance(element, Frame) else ObjType.LINK, element.unique_id))
            elif isinstance(element, Area):
                for n in element.nodes:
                    if (ObjType.AREA, element.unique_id) not in n.connected:
                        n.connected.append((ObjType.AREA, element.unique_id))
            self.mark_dirty()

    def mark_dirty_from_node(self, node: Node):
        if node is None:
            return

        for obj_type, elem_uid in node.connected:
            bucket = self._bucket_for_type(obj_type)
            if bucket is None:
                continue
            elem = bucket.get(int(elem_uid)) if elem_uid is not None else None
            if elem is not None:
                elem.mark_dirty()

        self.mark_dirty()


    def _bucket_for_type(self, obj_type) -> Optional[Dict]:
        if obj_type == ObjType.FRAME:    return self.frames
        if obj_type == ObjType.AREA:     return self.areas
        if obj_type == ObjType.LINK:     return self.links
        return None
    
    def get_element_by_id(self, unique_id: str) -> Optional[Element]:
        for elem in self.all_elements.values():
            if elem.unique_id == unique_id:
                return elem
        return None

    def get_element_by_unique_id(self, unique_id: int) -> Optional[Element]:
        for bucket in (self.frames, self.nodes, self.areas, self.links, self.polygons):
            if unique_id in bucket:
                return bucket[unique_id]
        return None

    @property
    def all_elements(self) -> Dict[int, Element]:
        elements = {}
        elements.update(self.nodes)
        elements.update(self.frames)
        elements.update(self.areas)
        elements.update(self.links)
        elements.update(self.polygons)
        return elements
    
    def get_selected(self) -> List[Element]:
        return [e for e in self.all_elements.values() if e.is_selected]
    
    def clear_selections(self) -> int:
        count = 0
        for e in self.all_elements.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        return count
    
    def get_bounds(self) -> tuple[np.ndarray, float]:
        points = [n.coords for n in self.nodes.values()]
        for f in self.frames.values():
            if f.node_i and f.node_j:
                points.extend([f.node_i.coords, f.node_j.coords])
        
        if not points:
            return np.array([0.0, 0.0, 0.0]), 1.0
        
        pts = np.array(points)
        min_p, max_p = pts.min(axis=0), pts.max(axis=0)
        center = (min_p + max_p) * 0.5
        size = float(np.linalg.norm(max_p - min_p))
        return center, size

    def _bucket(self, element: Element) -> Optional[Dict]:
        if isinstance(element, Node):     return self.nodes
        if isinstance(element, Frame):    return self.frames
        if isinstance(element, Area):     return self.areas
        if isinstance(element, Link):     return self.links
        if isinstance(element, Polygon):  return self.polygons
        return None

    def is_element_added(self, element: Element) -> bool:
        bucket = self._bucket(element)
        return bucket is not None and element.unique_id in bucket

    def add_element(self, element: Element) -> bool:
        if self.is_element_added(element):
            return False
        
        if isinstance(element, Node):     self.add_node(element)
        elif isinstance(element, Frame):  self.add_frame(element)
        elif isinstance(element, Area):   self.add_area(element)
        elif isinstance(element, Link):   self.add_link(element)
        elif isinstance(element, Polygon):self.add_polygon(element)
        else: return False
        return True