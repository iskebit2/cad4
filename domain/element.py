# domain/element.py
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum, auto
import uuid
import math

from domain.definition import AreaGravityLoad, AreaStrainLoad, AreaSurfacePressureLoad, AreaTemperatureLoad, AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad, FrameDistributedLoad, FrameGravityLoad, FramePointLoad, FrameTemperatureLoad, PointLoad, Restraint, Section, ObjType, SerializableData
from logging_config import CadLogger

logger = CadLogger.get(__name__)


def id_to_color(obj_id: int) -> Tuple[float, float, float]:
    r = ((obj_id >> 0) & 0xFF) / 255.0
    g = ((obj_id >> 8) & 0xFF) / 255.0
    b = ((obj_id >> 16) & 0xFF) / 255.0
    return r, g, b


def color_to_id(r: int, g: int, b: int) -> int:
    return int(r) + (int(g) << 8) + (int(b) << 16)


# ============================================================================
# ELEMENT BASE
# ============================================================================
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
        self.pick_id = self.unique_id
        self.element_type = None
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

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Tüm elemanlarda ortak olan temel meta veriler."""
        return {
            "unique_id": self.unique_id,
            "element_id": self.element_id,
            "element_type": self.element_type,
            "label": self.label,
            "is_selected": self.is_selected,
            "is_visible": self.is_visible,
            "color": list(self.color),
        }

    def _apply_base_dict(self, data: Dict[str, Any]):
        """from_dict sırasında taban sınıf değişkenlerini geri yükler."""
        if "unique_id" in data:
            self.unique_id = int(data["unique_id"])
            Element._id_counter = max(Element._id_counter, self.unique_id + 1)
            self.pick_id = self.unique_id
        if "element_id" in data:
            self.element_id = str(data["element_id"])
        self.is_selected = bool(data.get("is_selected", False))
        self.is_visible = bool(data.get("is_visible", True))
        if "color" in data and data["color"]:
            self.color = list(data["color"])


# ============================================================================
# NODE
# ============================================================================
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
        spring: Tuple[float, ...] = (),
        color=None
    ):
        super().__init__(label, color=color)
        self.element_type = "Node"

        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.restraint = restraint
        self.mass = tuple(mass)
        self.spring = tuple(spring)
        self.dof_indices: List[Optional[int]] = [None] * 6
        self.connected: List[Tuple[ObjType, str]] = []
        self.loads: List[Any] = []

    @property
    def coords(self):
        return (self.x, self.y, self.z)

    def set_coords(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.mark_dirty()

    def distance_to(self, other: 'Node') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def is_restrained(self) -> bool:
        return self.restraint is not None

    def is_free(self) -> bool:
        return self.restraint is None or self.restraint.is_free()

    def has_any_restraint(self) -> bool:
        return self.restraint is not None and not self.restraint.is_free()

    def enumerate_dofs(self, start_index: int) -> int:
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

    def add_connection(self, element):
        if isinstance(element, Frame):
            self.connected.append((ObjType.FRAME, element.element_id))
        elif isinstance(element, Area):
            self.connected.append((ObjType.AREA, element.element_id))
        elif isinstance(element, Link):
            self.connected.append((ObjType.LINK, element.element_id))

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "restraint": self.restraint.as_dict() if self.restraint else None,
            "mass": list(self.mass),
            "spring": list(self.spring),
            "loads": [l.to_dict() for l in self.loads],
        })
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        restraint_data = data.get("restraint")
        restraint = Restraint.from_dict(restraint_data) if restraint_data else None
        node = cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            z=data.get("z", 0.0),
            label=data.get("label", ""),
            restraint=restraint,
            mass=tuple(data.get("mass", (0.0,) * 6)),
            spring=tuple(data.get("spring", ())),
            
        )
        node._apply_base_dict(data)
        node.loads = [PointLoad.from_dict(l) for l in data.get("loads", [])]
        return node


# ============================================================================
# FRAME
# ============================================================================
class Frame(Element):
    def __init__(self, node_i: Node, node_j: Node, section: Section,
                 rotation_deg: float = 0.0, label: str = "", color=None):
        if color is None and section is not None and hasattr(section, 'color'):
            color = list(section.color[:3])
        super().__init__(label, color=color)
        self.element_type = "Frame"
        self.node_i = node_i
        self.node_j = node_j
        self.section = section
        self.rotation_deg = float(rotation_deg)
        self.release_i = None
        self.release_j = None

        self.point_loads: List[Any] = []
        self.dist_loads: List[Any] = []
        self.gravity_loads: List[Any] = []
        self.temp_loads: List[Any] = []

    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

    def get_midpoint(self):
        """Frame'in orta noktası."""
        return (
            (self.node_i.x + self.node_j.x) * 0.5,
            (self.node_i.y + self.node_j.y) * 0.5,
            (self.node_i.z + self.node_j.z) * 0.5,
        )

    def get_axis(self):
        """Frame'in birim yön vektörü (node_i → node_j)."""
        import glm
        dx = self.node_j.x - self.node_i.x
        dy = self.node_j.y - self.node_i.y
        dz = self.node_j.z - self.node_i.z
        length = (dx*dx + dy*dy + dz*dz) ** 0.5
        if length < 1e-9:
            return (1.0, 0.0, 0.0)
        return (dx / length, dy / length, dz / length)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_i_id": self.node_i.unique_id if self.node_i else None,
            "node_j_id": self.node_j.unique_id if self.node_j else None,
            "section_name": self.section.name if self.section else "",
            "rotation_deg": self.rotation_deg,
            # === YENİ: YÜKLER ===
            "point_loads":   [l.to_dict() for l in self.point_loads],
            "dist_loads":    [l.to_dict() for l in self.dist_loads],
            "gravity_loads": [l.to_dict() for l in self.gravity_loads],
            "temp_loads":    [l.to_dict() for l in self.temp_loads],
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any],
                  nodes_map: Dict[int, Node],
                  sections_map: Dict[str, Section]) -> 'Frame':
        ni = nodes_map.get(data.get("node_i_id"))
        nj = nodes_map.get(data.get("node_j_id"))
        sec_name = data.get("section_name", "")
        section = sections_map.get(sec_name) if sections_map else None

        frame = cls(
            node_i=ni,
            node_j=nj,
            section=section,
            rotation_deg=data.get("rotation_deg", 0.0),
            label=data.get("label", ""),
        )
        frame._apply_base_dict(data)
        # === YENİ: YÜKLERİ GERİ YÜKLE ===
        frame.point_loads = [
            FramePointLoad.from_dict(l) for l in data.get("point_loads", [])
        ]
        frame.dist_loads = [
            FrameDistributedLoad.from_dict(l) for l in data.get("dist_loads", [])
        ]
        frame.gravity_loads = [
            FrameGravityLoad.from_dict(l) for l in data.get("gravity_loads", [])
        ]
        frame.temp_loads = [
            FrameTemperatureLoad.from_dict(l) for l in data.get("temp_loads", [])
        ]
        return frame


# ============================================================================
# AREA
# ============================================================================
class Area(Element):
    def __init__(self, nodes: List[Node], thickness: float, label: str = "", color=None):
        if color is None:
            color = [0.5, 0.8, 1.0]
        super().__init__(label, color=color)
        self.element_type = "Area"
        self.nodes = list(nodes)
        self.thickness = float(thickness)

        self.material = None
        self.section_name = ""
        self.gravity_loads: List[Any] = []
        self.ref_temp: Optional[float] = None
        self.strain_loads: List[Any] = []
        self.surface_pressures: List[Any] = []
        self.temp_loads: List[Any] = []
        self.uniform_loads: List[Any] = []
        self.uniform_to_frame_loads: List[Any] = []
        self.wind_pressures: List[Any] = []

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_ids": [n.unique_id for n in self.nodes],
            "thickness": self.thickness,
            "section_name": self.section_name,
            # === YENİ ===
            "gravity_loads":          [l.to_dict() for l in self.gravity_loads],
            "ref_temp":               self.ref_temp,
            "strain_loads":           [l.to_dict() for l in self.strain_loads],
            "surface_pressures":      [l.to_dict() for l in self.surface_pressures],
            "temp_loads":             [l.to_dict() for l in self.temp_loads],
            "uniform_loads":          [l.to_dict() for l in self.uniform_loads],
            "uniform_to_frame_loads": [l.to_dict() for l in self.uniform_to_frame_loads],
            "wind_pressures":         [l.to_dict() for l in self.wind_pressures],
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], nodes_map: Dict[int, Node]) -> 'Area':
        area_nodes = [nodes_map[nid] for nid in data.get("node_ids", []) if nid in nodes_map]
        area = cls(
            nodes=area_nodes,
            thickness=data.get("thickness", 0.0),
            label=data.get("label", ""),
        )
        area.section_name = data.get("section_name", "")
        area._apply_base_dict(data)
        # === YENİ ===
        area.gravity_loads          = [AreaGravityLoad.from_dict(l) for l in data.get("gravity_loads", [])]
        area.ref_temp               = data.get("ref_temp")
        area.strain_loads           = [AreaStrainLoad.from_dict(l) for l in data.get("strain_loads", [])]
        area.surface_pressures      = [AreaSurfacePressureLoad.from_dict(l) for l in data.get("surface_pressures", [])]
        area.temp_loads             = [AreaTemperatureLoad.from_dict(l) for l in data.get("temp_loads", [])]
        area.uniform_loads          = [AreaUniformLoad.from_dict(l) for l in data.get("uniform_loads", [])]
        area.uniform_to_frame_loads = [AreaUniformToFrameLoad.from_dict(l) for l in data.get("uniform_to_frame_loads", [])]
        area.wind_pressures         = [AreaWindPressureLoad.from_dict(l) for l in data.get("wind_pressures", [])]
        return area


# ============================================================================
# LINK
# ============================================================================
class Link(Element):
    def __init__(self, node_i: Node, node_j: Node, propname: str = "LINK1", label: str = "", color=None):
        if color is None:
            color = [0.5, 0.5, 0.5]
        super().__init__(label, color=color)
        self.element_type = "Link"
        self.node_i = node_i
        self.node_j = node_j
        self.propname = propname

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_i_id": self.node_i.unique_id if self.node_i else None,
            "node_j_id": self.node_j.unique_id if self.node_j else None,
            "propname": self.propname,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], nodes_map: Dict[int, Node]) -> 'Link':
        ni = nodes_map.get(data.get("node_i_id"))
        nj = nodes_map.get(data.get("node_j_id"))
        link = cls(
            node_i=ni,
            node_j=nj,
            propname=data.get("propname", "LINK1"),
            label=data.get("label", ""),
        )
        link._apply_base_dict(data)
        return link


# ============================================================================
# POLYGON
# ============================================================================
class PolygonType(Enum):
    GENERIC = auto()
    SURFACE = auto()
    ZONE = auto()
    SECTION_CUT = auto()
    LOAD_AREA = auto()


class Polygon(Element):
    def __init__(self, nodes: List[Node], label: str = "",
                 poly_type: PolygonType = PolygonType.GENERIC, color=None):
        if color is None:
            color = [0.8, 0.3, 0.8, 0.6]
        super().__init__(label, color=color)
        self.element_type = "Polygon"
        self.poly_type = poly_type
        self.nodes = list(nodes)
        self.windplane: Dict[str, Any] = {}
        self.is_temporary = False

    def is_valid(self) -> bool:
        return len(self.nodes) >= 3

    def centroid(self):
        n = len(self.nodes)
        if n == 0:
            return (0.0, 0.0, 0.0)
        return (
            sum(nd.x for nd in self.nodes) / n,
            sum(nd.y for nd in self.nodes) / n,
            sum(nd.z for nd in self.nodes) / n,
        )

    def __repr__(self):
        return f"<Polygon {self.label} nodes={len(self.nodes)} type={self.poly_type.name}>"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "node_ids": [n.unique_id for n in self.nodes],
            "poly_type": self.poly_type.name,
            "windplane": self.windplane,
            "is_temporary": self.is_temporary,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], nodes_map: Dict[int, Node]) -> 'Polygon':
        poly_nodes = [nodes_map[nid] for nid in data.get("node_ids", []) if nid in nodes_map]

        type_str = data.get("poly_type", "GENERIC")
        try:
            poly_type = PolygonType[type_str]
        except KeyError:
            poly_type = PolygonType.GENERIC

        poly = cls(nodes=poly_nodes, label=data.get("label", ""), poly_type=poly_type)
        poly.windplane = data.get("windplane", {})
        poly.is_temporary = bool(data.get("is_temporary", False))
        poly._apply_base_dict(data)
        return poly