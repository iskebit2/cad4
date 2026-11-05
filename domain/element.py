# domain/element.py
from __future__ import annotations

import math

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


class Element:
    def __init__(self, label: str = "", is_selected: bool = False,
                 is_visible: bool = True, needs_update: bool = True, color=None):
        self.unique_id = IDManager.generate_id()
        self.pick_id = self.unique_id
        self.label = label
        self.is_selected = is_selected
        self.is_visible = is_visible
        self.needs_update = needs_update
        self.element_type = None
        self.color = list(color) if color is not None else None
        self.show_axes_override: bool | None = None

    def toggle_selection(self):
        self.is_selected = not self.is_selected

    def mark_dirty(self):
        self.needs_update = True


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

    def __init__(self, x, y, z, label: str = "",
                 restraint: D.Restraint | None = None,
                 color=None):
        super().__init__(label, color=color)
        self.element_type = "Node"
        self._x, self._y, self._z = float(x), float(y), float(z)
        self.restraint = restraint
        self.dof_indices: list[int | None] = [None] * 6
        self.connected: list[tuple[E.ObjType, int]] = []
        self.loads: list[D.PointLoad] = []
        self.coord_sys = "GLOBAL"
        self.coord_type = "Cartesian"
        self.special_jt = False
        self.constraint_name: str | None = None
        self.mass_coord_sys = "Joint Local"
        for f in ("mass_1", "mass_2", "mass_3", "mmi_1", "mmi_2", "mmi_3",
                  "added_mass_1", "added_mass_2", "added_mass_3",
                  "added_mmi_1", "added_mmi_2", "added_mmi_3",
                  "spring_u1", "spring_u2", "spring_u3",
                  "spring_r1", "spring_r2", "spring_r3"):
            setattr(self, f, 0.0)
        self.load_pattern = ""

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


class Frame(Element):
    __unit_schema__ = {
        "jt_offset_i": Dimension.LENGTH, "jt_offset_j": Dimension.LENGTH,
        "offset_length_i": Dimension.LENGTH, "offset_length_j": Dimension.LENGTH,
        "mesh_max_length": Dimension.LENGTH, "max_sta_spcg": Dimension.LENGTH,
    }

    def __init__(self, node_i, node_j, section, rotation_deg=0.0, label="", color=None):
        super().__init__(label, color=color)
        self.element_type = "Frame"
        self.node_i, self.node_j = node_i, node_j
        self.section = section
        self.rotation_deg = float(rotation_deg)
        self.release_i: dict | None = None
        self.release_j: dict | None = None
        self.point_loads: list = []
        self.gravity_loads: list = []
        self.temp_loads: list = []
        self.dist_load_sets: dict[str, D.FrameDistributedLoad] = {}
        self.cardinal_pt = "10 (centroid)"
        self.mirror2 = False
        self.mirror3 = False
        self.transform = True
        self.insertion_coord_sys = "Local"
        self.jt_offset_i = (0.0, 0.0, 0.0)
        self.jt_offset_j = (0.0, 0.0, 0.0)
        self.offset_type = "User"
        self.offset_length_i = 0.0
        self.offset_length_j = 0.0
        self.rigid_factor = 0.0
        self.station_type = "MinNumSta"
        self.min_num_sta = 3
        self.add_at_elm_int = True
        self.add_at_pt_load = True
        self.max_sta_spcg: float | None = None
        self.auto_mesh = False
        self.mesh_at_joints = False
        self.mesh_at_frames = False
        self.mesh_num_segments = 0
        self.mesh_max_length = 0.0
        self.mesh_max_degrees = 0.0
        self.mirror_abt2 = False
        self.mirror_abt3 = False
        self.modifiers: dict[str, float] = {}
        self.design_proc = "From Material"
        self.load_transfer = True
        self.section_rebar: dict = {}
        self.time_dependent: dict = {}

    @property
    def dist_loads(self) -> list[D.FrameDistributedLoad]:
        return [s for ls in self.dist_load_sets.values() for s in ls.to_sap_loads()]

    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

    def get_midpoint(self):
        return ((self.node_i._x + self.node_j._x) * 0.5,
                (self.node_i._y + self.node_j._y) * 0.5,
                (self.node_i._z + self.node_j._z) * 0.5)

    def get_axis(self):
        d = (self.node_j._x - self.node_i._x,
             self.node_j._y - self.node_i._y,
             self.node_j._z - self.node_i._z)
        L = math.sqrt(sum(c * c for c in d))
        return (1.0, 0.0, 0.0) if L < 1e-9 else tuple(c / L for c in d)

    def get_local_axes(self) -> glm.mat3:
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


class Area(Element):
    __unit_schema__ = {
        "thick_over": Dimension.LENGTH,
        "offset_over": Dimension.LENGTH,
    }

    def __init__(self, nodes, thickness, label="", color=None):
        super().__init__(label, color)
        self.element_type = "Area"
        self.nodes = list(nodes)
        self.__dict__["thickness"] = float(thickness)
        self.material = None
        self.section_name = ""
        self.area_section: D.AreaSection | None = None
        self.mat_prop = ""
        self.thick_over: float | None = None
        self.offset_over: float | None = None
        self.gravity_loads: list = []
        self.ref_temp: float | None = None
        self.strain_loads: list = []
        self.surface_pressures: list = []
        self.temp_loads: list = []
        self.uniform_loads: list = []
        self.uniform_to_frame_loads: list = []
        self.wind_pressures: list = []

    @property
    def thickness(self) -> float:
        if self.thick_over is not None:
            return self.thick_over
        if self.area_section is not None and self.area_section.thickness is not None:
            return float(self.area_section.thickness)
        return float(self.__dict__.get("thickness", 0.0))

    @thickness.setter
    def thickness(self, value):
        if self.area_section is not None:
            self.thick_over = float(value)
        else:
            self.__dict__["thickness"] = float(value)

    @property
    def section(self):
        return self.area_section

    @property
    def effective_bend_thick(self) -> float:
        if self.area_section is not None:
            return float(self.area_section.effective_bend_thick)
        return self.thickness


class Link(Element):
    def __init__(self, node_i, node_j, propname="LINK1", label="", color=None):
        super().__init__(label, color)
        self.element_type = "Link"
        self.node_i, self.node_j = node_i, node_j
        self.propname = propname