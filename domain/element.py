# domain/element.py
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid
import math
import logging

from domain.definition import Restraint, Section, ObjType, SectionType

logger = logging.getLogger(__name__)

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
                 needs_update: bool = True
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

from typing import Optional, List, Tuple
import math

class Node(Element):
    DOF_ORDER = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

    def __init__(self,
                 x: float,
                 y: float,
                 z: float,
                 label: str = "",
                 restraint: Optional[Restraint] = None):
        
        super().__init__(label)
        self.element_type= "Node"
        # Geometri
        self.x = x
        self.y = y
        self.z = z

        # Fiziksel sınır şartı
        self.restraint: Optional[Restraint] = restraint

        # Solver için global DOF indexleri (assemble aşamasında doldurulur)
        self.dof_indices: List[Optional[int]] = [None] * 6

        # Bağlantılar
        self.connected: List[Tuple[ObjType, str]] = []
    
    @classmethod
    def from_dict(cls, data: dict):
        restraint_data = data.get("restraint")

        restraint = None
        if restraint_data:
            restraint = Restraint.from_dict(restraint_data)

        return cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            label=data.get("label", ""),
            restraint=restraint
        )
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


class Frame(Element):
    def __init__(self, node_i: Node, node_j: Node, section: Section,
                 rotation_deg: float = 0.0, label: str = ""):
        super().__init__(label)
        self.element_type= "Frame"
        self.node_i = node_i
        self.node_j = node_j
        self.section = section
        self.rotation_deg = rotation_deg
        self.release_i = None
        self.release_j = None
    
    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

class Area(Element):
    def __init__(self, nodes: List[Node], thickness: float, label: str = ""):
        super().__init__(label)
        self.element_type= "Area"
        self.nodes = nodes
        self.thickness = thickness

class Link(Element):
    def __init__(self, node_i: Node, node_j: Node, propname: str = "LINK1", label: str = ""):
        super().__init__(label)
        self.element_type= "Link"
        self.node_i = node_i
        self.node_j = node_j
        self.propname = propname

class Polygon(Element):
    """
    Sadece görsel amaçlı poligon. Extrude edilmez.
    Köşeleri Node veya Point (şimdilik sadece Node) olabilir.
    """
    def __init__(self, nodes: List[Node], label: str = ""):
        super().__init__(label)
        self.element_type = "Polygon"
        self.nodes = list(nodes)   # En az 3
        self.color = [0.8, 0.3, 0.8]   # Mor (default)
    
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