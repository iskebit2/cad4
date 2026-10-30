# domain/element.py
"""Domain elementleri — Node, Frame, Area, Link, Polygon.

Birim sözleşmesi: model her zaman project.unit_system'de.
convert_project_units __unit_schema__ ile dönüştürür.
Node _x/_y/_z private — __dict__ doğrudan — mark_dirty yok.
"""
from __future__ import annotations

import math
from typing import Any

from pyglm import glm

from core.units import Dimension
from data import enums as E
from domain import definition as D
from logging_config import CadLogger

logger = CadLogger.get(__name__)


def id_to_color(obj_id: int) -> tuple[float, float, float]:
    return (
        ((obj_id >> 0) & 0xFF) / 255.0,
        ((obj_id >> 8) & 0xFF) / 255.0,
        ((obj_id >> 16) & 0xFF) / 255.0,
    )


def color_to_id(r: int, g: int, b: int) -> int:
    return int(r) + (int(g) << 8) + (int(b) << 16)


# ============================================================================
# ELEMENT BASE
# ============================================================================
class Element:
    _id_counter = 1

    def __init__(self, label: str = "", is_selected: bool = False,
                 is_visible: bool = True, needs_update: bool = True, color=None):
        self.unique_id = Element._id_counter
        Element._id_counter += 1
        self.label = label
        self.is_selected = is_selected
        self.is_visible = is_visible
        self.needs_update = needs_update
        self.pick_id = self.unique_id
        self.element_type = None
        self.color = list(color) if color is not None else None
        self.show_axes_override: bool | None = None

    def toggle_selection(self):
        self.is_selected = not self.is_selected

    def mark_dirty(self):
        self.needs_update = True

    def _apply_base_dict(self, data: dict[str, Any]):
        if "unique_id" in data:
            self.unique_id = int(data["unique_id"])
            Element._id_counter = max(Element._id_counter, self.unique_id + 1)
            self.pick_id = self.unique_id
        self.is_selected = bool(data.get("is_selected", False))
        self.is_visible = bool(data.get("is_visible", True))
        if data.get("color"):
            self.color = list(data["color"])


# ============================================================================
# NODE
# ============================================================================
class Node(Element):
    DOF_ORDER = ("ux", "uy", "uz", "rx", "ry", "rz")

    __unit_schema__ = {
        "_x": Dimension.LENGTH,
        "_y": Dimension.LENGTH,
        "_z": Dimension.LENGTH,
        # JOINT ADDED MASS — ilk 3 MASS, son 3 MASS_INERTIA
        "mass_1": Dimension.MASS,
        "mass_2": Dimension.MASS,
        "mass_3": Dimension.MASS,
        "mmi_1": Dimension.MASS_INERTIA,
        "mmi_2": Dimension.MASS_INERTIA,
        "mmi_3": Dimension.MASS_INERTIA,
        "added_mass_1": Dimension.MASS,
        "added_mass_2": Dimension.MASS,
        "added_mass_3": Dimension.MASS,
        "added_mmi_1": Dimension.MASS_INERTIA,
        "added_mmi_2": Dimension.MASS_INERTIA,
        "added_mmi_3": Dimension.MASS_INERTIA,
        "spring.0": Dimension.FORCE,
        "spring.1": Dimension.FORCE,
        "spring.2": Dimension.FORCE,
        "spring.3": Dimension.MOMENT,
        "spring.4": Dimension.MOMENT,
        "spring.5": Dimension.MOMENT,
    }

    def __init__(self, x: float, y: float, z: float, label: str = "",
                 restraint: D.Restraint | None = None,
                 spring: tuple[float, ...] = (), color=None):
        super().__init__(label, color=color)
        self.element_type = "Node"
        self._x = float(x)
        self._y = float(y)
        self._z = float(z)
        self.restraint = restraint
        # self.spring = tuple(spring)
        self.dof_indices: list[int | None] = [None] * 6
        self.connected: list[tuple[E.ObjType, str]] = []
        self.loads: list[D.PointLoad] = []

        # --- JOINT COORDINATES ---
        self.coord_sys: str = "GLOBAL"
        self.coord_type: str = "Cartesian"
        self.special_jt: bool = False

        # --- JOINT CONSTRAINT ASSIGNMENTS ---
        self.constraint_name: str | None = None

        # --- JOINT ADDED MASS ASSIGNMENTS ---
        self.mass_coord_sys: str = "Joint Local"
        self.mass_1: float = 0.0
        self.mass_2: float = 0.0
        self.mass_3: float = 0.0
        self.mmi_1: float = 0.0
        self.mmi_2: float = 0.0
        self.mmi_3: float = 0.0

        self.added_mass_1: float = 0.0
        self.added_mass_2: float = 0.0
        self.added_mass_3: float = 0.0
        self.added_mmi_1: float = 0.0
        self.added_mmi_2: float = 0.0
        self.added_mmi_3: float = 0.0

        self.spring_u1: float = 0.0
        self.spring_u2: float = 0.0
        self.spring_u3: float = 0.0
        self.spring_r1: float = 0.0
        self.spring_r2: float = 0.0
        self.spring_r3: float = 0.0

        # --- JOINT PATTERN (v10) ---
        self.load_pattern: str = ""

    # ---- x/y/z property (değişmedi) ----
    @property
    def x(self) -> float: return self._x

    @x.setter
    def x(self, v):
        self._x = float(v)
        self.mark_dirty()

    @property
    def y(self) -> float: return self._y

    @y.setter
    def y(self, v):
        self._y = float(v)
        self.mark_dirty()

    @property
    def z(self) -> float: return self._z

    @z.setter
    def z(self, v):
        self._z = float(v)
        self.mark_dirty()

    @property
    def coords(self): return (self._x, self._y, self._z)

    def set_coords(self, x, y, z):
        self._x, self._y, self._z = float(x), float(y), float(z)
        self.mark_dirty()

    def distance_to(self, other: Node) -> float:
        dx, dy, dz = self._x - other._x, self._y - other._y, self._z - other._z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def is_restrained(self) -> bool: return self.restraint is not None

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

    def get_dof_index(self, dof_name: str) -> int | None:
        return self.dof_indices[self.DOF_ORDER.index(dof_name)]

    def add_connection(self, element):
        if isinstance(element, Frame):
            self.connected.append((E.ObjType.FRAME, element.unique_id))
        elif isinstance(element, Area):
            self.connected.append((E.ObjType.AREA, element.unique_id))
        elif isinstance(element, Link):
            self.connected.append((E.ObjType.LINK, element.unique_id))

    # ---- kütle yardımcıları ----
    @property
    def total_mass(self) -> tuple[float, float, float, float, float, float]:
        """(Mass1, Mass2, Mass3, MMI1, MMI2, MMI3) = mass + added_mass."""
        return (
            self.mass_1 + self.added_mass_1,
            self.mass_2 + self.added_mass_2,
            self.mass_3 + self.added_mass_3,
            self.mmi_1 + self.added_mmi_1,
            self.mmi_2 + self.added_mmi_2,
            self.mmi_3 + self.added_mmi_3,
        )

    def has_mass(self) -> bool:
        return any(
            abs(v) > 1e-12
            for v in (
                self.mass_1, self.mass_2, self.mass_3,
                self.mmi_1, self.mmi_2, self.mmi_3,
                self.added_mass_1, self.added_mass_2, self.added_mass_3,
                self.added_mmi_1, self.added_mmi_2, self.added_mmi_3,
            )
        )


# ============================================================================
# FRAME
# ============================================================================
# domain/element.py  — Frame bölümünü bununla değiştir

class Frame(Element):
    """S2K frame — geometri + section + tüm atama tabloları.

    Birim sözleşmesi: model her zaman project.unit_system'de.
    __unit_schema__ convert_project_units tarafından kullanılır.
    """

    __unit_schema__ = {
        # --- geometri ---
        "rotation_deg": None,          # açı — boyutsuz
        # --- insertion point offsets (FRAME INSERTION POINT ASSIGNMENTS) ---
        "jt_offset_i": Dimension.LENGTH,   # tuple → her bileşen LENGTH
        "jt_offset_j": Dimension.LENGTH,
        # --- end offsets (FRAME OFFSET ALONG LENGTH ASSIGNMENTS) ---
        "offset_length_i": Dimension.LENGTH,
        "offset_length_j": Dimension.LENGTH,
        "rigid_factor": None,              # boyutsuz
        # --- auto mesh (FRAME AUTO MESH / AUTO SUBDIVISION) ---
        "mesh_max_length": Dimension.LENGTH,
        "mesh_max_degrees": None,          # açı — boyutsuz
        # --- output stations ---
        "max_sta_spcg": Dimension.LENGTH,
        # --- modifiers (boyutsuz) ---
        # modifiers dict içindeki değerler boyutsuz — schema gerekmez
        # --- rebar / cover (FRAME SECTION PROPERTIES 02/03) ---
        # section_rebar dict — LENGTH alanları var ama dict; manuel işlenir
    }

    def __init__(self, node_i, node_j, section, rotation_deg=0.0, label="", color=None):
        super().__init__(label, color=color)
        self.element_type = "Frame"
        self.node_i = node_i
        self.node_j = node_j
        self.section = section
        self.rotation_deg = float(rotation_deg)

        # --- end releases (FRAME END RELEASE ASSIGNMENTS) ---
        # {"i": {"PI":bool,"V2I":bool,...}, "j": {...}} veya None
        self.release_i: dict | None = None
        self.release_j: dict | None = None

        # --- yükler ---
        self.point_loads: list[Any] = []
        
        self.gravity_loads: list[Any] = []
        self.temp_loads: list[Any] = []
        self.dist_load_sets: dict[str, D.FrameDistributedLoad] = {}

        # ============================================================
        # FRAME INSERTION POINT ASSIGNMENTS
        # ============================================================
        self.cardinal_pt: str = "10 (centroid)"
        self.mirror2: bool = False
        self.mirror3: bool = False
        self.transform: bool = True
        self.insertion_coord_sys: str = "Local"
        self.jt_offset_i: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.jt_offset_j: tuple[float, float, float] = (0.0, 0.0, 0.0)

        # ============================================================
        # FRAME OFFSET ALONG LENGTH ASSIGNMENTS
        # ============================================================
        self.offset_type: str = "User"       # User / Auto
        self.offset_length_i: float = 0.0
        self.offset_length_j: float = 0.0
        self.rigid_factor: float = 0.0

        # ============================================================
        # FRAME OUTPUT STATION ASSIGNMENTS
        # ============================================================
        self.station_type: str = "MinNumSta"
        self.min_num_sta: int = 3
        self.add_at_elm_int: bool = True
        self.add_at_pt_load: bool = True
        self.max_sta_spcg: float | None = None

        # ============================================================
        # FRAME AUTO MESH / AUTO SUBDIVISION ASSIGNMENTS
        # ============================================================
        self.auto_mesh: bool = False
        self.mesh_at_joints: bool = False
        self.mesh_at_frames: bool = False
        self.mesh_num_segments: int = 0
        self.mesh_max_length: float = 0.0
        self.mesh_max_degrees: float = 0.0

        # ============================================================
        # FRAME LOCAL AXES ASSIGNMENTS (v10 ek: mirror abt 2/3)
        # ============================================================
        self.mirror_abt2: bool = False
        self.mirror_abt3: bool = False

        # ============================================================
        # FRAME MODIFIERS  (amod, as2mod, as3mod, jmod, i22mod, i33mod, massmod, weightmod)
        # ============================================================
        self.modifiers: dict[str, float] = {}

        # ============================================================
        # FRAME DESIGN PROCEDURES / LOAD TRANSFER
        # ============================================================
        self.design_proc: str = "From Material"
        self.load_transfer: bool = True

        # ============================================================
        # FRAME SECTION PROPERTIES 02/03/13  (betonarme)
        # ============================================================
        # column: rebar_mat_l, rebar_mat_c, reinf_config, lat_reinf, cover,
        #         num_bars3_dir, num_bars2_dir, bar_size_l, bar_size_c,
        #         spacing_c, num_cbars2, num_cbars3, reinf_type
        # beam:   top_cover, bot_cover, top_left_area, top_rght_area,
        #         bot_left_area, bot_rght_area
        self.section_rebar: dict[str, Any] = {}
        # FRAME SECTION PROPERTIES 13 - TIME DEPENDENT
        self.time_dependent: dict[str, Any] = {}   # {"type_size": "Auto", "auto_sf_size": 1.0}

    @property
    def dist_loads(self) -> list[D.FrameDistributedLoad]:
        """Türetilmiş görünüm — dist_load_sets'ten her erişimde."""
        out: list[D.FrameDistributedLoad] = []
        for load_set in self.dist_load_sets.values():
            out.extend(load_set.to_sap_loads())
        return out
    
    # ----------------------------------------------------------------
    # mevcut yardımcılar (değişmedi)
    # ----------------------------------------------------------------
    def get_length(self) -> float:
        return self.node_i.distance_to(self.node_j)

    def get_midpoint(self):
        return (
            (self.node_i._x + self.node_j._x) * 0.5,
            (self.node_i._y + self.node_j._y) * 0.5,
            (self.node_i._z + self.node_j._z) * 0.5,
        )

    def get_axis(self):
        dx = self.node_j._x - self.node_i._x
        dy = self.node_j._y - self.node_i._y
        dz = self.node_j._z - self.node_i._z
        L = (dx * dx + dy * dy + dz * dz) ** 0.5
        if L < 1e-9:
            return (1.0, 0.0, 0.0)
        return (dx / L, dy / L, dz / L)

    def get_local_axes(self) -> glm.mat3:
        """SAP2000 konvansiyonu."""
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

    def align_to_polygon_plane(self, polygon_nodes) -> float:
        """Local 2 eksenini polygon normaline hizala."""
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
        R0 = Frame(self.node_i, self.node_j, self.section, rotation_deg=0.0).get_local_axes()
        e2_natural = glm.vec3(R0[1][0], R0[1][1], R0[1][2])
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
    __unit_schema__ = {
        "thick_over": Dimension.LENGTH,
        "offset_over": Dimension.LENGTH,
    }

    def __init__(self, nodes: list[Node], thickness: float, label: str = "", color=None):
        super().__init__(label, color)
        self.element_type = "Area"
        self.nodes = list(nodes)
        self.__dict__["thickness"] = float(thickness)

        self.material = None
        self.section_name = ""

        # ============================================================
        # AREA SECTION ASSIGNMENTS — referans (AreaSection nesnesi)
        # ============================================================
        self.area_section: D.AreaSection | None = None

        # ============================================================
        # AREA SECTION ASSIGNMENTS — override'lar
        # ============================================================
        self.mat_prop: str = ""           # MatProp (Default / material adı)
        self.thick_over: float | None = None     # ThickOver
        self.offset_over: float | None = None    # OffsetOver

        # ============================================================
        # yükler (mevcut)
        # ============================================================
        self.gravity_loads: list[Any] = []
        self.ref_temp: float | None = None
        self.strain_loads: list[Any] = []
        self.surface_pressures: list[Any] = []
        self.temp_loads: list[Any] = []
        self.uniform_loads: list[Any] = []
        self.uniform_to_frame_loads: list[Any] = []
        self.wind_pressures: list[Any] = []

    @property
    def thickness(self) -> float:
        if self.thick_over is not None:
            return self.thick_over
        if self.area_section is not None:
            return self.area_section.thickness
        return float(self.__dict__.get("thickness", 0.0))

    @thickness.setter
    def thickness(self, value: float) -> None:
        if getattr(self, "area_section", None) is not None:
            self.thick_over = float(value)
        else:
            self.__dict__["thickness"] = float(value)

    @property
    def section(self):
        """Geriye dönük uyum — AreaSection döndürür."""
        if self.area_section is not None:
            return self.area_section
        proj = getattr(getattr(self, "_scene", None), "project", None)
        if proj and self.section_name:
            return proj.sections.get(self.section_name)
        return None

    # --- yeni yardımcılar ---
    @property
    def effective_thickness(self) -> float:
        """ThickOver varsa onu, yoksa AreaSection.thickness, yoksa kendi thickness."""
        if self.thick_over is not None:
            return self.thick_over
        if self.area_section is not None:
            return self.area_section.thickness
        return self.thickness

    @property
    def effective_bend_thick(self) -> float:
        if self.area_section is not None:
            return self.area_section.effective_bend_thick
        return self.thickness


# ============================================================================
# LINK
# ============================================================================
class Link(Element):
    def __init__(self, node_i: Node, node_j: Node, propname: str = "LINK1",
                 label: str = "", color=None):
        super().__init__(label, color)
        self.element_type = "Link"
        self.node_i = node_i
        self.node_j = node_j
        self.propname = propname


# ============================================================================
# POLYGON
# ============================================================================
class Polygon(Element):
    def __init__(self, nodes: list[Node], label: str = "",
                 poly_type: E.PolygonType = E.PolygonType.GENERIC, color=None):
        super().__init__(label, color=color or [0.8, 0.3, 0.8, 0.6])
        self.element_type = "Polygon"
        self.poly_type = poly_type
        self.nodes = list(nodes)
        self.windplane: dict[str, Any] = {}
        self.is_temporary = False
        self.uniform_to_frame_loads: list[Any] = []
        self.associated_frame_ids: list[int] = []
        self.assigned_loads: list[D.AreaUniformLoad] = []   # yüzey yükü
        self.load_pattern: str = ""                        # hangi pattern'a ait
        self.transfer_target: str = "frames"               # frames / areas
        self.transfer_dist_type: str = "one_way"           # DistType
        self.is_load_area: bool = False                    # load transfer aktif

    def collect_loads(self) -> list[D.AreaUniformLoad]:
        """Bu polygon'a atanmış yükler."""
        return list(self.assigned_loads)

    def is_valid(self) -> bool: return len(self.nodes) >= 3

    def centroid(self) -> tuple[float, float, float]:
        n = len(self.nodes)
        if n == 0:
            return (0.0, 0.0, 0.0)
        return (
            sum(nd._x for nd in self.nodes) / n,
            sum(nd._y for nd in self.nodes) / n,
            sum(nd._z for nd in self.nodes) / n,
        )

    @staticmethod
    def calculate_normal(nodes: list[Node], use_newell: bool = True) -> glm.vec3:
        n = glm.vec3(0, 0, 0)
        if use_newell:
            N = len(nodes)
            for i in range(N):
                a, b = nodes[i], nodes[(i + 1) % N]
                n.x += (a._y - b._y) * (a._z + b._z)
                n.y += (a._z - b._z) * (a._x + b._x)
                n.z += (a._x - b._x) * (a._y + b._y)
        else:
            if len(nodes) < 3: return glm.vec3(0, 0, 1)
            v1 = glm.vec3(nodes[1]._x - nodes[0]._x, nodes[1]._y - nodes[0]._y, nodes[1]._z - nodes[0]._z)
            v2 = glm.vec3(nodes[2]._x - nodes[0]._x, nodes[2]._y - nodes[0]._y, nodes[2]._z - nodes[0]._z)
            n = glm.cross(v1, v2)
        L = glm.length(n)
        return n / L if L > 1e-9 else glm.vec3(0, 0, 1)

    @staticmethod
    def calculate_plane_axes(nodes: list[Node]) -> tuple[glm.vec3, glm.vec3, glm.vec3]:
        N = Polygon.calculate_normal(nodes)
        u = glm.vec3(nodes[1]._x - nodes[0]._x, nodes[1]._y - nodes[0]._y, nodes[1]._z - nodes[0]._z)
        u = u - N * glm.dot(u, N)
        if glm.length(u) < 1e-6:
            u = glm.vec3(1, 0, 0) - N * N.x
        u = glm.normalize(u)
        v = glm.normalize(glm.cross(N, u))
        return u, v, N

    def get_plane_frame(self):
        if len(self.nodes) < 3:
            return glm.vec3(0), glm.vec3(1, 0, 0), glm.vec3(0, 1, 0), glm.vec3(0, 0, 1)
        u, v, n = self.calculate_plane_axes(self.nodes)
        cx, cy, cz = self.centroid()
        return glm.vec3(cx, cy, cz), u, v, n

    def classify_load_direction(self, load_dir_enum: E.LoadDirection, cos_threshold: float = 0.85):
        u, v_ax, n = self.calculate_plane_axes(self.nodes)
        mapping = {
            E.LoadDirection.GLOBAL_X: glm.vec3(1, 0, 0),
            E.LoadDirection.GLOBAL_Y: glm.vec3(0, 1, 0),
            E.LoadDirection.GLOBAL_Z: glm.vec3(0, 0, 1),
            E.LoadDirection.GRAVITY: glm.vec3(0, 0, -1),
            E.LoadDirection.LOCAL_1: u,
            E.LoadDirection.LOCAL_2: v_ax,
            E.LoadDirection.LOCAL_3: n,
            E.LoadDirection.PROJECTED_X: glm.vec3(1, 0, 0),
            E.LoadDirection.PROJECTED_Y: glm.vec3(0, 1, 0),
            E.LoadDirection.PROJECTED_Z: glm.vec3(0, 0, 1),
        }
        if load_dir_enum not in mapping:
            return "UNKNOWN", glm.vec3(0, 0, -1)
        vec = mapping[load_dir_enum]
        vec = glm.normalize(vec) if glm.length(vec) > 1e-9 else vec
        dots = {"NORMAL": abs(glm.dot(vec, n)), "U": abs(glm.dot(vec, u)), "V": abs(glm.dot(vec, v_ax))}
        best = max(dots, key=dots.get)
        if dots[best] >= cos_threshold:
            return best, vec
        world_dots = {"GX": abs(vec.x), "GY": abs(vec.y), "GZ": abs(vec.z), "GRAV": abs(-vec.z)}
        best_w = max(world_dots, key=world_dots.get)
        if world_dots[best_w] >= cos_threshold:
            return best_w, vec
        return "UNKNOWN", vec

    def add_uniform_to_frame_load(self, pattern_name: str, value: float,
                                  direction=None, dist_type=None):
        from domain.definition import AreaUniformToFrameLoad, DistType
        if direction is None:
            direction = E.LoadDirection.GRAVITY
        if dist_type is None:
            dist_type = DistType.ONE_WAY
        load_item = AreaUniformToFrameLoad(
            pattern_name=pattern_name.strip(),
            direction=direction, value=value,
            dist_type=dist_type, coordinate_system="GLOBAL",
        )
        self.uniform_to_frame_loads.append(load_item)
        self.mark_dirty()


# ============================================================================
# GEOMETRİ YARDIMCILARI
# ============================================================================
def project_point_to_plane(point, plane_origin, plane_normal):
    p = glm.vec3(*point) if not isinstance(point, glm.vec3) else point
    diff = p - plane_origin
    d = glm.dot(diff, plane_normal)
    return p - plane_normal * d, d


def point_to_segment_distance_3d(p, a, b):
    pa = glm.vec3(*a) if not isinstance(a, glm.vec3) else a
    pb = glm.vec3(*b) if not isinstance(b, glm.vec3) else b
    pp = glm.vec3(*p) if not isinstance(p, glm.vec3) else p
    ab = pb - pa
    L2 = glm.dot(ab, ab)
    if L2 < 1e-12:
        return glm.length(pp - pa)
    t = max(0.0, min(1.0, glm.dot(pp - pa, ab) / L2))
    return glm.length(pp - (pa + ab * t))