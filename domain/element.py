# domain/element.py
from __future__ import annotations
import math
from dataclasses import dataclass, field
from pyglm import glm
from core.id_manager import IDManager
from core.units import Dimension
from data import enums as E
from domain import definition as D

def id_to_color(obj_id: int) -> tuple[float, float, float]:
    return (
        ((obj_id >> 0) & 0xFF) / 255.0,
        ((obj_id >> 8) & 0xFF) / 255.0,
        ((obj_id >> 16) & 0xFF) / 255.0,
    )

def color_to_id(r, g, b) -> int:
    return int(r) + (int(g) << 8) + (int(b) << 16)

@dataclass
class Element:
    label: str = ""
    is_selected: bool = False
    is_visible: bool = True
    needs_update: bool = True
    color: list | None = None
    show_axes_override: bool | None = None
    unique_id: int = field(default_factory=IDManager.generate_id)
    pick_id: int = 0
    element_type: str = "Element"

    def __post_init__(self):
        if self.pick_id == 0:
            self.pick_id = self.unique_id

    def toggle_selection(self) -> None:
        self.is_selected = not self.is_selected

    def mark_dirty(self) -> None:
        self.needs_update = True


@dataclass
class Node(Element):
    DOF_ORDER = ("ux", "uy", "uz", "rx", "ry", "rz")

    __unit_schema__ = {
        "_x": Dimension.LENGTH, "_y": Dimension.LENGTH, "_z": Dimension.LENGTH,
        "mass_1": Dimension.MASS, "mass_2": Dimension.MASS, "mass_3": Dimension.MASS,
        "mmi_1": Dimension.MASS_INERTIA, "mmi_2": Dimension.MASS_INERTIA, "mmi_3": Dimension.MASS_INERTIA,
        "added_mass_1": Dimension.MASS, "added_mass_2": Dimension.MASS, "added_mass_3": Dimension.MASS,
        "added_mmi_1": Dimension.MASS_INERTIA, "added_mmi_2": Dimension.MASS_INERTIA, "added_mmi_3": Dimension.MASS_INERTIA,
        "spring_u1": Dimension.FORCE, "spring_u2": Dimension.FORCE, "spring_u3": Dimension.FORCE,
        "spring_r1": Dimension.MOMENT, "spring_r2": Dimension.MOMENT, "spring_r3": Dimension.MOMENT,
    }

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    restraint: D.Restraint | None = None
    dof_indices: list[int | None] = field(default_factory=lambda: [None] * 6)
    connected: list[tuple[E.ObjType, int]] = field(default_factory=list)
    loads: list[D.PointLoad] = field(default_factory=list)
    coord_sys: str = "GLOBAL"
    coord_type: str = "Cartesian"
    special_jt: bool = False
    constraint_name: str | None = None
    mass_coord_sys: str = "Joint Local"
    load_pattern: str = ""
    
    mass_1: float = 0.0
    mass_2: float = 0.0
    mass_3: float = 0.0
    mmi_1: float = 0.0
    mmi_2: float = 0.0
    mmi_3: float = 0.0
    added_mass_1: float = 0.0
    added_mass_2: float = 0.0
    added_mass_3: float = 0.0
    added_mmi_1: float = 0.0
    added_mmi_2: float = 0.0
    added_mmi_3: float = 0.0
    spring_u1: float = 0.0
    spring_u2: float = 0.0
    spring_u3: float = 0.0
    spring_r1: float = 0.0
    spring_r2: float = 0.0
    spring_r3: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        self.element_type = "Node"
        self._x, self._y, self._z = float(self.x), float(self.y), float(self.z)

    @property
    def x(self): return self._x
    @x.setter
    def x(self, v): self._x = float(v); self.mark_dirty()

    @property
    def y(self): return self._y
    @y.setter
    def y(self, v): self._y = float(v); self.mark_dirty()

    @property
    def z(self): return self._z
    @z.setter
    def z(self, v): self._z = float(v); self.mark_dirty()

    @property
    def coords(self): return (self._x, self._y, self._z)

    def set_coords(self, x, y, z):
        self._x, self._y, self._z = float(x), float(y), float(z)
        self.mark_dirty()

    def distance_to(self, other: "Node") -> float:
        return math.dist(self.coords, other.coords)

    def is_restrained(self): return self.restraint is not None

    def is_free(self): return self.restraint is None or self.restraint.is_free()

    def has_any_restraint(self):
        return self.restraint is not None and not self.restraint.is_free()

    def enumerate_dofs(self, start_index: int) -> int:
        current = start_index
        for i, name in enumerate(self.DOF_ORDER):
            restrained = getattr(self.restraint, name, False) if self.restraint else False
            if restrained:
                self.dof_indices[i] = None
            else:
                self.dof_indices[i] = current
                current += 1
        return current

    def get_dof_index(self, name: str):
        return self.dof_indices[self.DOF_ORDER.index(name)]

    def add_connection(self, element):
        t = {"Frame": E.ObjType.FRAME, "Area": E.ObjType.AREA, "Link": E.ObjType.LINK}.get(element.element_type)
        if t is not None:
            self.connected.append((t, element.unique_id))

    @property
    def total_mass(self):
        return tuple(
            getattr(self, f"mass_{i}") + getattr(self, f"added_mass_{i}")
            for i in (1, 2, 3)
        ) + tuple(
            getattr(self, f"mmi_{i}") + getattr(self, f"added_mmi_{i}")
            for i in (1, 2, 3)
        )

    def has_mass(self) -> bool:
        return any(abs(v) > 1e-12 for v in self.total_mass)


@dataclass
class Frame(Element):
    __unit_schema__ = {
        "jt_offset_i": Dimension.LENGTH, "jt_offset_j": Dimension.LENGTH,
        "offset_length_i": Dimension.LENGTH, "offset_length_j": Dimension.LENGTH,
        "mesh_max_length": Dimension.LENGTH, "max_sta_spcg": Dimension.LENGTH,
    }

    node_i: Node | None = None
    node_j: Node | None = None
    section: any = None
    rotation_deg: float = 0.0
    
    release_i: dict | None = None
    release_j: dict | None = None
    point_loads: list = field(default_factory=list)
    gravity_loads: list = field(default_factory=list)
    temp_loads: list = field(default_factory=list)
    dist_load_sets: dict[str, D.FrameDistributedLoad] = field(default_factory=dict)
    
    cardinal_pt: str = "10 (centroid)"
    mirror2: bool = False
    mirror3: bool = False
    transform: bool = True
    insertion_coord_sys: str = "Local"
    jt_offset_i: tuple[float, float, float] = (0.0, 0.0, 0.0)
    jt_offset_j: tuple[float, float, float] = (0.0, 0.0, 0.0)
    offset_type: str = "User"
    offset_length_i: float = 0.0
    offset_length_j: float = 0.0
    rigid_factor: float = 0.0
    station_type: str = "MinNumSta"
    min_num_sta: int = 3
    add_at_elm_int: bool = True
    add_at_pt_load: bool = True
    max_sta_spcg: float | None = None
    auto_mesh: bool = False
    mesh_at_joints: bool = False
    mesh_at_frames: bool = False
    mesh_num_segments: int = 0
    mesh_max_length: float = 0.0
    mesh_max_degrees: float = 0.0
    mirror_abt2: bool = False
    mirror_abt3: bool = False
    modifiers: dict[str, float] = field(default_factory=dict)
    design_proc: str = "From Material"
    load_transfer: bool = True
    section_rebar: dict = field(default_factory=dict)
    time_dependent: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        self.element_type = "Frame"
        self.rotation_deg = float(self.rotation_deg)

    @property
    def dist_loads(self) -> list[D.FrameDistributedLoad]:
        return [s for ls in self.dist_load_sets.values() for s in ls.to_sap_loads()]

    def get_length(self) -> float:
        if not self.node_i or not self.node_j:
            return 0.0
        return self.node_i.distance_to(self.node_j)

    def get_midpoint(self):
        if not self.node_i or not self.node_j:
            return (0.0, 0.0, 0.0)
        return ((self.node_i._x + self.node_j._x) * 0.5,
                (self.node_i._y + self.node_j._y) * 0.5,
                (self.node_i._z + self.node_j._z) * 0.5)

    def get_axis(self):
        if not self.node_i or not self.node_j:
            return (1.0, 0.0, 0.0)
        d = (self.node_j._x - self.node_i._x,
             self.node_j._y - self.node_i._y,
             self.node_j._z - self.node_i._z)
        L = math.sqrt(sum(c * c for c in d))
        return (1.0, 0.0, 0.0) if L < 1e-9 else tuple(c / L for c in d)

    def get_local_axes(self) -> glm.mat3:
        if not self.node_i or not self.node_j:
            return glm.mat3(1.0)
        dx = self.node_j._x - self.node_i._x
        dy = self.node_j._y - self.node_i._y
        dz = self.node_j._z - self.node_i._z
        L = math.sqrt(dx * dx + dy * dy + dz * dz)
        if L < 1e-9:
            return glm.mat3(1.0)
        e1 = glm.vec3(dx / L, dy / L, dz / L)
        ref = glm.vec3(0, 0, 1) if abs(e1.z) < 0.9999 else glm.vec3(1, 0, 0)
        e2 = glm.normalize(ref - e1 * glm.dot(ref, e1))
        e3 = glm.cross(e1, e2)
        if abs(self.rotation_deg) > 1e-9:
            a = math.radians(self.rotation_deg)
            ca, sa = math.cos(a), math.sin(a)
            e2, e3 = glm.normalize(e2 * ca + e3 * sa), glm.normalize(-e2 * sa + e3 * ca)
        return glm.mat3(e1, e2, e3)


@dataclass
class Area(Element):
    __unit_schema__ = {
        "thick_over": Dimension.LENGTH,
        "offset_over": Dimension.LENGTH,
    }

    nodes: list = field(default_factory=list)
    _thickness_val: float = 0.0
    material: any = None
    section_name: str = ""
    area_section: D.AreaSection | None = None
    mat_prop: str = ""
    thick_over: float | None = None
    offset_over: float | None = None
    gravity_loads: list = field(default_factory=list)
    ref_temp: float | None = None
    strain_loads: list = field(default_factory=list)
    surface_pressures: list = field(default_factory=list)
    temp_loads: list = field(default_factory=list)
    uniform_loads: list = field(default_factory=list)
    uniform_to_frame_loads: list = field(default_factory=list)
    wind_pressures: list = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.element_type = "Area"
        self.nodes = list(self.nodes)
        # self._thickness_val = float(self.thickness)

    @property
    def thickness(self) -> float:
        if self.thick_over is not None:
            return self.thick_over
        if self.area_section is not None and self.area_section.thickness is not None:
            return float(self.area_section.thickness)
        return self._thickness_val

    @thickness.setter
    def thickness(self, value):
        if self.area_section is not None:
            self.thick_over = float(value)
        else:
            self._thickness_val = float(value)

    @property
    def section(self):
        return self.area_section

    @property
    def effective_bend_thick(self) -> float:
        if self.area_section is not None:
            return float(self.area_section.effective_bend_thick)
        return self.thickness


@dataclass
class Link(Element):
    node_i: Node | None = None
    node_j: Node | None = None
    propname: str = "LINK1"

    def __post_init__(self):
        super().__post_init__()
        self.element_type = "Link"