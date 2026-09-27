# domain/scene.py
from typing import Dict, Optional, List
import numpy as np
from domain.element import Node, Frame, Area, Link, Element, Polygon
from domain.definition import DefinitionManager, ObjType


class Scene:
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.frames: Dict[int, Frame] = {}
        self.areas: Dict[int, Area] = {}
        self.links: Dict[int, Link] = {}
        self.polygons: Dict[int, Polygon] = {}   # YENİ
        self.def_mgr = DefinitionManager()
    
    def add_node(self, node: Node):
        self.nodes[node.unique_id] = node
    
    def add_frame(self, frame: Frame):
        self.frames[frame.unique_id] = frame
        frame.node_i.add_connection(frame)
        frame.node_j.add_connection(frame)
    
    def add_area(self, area: Area):
        self.areas[area.unique_id] = area
        for node in area.nodes:
            node.add_connection(area)
    
    def add_link(self, link: Link):
        self.links[link.unique_id] = link
        link.node_i.add_connection(link)
        link.node_j.add_connection(link)

    def add_polygon(self, polygon: Polygon):
        self.polygons[polygon.unique_id] = polygon

    def can_remove(self, element) -> tuple:
        """
        Eleman silinebilir mi?
        Returns: (bool, reason_str)
        """
        # Node sadece bağlantısı yoksa silinebilir
        if isinstance(element, Node):
            if element.connected:
                return False, f"Node bağlı {len(element.connected)} eleman var"
        return True, ""


    def remove_element(self, element) -> bool:
        """
        Elementi scene'den çıkar. Başarılıysa True.
        Bağlı Node'ların 'connected' listesini de temizler.
        """
        ok, _ = self.can_remove(element)
        if not ok:
            return False
        
        if isinstance(element, Node):
            if element.unique_id not in self.nodes:
                return False
            del self.nodes[element.unique_id]
            return True
        
        if isinstance(element, Frame):
            if element.unique_id not in self.frames:
                return False
            # Node'lardan referansı sil
            for n in (element.node_i, element.node_j):
                n.connected = [
                    (t, eid) for (t, eid) in n.connected
                    if eid != element.element_id
                ]
            del self.frames[element.unique_id]
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
            return True
        
        if isinstance(element, Polygon):
            if element.unique_id not in self.polygons:
                return False
            del self.polygons[element.unique_id]
            return True
        
        return False


    def restore_element(self, element):
        """
        Silinen elementi geri koy.
        Node'ların 'connected' listesini yeniden inşa eder.
        """
        if isinstance(element, Node):
            self.nodes[element.unique_id] = element
        
        elif isinstance(element, Frame):
            self.frames[element.unique_id] = element
            # Node'lara geri bağla
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

    def mark_dirty_from_node(self, node: Node):
        """Node değişince bağlı tüm elemanları dirty yap"""
        for obj_type, elem_id in node.connected:
            elem = self.get_element_by_id(elem_id)  # Bu metod yok!
            if elem:
                elem.mark_dirty()
    
    # ===== YARDIMCI =====
    def get_element_by_id(self, element_id: str) -> Optional[Element]:
        """element_id (UUID) ile element bul"""
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
        elements.update(self.polygons)     # YENİ
        return elements
    
    def get_selected(self) -> List[Element]:
        selected = []
        for e in self.frames.values():
            if e.is_selected:
                selected.append(e)
        for e in self.nodes.values():
            if e.is_selected:
                selected.append(e)
        for e in self.areas.values():
            if e.is_selected:
                selected.append(e)
        for e in self.links.values():
            if e.is_selected:
                selected.append(e)
        for e in self.polygons.values():
            if e.is_selected:
                selected.append(e)
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
        """unique_id'den elementi bul"""
        element = self.frames.get(unique_id)
        if element:
            return element
        element = self.nodes.get(unique_id)
        if element:
            return element
        element = self.areas.get(unique_id)
        if element:
            return element
        element = self.links.get(unique_id)
        if element:
            return element
        element = self.polygons.get(unique_id)
        if element:
            return element
        return None
    