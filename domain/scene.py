# domain/scene.py
from dataclasses import field
from typing import Dict, Optional, List
import numpy as np
from domain.definition_manager import DefinitionManager
from domain.element import Node, Frame, Area, Link, Element, Polygon
from domain.definition import ObjType, SerializableData


class Scene(SerializableData):
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.frames: Dict[int, Frame] = {}
        self.areas: Dict[int, Area] = {}
        self.links: Dict[int, Link] = {}
        self.polygons: Dict[int, Polygon] = {}
        self.def_mgr = DefinitionManager()   # runtime kolaylık; serialize edilmez
        self.units = "N, mm, C"
        self._is_dirty: bool = True  # Doğru öznitelik tanımı

    def mark_dirty(self):
        """Sahnede bir değişiklik olduğunu işaretler."""
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
        frame.node_i.add_connection(frame)
        frame.node_j.add_connection(frame)
        self.mark_dirty()
    
    def add_area(self, area: Area):
        self.areas[area.unique_id] = area
        for node in area.nodes:
            node.add_connection(area)
        self.mark_dirty()
    
    def add_link(self, link: Link):
        self.links[link.unique_id] = link
        link.node_i.add_connection(link)
        link.node_j.add_connection(link)
        self.mark_dirty()

    def add_polygon(self, polygon: Polygon):
        self.polygons[polygon.unique_id] = polygon
        self.mark_dirty()

    def can_remove(self, element) -> tuple:
        """
        Eleman silinebilir mi?
        Returns: (bool, reason_str)
        """
        if isinstance(element, Node):
            if element.connected:
                return False, f"Node bağlı {len(element.connected)} eleman var"
        return True, ""


    def remove_element(self, element) -> bool:
        """
        Elementi scene'den çıkar. Başarılıysa True.
        """
        ok, _ = self.can_remove(element)
        if not ok:
            return False
        
        if isinstance(element, Node):
            if element.unique_id not in self.nodes:
                return False
            del self.nodes[element.unique_id]
            self.mark_dirty()
            return True
        
        if isinstance(element, Frame):
            if element.unique_id not in self.frames:
                return False
            for n in (element.node_i, element.node_j):
                n.connected = [
                    (t, eid) for (t, eid) in n.connected
                    if eid != element.element_id
                ]
            del self.frames[element.unique_id]
            self.mark_dirty()
            return True
        
        if isinstance(element, Link):
            if element.unique_id not in self.links:
                return False
            for n in (element.node_i, element.node_j):
                n.connected = [
                    (t, eid) for (t, eid) in n.connected
                    if eid != element.element_id
                ]
            del self.links[element.unique_id]
            self.mark_dirty()
            return True
        
        if isinstance(element, Area):
            if element.unique_id not in self.areas:
                return False
            for n in element.nodes:
                n.connected = [
                    (t, eid) for (t, eid) in n.connected
                    if eid != element.element_id
                ]
            del self.areas[element.unique_id]
            self.mark_dirty()
            return True
        
        if isinstance(element, Polygon):
            if element.unique_id not in self.polygons:
                return False
            del self.polygons[element.unique_id]
            self.mark_dirty()
            return True
        
        return False


    def restore_element(self, element):
        """
        Silinen elementi geri koy.
        """
        if isinstance(element, Node):
            self.nodes[element.unique_id] = element
        elif isinstance(element, Frame):
            self.frames[element.unique_id] = element
            for n in (element.node_i, element.node_j):
                if (ObjType.FRAME, element.element_id) not in n.connected:
                    n.connected.append((ObjType.FRAME, element.element_id))
        elif isinstance(element, Link):
            self.links[element.unique_id] = element
            for n in (element.node_i, element.node_j):
                if (ObjType.LINK, element.element_id) not in n.connected:
                    n.connected.append((ObjType.LINK, element.element_id))
        elif isinstance(element, Area):
            self.areas[element.unique_id] = element
            for n in element.nodes:
                if (ObjType.AREA, element.element_id) not in n.connected:
                    n.connected.append((ObjType.AREA, element.element_id))
        elif isinstance(element, Polygon):
            self.polygons[element.unique_id] = element
        
        self.mark_dirty()

    def mark_dirty_from_node(self, node: Node):
        """Node değişince bağlı tüm elemanları dirty yap"""
        for obj_type, elem_id in node.connected:
            elem = None
            try:
                elem = self.get_element_by_unique_id(int(elem_id))
            except (ValueError, TypeError):
                pass

            if elem is None:
                elem = self.get_element_by_id(str(elem_id))

            if elem:
                elem.mark_dirty()
        self.mark_dirty()
    
    def get_element_by_id(self, element_id: str) -> Optional[Element]:
        for elem in self.all_elements.values():
            if elem.element_id == element_id:
                return elem
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
        selected = []
        for e in self.frames.values():
            if e.is_selected: selected.append(e)
        for e in self.nodes.values():
            if e.is_selected: selected.append(e)
        for e in self.areas.values():
            if e.is_selected: selected.append(e)
        for e in self.links.values():
            if e.is_selected: selected.append(e)
        for e in self.polygons.values():
            if e.is_selected: selected.append(e)
        return selected
    
    def clear_selections(self) -> int:
        count = 0
        for e in self.frames.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        for e in self.nodes.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        for e in self.areas.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        for e in self.links.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        for e in self.polygons.values():
            if e.is_selected:
                e.is_selected = False
                count += 1
        return count
    
    def get_bounds(self):
        points = []
        for n in self.nodes.values():
            points.append([n.x, n.y, n.z])
        for f in self.frames.values():
            points.append([f.node_i.x, f.node_i.y, f.node_i.z])
            points.append([f.node_j.x, f.node_j.y, f.node_j.z])
        
        if not points:
            return np.array([0,0,0]), 1.0
        
        pts = np.array(points)
        min_p = pts.min(axis=0)
        max_p = pts.max(axis=0)
        center = (min_p + max_p) * 0.5
        size = np.linalg.norm(max_p - min_p)
        return center, size
    
    def get_element_by_unique_id(self, unique_id: int) -> Optional[Element]:
        element = self.frames.get(unique_id)
        if element: return element
        element = self.nodes.get(unique_id)
        if element: return element
        element = self.areas.get(unique_id)
        if element: return element
        element = self.links.get(unique_id)
        if element: return element
        element = self.polygons.get(unique_id)
        if element: return element
        return None

    def _bucket(self, element):
        if isinstance(element, Node):     return self.nodes
        if isinstance(element, Frame):    return self.frames
        if isinstance(element, Area):     return self.areas
        if isinstance(element, Link):     return self.links
        if isinstance(element, Polygon):  return self.polygons
        return None

    def is_element_added(self, element) -> bool:
        bucket = self._bucket(element)
        if bucket is None:
            return False
        return element.unique_id in bucket

    def add_element(self, element) -> bool:
        if self.is_element_added(element):
            return False

        if isinstance(element, Node):
            self.add_node(element)
        elif isinstance(element, Frame):
            self.add_frame(element)
        elif isinstance(element, Area):
            self.add_area(element)
        elif isinstance(element, Link):
            self.add_link(element)
        elif isinstance(element, Polygon):
            self.add_polygon(element)
        else:
            return False

        return True

    def to_dict(self) -> dict:
        return {
            "units":    self.units,
            "nodes":    [n.to_dict() for n in self.nodes.values()],
            "frames":   [f.to_dict() for f in self.frames.values()],
            "areas":    [a.to_dict() for a in self.areas.values()],
            "links":    [l.to_dict() for l in self.links.values()],
            "polygons": [p.to_dict() for p in self.polygons.values()],
        }

    @classmethod
    def from_dict(cls, data: dict, definitions: DefinitionManager = None) -> "Scene":
        scene = cls()
        scene.units = data.get("units", "N, mm, C")

        if definitions is not None:
            scene.def_mgr = definitions

        for n_data in data.get("nodes", []):
            scene.add_node(Node.from_dict(n_data))

        sections_map = scene.def_mgr.sections if scene.def_mgr else {}
        for f_data in data.get("frames", []):
            sec_name = f_data.get("section_name")
            if sec_name and sec_name not in sections_map and sections_map:
                f_data = {**f_data, "section_name": next(iter(sections_map))}
            elif not sec_name and sections_map:
                f_data = {**f_data, "section_name": next(iter(sections_map))}

            frame = Frame.from_dict(f_data, scene.nodes, sections_map)
            if frame.node_i and frame.node_j:
                scene.add_frame(frame)

        for a_data in data.get("areas", []):
            area = Area.from_dict(a_data, scene.nodes)
            if area.nodes:
                scene.add_area(area)

        for l_data in data.get("links", []):
            link = Link.from_dict(l_data, scene.nodes)
            if link.node_i and link.node_j:
                scene.add_link(link)

        for p_data in data.get("polygons", []):
            poly = Polygon.from_dict(p_data, scene.nodes)
            if poly.nodes:
                scene.add_polygon(poly)

        scene.mark_dirty()
        return scene