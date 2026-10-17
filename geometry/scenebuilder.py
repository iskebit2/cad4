# geometry/scenebuilder.py
from typing import Dict, Tuple, Optional, List
from data.enums import LinkPropType, MatType, SectionType
from domain.definition import LinkProp, LinkPropLinear, Material, Restraint, Section
from domain.element import Node, Frame, Area, Link
from domain.project import Project

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class SceneBuilder:
    def __init__(self, project: Project):
        self.project = project
        self.scene = project.scene  # Sahne doğrudan projenin sahnesidir
        self._node_cache: Dict[str, Node] = {}
        
    def create_material(self, name: str, mat_type: MatType, 
                       E: float = 2.0e8, density: float = 7850,
                       color: Tuple[float, float, float] = (0.8, 0.8, 0.8)) -> Material:
        """Malzeme oluştur ve doğrudan Project içine kaydet"""
        material = Material(name=name, mat_type=mat_type, E1=E, 
                          density=density, color=color)
        self.project.add_material(material)
        return material
    
    def create_section(self, name: str, profile_type: SectionType,
                      profile_params: Dict[str, float],
                      material: Optional[Material] = None,
                      color: Tuple[float, float, float] = (0.8, 0.8, 0.8)) -> Section:
        """Kesit oluştur ve doğrudan Project içine kaydet"""
        section = Section(name=profile_type, profile_params=profile_params, material=material, color=color)
        self.project.add_section(section)
        return section
    
    def create_link_prop(self, name: str, prop_type: LinkPropType = LinkPropType.LINEAR,
                        Ke: Optional[Dict] = None, Ce: Optional[Dict] = None) -> LinkProp:
        """Link property oluştur ve doğrudan Project içine kaydet"""
        if prop_type == LinkPropType.LINEAR:
            prop = LinkPropLinear(name=name, Ke=Ke, Ce=Ce)
        else:
            prop = LinkProp(name=name, prop_type=prop_type)
        
        self.project.add_link_prop(prop)
        return prop
    
    def create_node(self, x: float, y: float, z: float,
                   label: str = "",
                   restraint: Optional[Dict[str, bool]] = None) -> Node:
        """Node oluştur ve sahneye ekle"""
        restraint_obj = Restraint(**restraint) if isinstance(restraint, dict) else restraint
        node = Node(x, y, z, label, restraint_obj)
        self.scene.add_node(node)
        
        if label:
            self._node_cache[label] = node
        return node
    
    def create_frame(self, node_i, node_j, section_name: str,
                    rotation_deg: float = 0.0, label: str = "") -> Frame:
        """Frame oluştur - kesiti doğrudan Project içerisinden bulur"""
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]
        
        section = self.project.get_section_by_name(section_name)
        if section is None:
            raise ValueError(f"Section '{section_name}' not found in Project!")
        
        frame = Frame(node_i, node_j, section, rotation_deg, label)
        self.scene.add_frame(frame)
        return frame
    
    def create_area(self, nodes: List, thickness: float, label: str = "") -> Area:
        """Area oluştur"""
        area_nodes = [self._node_cache[n] if isinstance(n, str) else n for n in nodes]
        area = Area(area_nodes, thickness, label)
        self.scene.add_area(area)
        return area
    
    def create_link(self, node_i, node_j, prop_name: str = "LINK1",
                   label: str = "") -> Link:
        """Link oluştur"""
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]
        
        link = Link(node_i, node_j, prop_name, label)
        self.scene.add_link(link)
        return link