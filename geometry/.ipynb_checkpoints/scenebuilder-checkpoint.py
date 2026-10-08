# geometry/scenebuilder.py
from typing import Dict,Tuple,Optional, List
from domain.scene import Scene
from domain.definition import MatType, Material, Section, SectionType, LinkPropType,LinkProp, LinkPropLinear, Restraint
from domain.definition_manager import DefinitionManager
from domain.element import Node, Frame, Area, Link

from logging_config import CadLogger
logger = CadLogger.get(__name__)

class SceneBuilder:
    def __init__(self):
        self.scene = Scene()
        self.def_mgr = self.scene.def_mgr
        self._node_cache: Dict[str, Node] = {}
        
    
    def create_material(self, name: str, mat_type: MatType, 
                       E: float = 2.0e8, density: float = 7850,
                       color: Tuple[float, float, float] = (0.8, 0.8, 0.8)) -> Material:
        """Malzeme oluştur ve definition manager'a ekle"""
        material = Material(name=name, mat_type=mat_type, E=E, 
                          density=density, color=color)
        self.def_mgr.add_material(material)
        # logger.debug_changed("create_material")
        return material
    
    def create_section(self, name: str, profile_type: SectionType,
                      profile_params: Dict[str, float],
                      material: Optional[Material] = None,
                      color: Tuple[float, float, float] = (0.8, 0.8, 0.8)) -> Section:
        """Kesit oluştur ve definition manager'a ekle"""
        section = Section(name, profile_type, profile_params, material, color)
        self.def_mgr.add_section(section)
        # logger.debug_changed(f"Section '{name}' added to def_mgr. Total sections: {len(self.def_mgr.sections)}")
        # logger.debug_changed("create_section")
        return section
    
    def create_link_prop(self, name: str, prop_type: LinkPropType = LinkPropType.LINEAR,
                        Ke: Optional[Dict] = None, Ce: Optional[Dict] = None) -> LinkProp:
        """Link property oluştur"""
        if prop_type == LinkPropType.LINEAR:
            prop = LinkPropLinear(name=name, Ke=Ke, Ce=Ce)
        else:
            prop = LinkProp(name=name, prop_type=prop_type)
        
        self.def_mgr.add_link_prop(prop)
        # logger.debug_changed("create_link_prop")
        return prop
    
    def create_node(self, x: float, y: float, z: float,
                   label: str = "",
                   restraint: Optional[Dict[str, bool]] = None) -> Node:
        """Node oluştur"""
        restraint_obj = None
        if restraint is not None:
            restraint_obj = Restraint.from_dict(restraint)
        
        node = Node(x, y, z, label, restraint_obj)
        self.scene.add_node(node)
        
        if label:
            self._node_cache[label] = node

        # logger.debug_changed("create_node")
        return node
    
    def create_frame(self, node_i, node_j, section_name: str,  # section_name ile
                    rotation_deg: float = 0.0, label: str = "") -> Frame:
        """Frame oluştur - section ismi ile"""
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]
        
        # Section'ı definition manager'dan bul
        section = self.def_mgr.get_section_by_name(section_name)
        if section is None:
            raise ValueError(f"Section '{section_name}' not found!")
        
        frame = Frame(node_i, node_j, section, rotation_deg, label)
        self.scene.add_frame(frame)
        # logger.debug_changed("create_frame")
        return frame
    
    def create_area(self, nodes: List, thickness: float, label: str = "") -> Area:
        """Area oluştur"""
        area_nodes = []
        for n in nodes:
            if isinstance(n, str):
                n = self._node_cache[n]
            area_nodes.append(n)
        
        area = Area(area_nodes, thickness, label)
        self.scene.add_area(area)
        # logger.debug_changed("create_area")
        return area
    
    def create_link(self, node_i, node_j, prop_name: str = "LINK1",
                   label: str = "") -> Link:
        """Link oluştur - property ismi ile"""
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]
        
        link = Link(node_i, node_j, prop_name, label)
        self.scene.add_link(link)
        # logger.debug_changed("create_link")
        return link