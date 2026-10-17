# domain/element.py
from dataclasses import field
from typing import List, Optional, Dict, Any, Tuple
import uuid
import math
import glm

from domain import definition as D
from data import enums as E

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
        self.show_axes_override: Optional[bool] = None  # None → scene default

    def toggle_selection(self):
        self.is_selected = not self.is_selected

    def mark_dirty(self):
        self.needs_update = True

    def _apply_base_dict(self, data: Dict[str, Any]):
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
        restraint: Optional[D.Restraint] = None,
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
        self.connected: List[Tuple[E.ObjType, str]] = []
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
            self.connected.append((E.ObjType.FRAME, element.element_id))
        elif isinstance(element, Area):
            self.connected.append((E.ObjType.AREA, element.element_id))
        elif isinstance(element, Link):
            self.connected.append((E.ObjType.LINK, element.element_id))


# ============================================================================
# FRAME (Yerel Eksen ve Matris Hesaplamaları Dahil)
# ============================================================================
class Frame(Element):
    def __init__(self, node_i: Node, node_j: Node, section: D.Section,
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
        self.dist_load_sets: Dict[str, D.FrameDistributedLoadSet] = {}

    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

    def get_midpoint(self):
        return (
            (self.node_i.x + self.node_j.x) * 0.5,
            (self.node_i.y + self.node_j.y) * 0.5,
            (self.node_i.z + self.node_j.z) * 0.5,
        )

    def get_axis(self):
        dx = self.node_j.x - self.node_i.x
        dy = self.node_j.y - self.node_i.y
        dz = self.node_j.z - self.node_i.z
        length = (dx*dx + dy*dy + dz*dz) ** 0.5
        if length < 1e-9:
            return (1.0, 0.0, 0.0)
        return (dx / length, dy / length, dz / length)

    def get_local_axes(self) -> glm.mat3:
        """
        Frame için 3x3 dönüşüm matrisi döner (global → local).
        SAP2000 konvansiyonu:
          - 1-ekseni: i → j yönü
          - 2-ekseni: başlangıçta global Z'ye dik, XY düzleminde
          - 3-ekseni: sağ el kuralı (cross product)
          - rotation_deg: 1-eksen etrafında saat yönü tersi dönme
        """
        dx = self.node_j.x - self.node_i.x
        dy = self.node_j.y - self.node_i.y
        dz = self.node_j.z - self.node_i.z
        L = math.sqrt(dx*dx + dy*dy + dz*dz)
        if L < 1e-9:
            return glm.mat3(1.0)
        e1 = glm.vec3(dx/L, dy/L, dz/L)
        
        ref = glm.vec3(0, 0, 1) if abs(e1.z) < 0.9999 else glm.vec3(1, 0, 0)
        e2 = glm.normalize(ref - e1 * glm.dot(ref, e1))
        e3 = glm.cross(e1, e2)
        
        if abs(self.rotation_deg) > 1e-9:
            a = math.radians(self.rotation_deg)
            ca, sa = math.cos(a), math.sin(a)
            e2_new = e2 * ca + e3 * sa
            e3_new = -e2 * sa + e3 * ca
            e2, e3 = glm.normalize(e2_new), glm.normalize(e3_new)
        
        return glm.mat3(e1, e2, e3)

    def align_to_polygon_plane(self, polygon_nodes):
        """
        Frame'in Local 2 eksenini poligon normaline hizalar.
        Böylece LOAD_DIR='2' yükü düzleme dik olur.
        """
        if len(polygon_nodes) < 3:
            return 0.0

        _, _, n_poly = Polygon.calculate_plane_axes(polygon_nodes)
        e1 = glm.vec3(*self.get_axis())
        L = glm.length(e1)
        if L < 1e-9:
            return 0.0
        e1 = e1 / L

        if abs(glm.dot(e1, n_poly)) > 0.999:
            return 0.0

        # Doğal e2 (rotation_deg=0 için)
        R0 = Frame(self.node_i, self.node_j, self.section, rotation_deg=0.0).get_local_axes()
        e2_natural = glm.vec3(R0[1][0], R0[1][1], R0[1][2])

        # e2'yi n_poly'ye hizala
        dot = max(-1.0, min(1.0, glm.dot(e2_natural, n_poly)))
        angle_rad = math.acos(dot)
        cross = glm.cross(e2_natural, n_poly)
        sign = 1.0 if glm.dot(cross, e1) >= 0.0 else -1.0

        angle_deg = math.degrees(angle_rad) * sign
        while angle_deg > 180.0: angle_deg -= 360.0
        while angle_deg < -180.0: angle_deg += 360.0

        self.rotation_deg = angle_deg
        self.mark_dirty()
        return angle_deg


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


# ============================================================================
# POLYGON (Düzlem, Normal ve Yön Sınıflandırma Metotları Dahil)
# ============================================================================

class Polygon(Element):
    def __init__(self, nodes: List[Node], label: str = "",
                 poly_type: E.PolygonType = E.PolygonType.GENERIC, color=None):
        if color is None:
            color = [0.8, 0.3, 0.8, 0.6]
        super().__init__(label, color=color)
        self.element_type = "Polygon"
        self.poly_type = poly_type
        self.nodes = list(nodes)
        self.windplane: Dict[str, Any] = {}
        self.is_temporary = False
        self.uniform_to_frame_loads: List[Any] = []
        associated_frame_ids: List[int] = field(default_factory=list)

    def is_valid(self) -> bool:
        return len(self.nodes) >= 3

    def centroid(self) -> Tuple[float, float, float]:
        n = len(self.nodes)
        if n == 0:
            return (0.0, 0.0, 0.0)
        return (
            sum(nd.x for nd in self.nodes) / n,
            sum(nd.y for nd in self.nodes) / n,
            sum(nd.z for nd in self.nodes) / n,
        )

    @staticmethod
    def calculate_normal(nodes: List[Node], use_newell: bool = True) -> glm.vec3:
        """Newell metodu ile polygon normal vektörü."""
        n = glm.vec3(0, 0, 0)
        if use_newell:
            N = len(nodes)
            for i in range(N):
                a = nodes[i]
                b = nodes[(i + 1) % N]
                n.x += (a.y - b.y) * (a.z + b.z)
                n.y += (a.z - b.z) * (a.x + b.x)
                n.z += (a.x - b.x) * (a.y + b.y)
        else:
            if len(nodes) < 3: return glm.vec3(0, 0, 1)
            v1 = glm.vec3(nodes[1].x-nodes[0].x, nodes[1].y-nodes[0].y, nodes[1].z-nodes[0].z)
            v2 = glm.vec3(nodes[2].x-nodes[0].x, nodes[2].y-nodes[0].y, nodes[2].z-nodes[0].z)
            n = glm.cross(v1, v2)
        L = glm.length(n)
        return n / L if L > 1e-9 else glm.vec3(0, 0, 1)

    @staticmethod
    def calculate_plane_axes(nodes: List[Node]) -> Tuple[glm.vec3, glm.vec3, glm.vec3]:
        """Polygon düzlemi için (e_u, e_v, n) ortonormal frame."""
        N = Polygon.calculate_normal(nodes)
        u = glm.vec3(nodes[1].x-nodes[0].x, nodes[1].y-nodes[0].y, nodes[1].z-nodes[0].z)
        u = u - N * glm.dot(u, N)
        if glm.length(u) < 1e-6:
            u = glm.vec3(1, 0, 0) - N * N.x
        u = glm.normalize(u)
        v = glm.normalize(glm.cross(N, u))
        return u, v, N

    def get_plane_frame(self):
        """Polygon düzlem eksenlerini (origin, u, v, n) olarak döner."""
        if len(self.nodes) < 3:
            return glm.vec3(0), glm.vec3(1, 0, 0), glm.vec3(0, 1, 0), glm.vec3(0, 0, 1)
        u, v, n = self.calculate_plane_axes(self.nodes)
        cx, cy, cz = self.centroid()
        return glm.vec3(cx, cy, cz), u, v, n

    def classify_load_direction(self, load_dir_enum: E.LoadDirection, cos_threshold: float = 0.85):
        """Poligon yükünün yönünü sınıflandırır."""
        u, v_ax, n = self.calculate_plane_axes(self.nodes)

        if load_dir_enum == E.LoadDirection.GLOBAL_X: world_v = glm.vec3(1, 0, 0)
        elif load_dir_enum == E.LoadDirection.GLOBAL_Y: world_v = glm.vec3(0, 1, 0)
        elif load_dir_enum == E.LoadDirection.GLOBAL_Z: world_v = glm.vec3(0, 0, 1)
        elif load_dir_enum == E.LoadDirection.GRAVITY: world_v = glm.vec3(0, 0, -1)
        elif load_dir_enum == E.LoadDirection.LOCAL_1: world_v = u
        elif load_dir_enum == E.LoadDirection.LOCAL_2: world_v = v_ax
        elif load_dir_enum == E.LoadDirection.LOCAL_3: world_v = n
        elif load_dir_enum == E.LoadDirection.PROJECTED_X: world_v = glm.vec3(1, 0, 0)
        elif load_dir_enum == E.LoadDirection.PROJECTED_Y: world_v = glm.vec3(0, 1, 0)
        elif load_dir_enum == E.LoadDirection.PROJECTED_Z: world_v = glm.vec3(0, 0, 1)
        else: return "UNKNOWN", glm.vec3(0, 0, -1)

        vec = glm.normalize(world_v) if glm.length(world_v) > 1e-9 else world_v

        dots = {
            "NORMAL": abs(glm.dot(vec, n)),
            "U":      abs(glm.dot(vec, u)),
            "V":      abs(glm.dot(vec, v_ax)),
        }
        best = max(dots, key=dots.get)
        if dots[best] >= cos_threshold:
            return best, vec

        world_dots = {
            "GX": abs(vec.x),
            "GY": abs(vec.y),
            "GZ": abs(vec.z),
            "GRAV": abs(-vec.z),
        }
        best_w = max(world_dots, key=world_dots.get)
        if world_dots[best_w] >= cos_threshold:
            return best_w, vec

        return "UNKNOWN", vec

    def add_uniform_to_frame_load(self, pattern_name: str, value: float, direction=None, dist_type=None):
        from domain.definition import AreaUniformToFrameLoad, DistType
        if direction is None:
            direction = E.LoadDirection.GRAVITY
        if dist_type is None:
            dist_type = DistType.ONE_WAY

        load_item = AreaUniformToFrameLoad(
            pattern_name=pattern_name.strip(),
            direction=direction,
            value=value,
            dist_type=dist_type,
            coordinate_system="GLOBAL"
        )
        self.uniform_to_frame_loads.append(load_item)
        self.mark_dirty()


# ============================================================================
# GENEL GEOMETRİ YARDIMCILARI (Bağımsız Fonksiyonlar)
# ============================================================================
def project_point_to_plane(point, plane_origin, plane_normal):
    p = glm.vec3(*point) if not isinstance(point, glm.vec3) else point
    diff = p - plane_origin
    d = glm.dot(diff, plane_normal)
    proj = p - plane_normal * d
    return proj, d


def point_to_segment_distance_3d(p, a, b):
    pa = glm.vec3(*a) if not isinstance(a, glm.vec3) else a
    pb = glm.vec3(*b) if not isinstance(b, glm.vec3) else b
    pp = glm.vec3(*p) if not isinstance(p, glm.vec3) else p

    ab = pb - pa
    L2 = glm.dot(ab, ab)
    if L2 < 1e-12:
        return glm.length(pp - pa)
    t = glm.dot(pp - pa, ab) / L2
    t = max(0.0, min(1.0, t))
    proj = pa + ab * t
    return glm.length(pp - proj)