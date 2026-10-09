# domain/element.py
from turtle import color
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum, auto
import uuid
import math
from logging_config import CadLogger

from domain.definition import AreaGravityLoad, AreaStrainLoad, AreaSurfacePressureLoad, AreaTemperatureLoad, AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad, FrameDistributedLoad, FrameGravityLoad, FramePointLoad, FrameTemperatureLoad, Restraint, Section, ObjType, SectionType, PointLoad

from logging_config import CadLogger

logger = CadLogger.get(__name__)

def id_to_color(obj_id: int) -> Tuple[float, float, float]:
    r = ((obj_id >> 0) & 0xFF) / 255.0
    g = ((obj_id >> 8) & 0xFF) / 255.0
    b = ((obj_id >> 16) & 0xFF) / 255.0
    return r, g, b

def color_to_id(r: int, g: int, b: int) -> int:
    return int(r) + (int(g) << 8) + (int(b) << 16)



class Element:
    _id_counter = 1
    
    def __init__(self,
                 label: str = "",
                 is_selected: bool = False,
                 is_visible: bool = True,
                 needs_update: bool = True,
                 color=None
                 ):
        self.unique_id = Element._id_counter
        Element._id_counter += 1
        self.element_id = str(uuid.uuid4())
        self.label = label
        self.is_selected = is_selected
        self.is_visible = is_visible
        self.needs_update = needs_update
        self.pick_id= self.unique_id
        self.element_type= None
        self.color = list(color[:3]) if color is not None else [0.7, 0.7, 0.7]
        
    def toggle_selection(self):
        self.is_selected = not self.is_selected
    
    def mark_dirty(self):
        self.needs_update = True
        
    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"id={self.unique_id}, "
            f"label={self.label!r}, "
            f"selected={self.is_selected}, "
            f"visible={self.is_visible}, "
            f"element_type={self.element_type}, "
            f"pick_id={self.pick_id}>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Tüm elemanlarda ortak olan temel meta veriler"""
        return {
            "unique_id": self.unique_id,
            "element_id": self.element_id,
            "element_type": self.element_type,
            "label": self.label,
            "is_selected": self.is_selected,
            "is_visible": self.is_visible
        }

    def _apply_base_dict(self, data: Dict[str, Any]):
        """from_dict sırasında taban sınıf değişkenlerini geri yükler"""
        if "unique_id" in data:
            self.unique_id = data["unique_id"]
            Element._id_counter = max(Element._id_counter, self.unique_id + 1)
        if "element_id" in data:
            self.element_id = data["element_id"]
        self.is_selected = data.get("is_selected", False)
        self.is_visible = data.get("is_visible", True)
        self.pick_id = self.unique_id



class Node(Element):
    DOF_ORDER = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        label: str = "",
        restraint: Optional[Restraint] = None,
        mass: Tuple[float, ...] = (0.0,) * 6,
        spring: Tuple[float, ...] = (),color=None
    ):
        super().__init__(label, color=color)

        self.element_type = "Node"

        # Geometri
        self.x = x
        self.y = y
        self.z = z
        self.restraint = restraint
        self.mass = tuple(mass)
        self.spring = tuple(spring)
        self.dof_indices: List[Optional[int]] = [None] * 6
        self.connected: List[Tuple[ObjType, str]] = []
        self.loads: List[PointLoad] = []

    # -------------------------------------------------
    # GEOMETRİ
    # -------------------------------------------------
    @property
    def coords(self):
        return (self.x, self.y, self.z)

    def set_coords(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.mark_dirty()

    def distance_to(self, other: 'Node') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    # -------------------------------------------------
    # RESTRAINT
    # -------------------------------------------------
    def is_restrained(self) -> bool:
        return self.restraint is not None

    def is_free(self) -> bool:
        return self.restraint is None or self.restraint.is_free()
        
    def has_any_restraint(self) -> bool:
        return self.restraint is not None and not self.restraint.is_free()

    # -------------------------------------------------
    # SOLVER YARDIMCI
    # -------------------------------------------------
    def enumerate_dofs(self, start_index: int) -> int:
        """
        Global DOF numaralandırması.
        Sadece serbest DOF'lara index verir.
        """
        current = start_index

        for i, dof_name in enumerate(self.DOF_ORDER):

            restrained = getattr(self.restraint, dof_name, False) if self.restraint else False

            if restrained:
                self.dof_indices[i] = None
            else:
                self.dof_indices[i] = current
                current += 1

        return current

    def get_dof_index(self, dof_name: str) -> Optional[int]:
        i = self.DOF_ORDER.index(dof_name)
        return self.dof_indices[i]

    # -------------------------------------------------
    # CONNECTIONS
    # -------------------------------------------------
    def add_connection(self, element):
        if isinstance(element, Frame):
            self.connected.append((ObjType.FRAME, element.element_id))
        elif isinstance(element, Area):
            self.connected.append((ObjType.AREA, element.element_id))
        elif isinstance(element, Link):
            self.connected.append((ObjType.LINK, element.element_id))

    # -------------------------------------------------
    # DIRTY FLAG
    # -------------------------------------------------
    def mark_dirty(self):
        self.needs_update = True

    @classmethod
    def from_list(cls, values):
        return cls(*values)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "restraint": self.restraint.as_dict() if self.restraint else None,
            "mass": list(self.mass),
            "spring": list(self.spring)
        })
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        restraint_data = data.get("restraint")
        restraint = Restraint.from_dict(restraint_data) if restraint_data else None
        node = cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            label=data.get("label", ""),
            restraint=restraint,
            mass=tuple(data.get("mass", (0.0,) * 6)),
            spring=tuple(data.get("spring", ()))
        )
        node._apply_base_dict(data)
        return node

class Frame(Element):
    def __init__(self, node_i: Node, node_j: Node, section: Section,
                 rotation_deg: float = 0.0, label: str = "", color=None):
        if color is None and section is not None and hasattr(section, 'color'):
            color = list(section.color[:3])
        super().__init__(label, color=color)
        self.element_type= "Frame"
        self.node_i = node_i
        self.node_j = node_j
        self.section = section
        self.rotation_deg = rotation_deg
        self.release_i = None
        self.release_j = None

        self.point_loads: List[FramePointLoad] = []
        self.dist_loads: List[FrameDistributedLoad] = []
        self.gravity_loads: List[FrameGravityLoad] = []
        self.temp_loads: List[FrameTemperatureLoad] = []

    
    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_i_id": self.node_i.unique_id,
            "node_j_id": self.node_j.unique_id,
            "section_name": self.section.name if self.section else "",
            "rotation_deg": self.rotation_deg
        })
        return data

class Area(Element):
    def __init__(self, nodes: List[Node], thickness: float, label: str = "",color=None):
        if color is None:
            color = [0.5, 0.8, 1.0]
        super().__init__(label, color=color)
        self.element_type= "Area"
        self.nodes = nodes
        self.thickness = thickness

        self.material = None          # ← YENİ
        self.section_name = ""        # ← YENİ
        self.gravity_loads: List[AreaGravityLoad] = []
        self.ref_temp: Optional[float] = None
        self.strain_loads: List[AreaStrainLoad] = []
        self.surface_pressures: List[AreaSurfacePressureLoad] = []
        self.temp_loads: List[AreaTemperatureLoad] = []
        self.uniform_loads: List[AreaUniformLoad] = []
        self.uniform_to_frame_loads: List[AreaUniformToFrameLoad] = []
        self.wind_pressures: List[AreaWindPressureLoad] = []

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_ids": [n.unique_id for n in self.nodes],
            "thickness": self.thickness,
            "section_name": self.section_name
        })
        return data

class Link(Element):
    def __init__(self, node_i: Node, node_j: Node, propname: str = "LINK1", label: str = "",color=None):
        if color is None:
            color = [0.5, 0.5, 0.5]
        super().__init__(label, color=color)
        self.element_type= "Link"
        self.node_i = node_i
        self.node_j = node_j
        self.propname = propname

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_i_id": self.node_i.unique_id,
            "node_j_id": self.node_j.unique_id,
            "propname": self.propname
        })
        return data

class PolygonType(Enum):
    GENERIC = auto()       # Standart/Varsayılan poligon
    SURFACE = auto()       # Yapısal yüzey (Duvar, Çatı döşemesi vb.)
    ZONE = auto()          # Rüzgar/Kar vb. yük bölgeleri
    SECTION_CUT = auto()   # Kesit tesiri alma düzlemleri
    LOAD_AREA = auto()     # Yayılı yük etki alanları
    
class Polygon(Element):
    def __init__(self, nodes: List[Node], label: str = "", poly_type: PolygonType = PolygonType.GENERIC, color=None):
        if color is None:
            color = [0.8, 0.3, 0.8, 0.6]
        super().__init__(label, color=color)
        self.element_type = "Polygon"
        self.poly_type = poly_type  # Enum tipi
        self.nodes = list(nodes)
        self.color = [0.8, 0.3, 0.8, 0.6]  # Default RGBA
        self.windplane: Dict[str, Any] = {}
    
    def is_valid(self) -> bool:
        return len(self.nodes) >= 3
    
    def centroid(self):
        n = len(self.nodes)
        if n == 0: return (0, 0, 0)
        return (
            sum(nd.x for nd in self.nodes) / n,
            sum(nd.y for nd in self.nodes) / n,
            sum(nd.z for nd in self.nodes) / n,
        )
    
    def __repr__(self):
        return f"<Polygon {self.label} nodes={len(self.nodes)}>"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_ids": [n.unique_id for n in self.nodes],
            "color": self.color,
            "poly_type": self.poly_type.name,  # JSON kaydı için enum adını saklıyoruz
            "windplane": self.windplane
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], nodes_map: Dict[int, Node]) -> 'Polygon':
        # JSON'dan okurken Enum'a geri çevirme
        poly_nodes = [nodes_map[nid] for nid in data.get("node_ids", []) if nid in nodes_map]
        
        type_str = data.get("poly_type", "GENERIC")
        try:
            poly_type = PolygonType[type_str]
        except KeyError:
            poly_type = PolygonType.GENERIC

        poly = cls(nodes=poly_nodes, label=data.get("label", ""), poly_type=poly_type)
        poly.color = data.get("color", [0.8, 0.3, 0.8, 0.6])
        poly.windplane = data.get("windplane", {})
        return poly