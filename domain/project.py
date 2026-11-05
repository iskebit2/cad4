# domain/project.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.units import UnitSystem
from data.serializer import load_project_file, save_project_file
from domain.definition import (
    AnalysisManager, AreaSection, AutoSeismicTSC2018, ConstraintDefinition,
    GeneralProjectInfo, LinkProp, LoadCase, LoadCombination, LoadManager,
    LoadPattern, Material, ModalCase, ProjectConfig, ProjectInfo,
    ReportManager, ResponseSpectrumCase, Section, SectionCut,
    SiteInformation, SpectrumFunction, SpectrumSourceType,
    get_tsc2018_site_coefficients,
)
from domain.grid import Grid
from domain.line import Line
from domain.plane import Plane
from domain.polygon import Polygon
from domain.scene import Scene


@dataclass
class Project:
    info: ProjectInfo = field(default_factory=ProjectInfo)
    general_info: GeneralProjectInfo = field(default_factory=GeneralProjectInfo)
    site_info: SiteInformation = field(default_factory=SiteInformation)
    config: ProjectConfig = field(default_factory=ProjectConfig)
    scene: Scene = field(default_factory=Scene)
    polygons: dict[int, Polygon] = field(default_factory=dict)
    lines: dict[int, Line] = field(default_factory=dict)   # ← ekle
    loads: LoadManager = field(default_factory=LoadManager)
    analysis: AnalysisManager = field(default_factory=AnalysisManager)
    report: ReportManager = field(default_factory=ReportManager)
    unit_system: UnitSystem = UnitSystem.N_MM

    grid: Grid = field(default_factory=Grid)
    custom_planes: dict[str, Plane] = field(default_factory=dict)

    _active_plane_id: str | None = field(
        default=None, init=False, repr=False, compare=False,
    )
    _grid_planes_cache: dict[str, Plane] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )

    materials: dict[str, Material] = field(default_factory=dict)
    sections: dict[str, Section] = field(default_factory=dict)
    area_sections: dict[str, AreaSection] = field(default_factory=dict)
    link_props: dict[str, LinkProp] = field(default_factory=dict)
    load_patterns: dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: dict[str, ModalCase] = field(default_factory=dict)
    combinations: dict[str, LoadCombination] = field(default_factory=dict)
    spectrum_functions: dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: dict[str, ResponseSpectrumCase] = field(default_factory=dict)
    auto_seismics: dict[str, AutoSeismicTSC2018] = field(default_factory=dict)
    mass_source_map: dict[str, float] = field(default_factory=dict)
    constraint_definitions: dict[str, ConstraintDefinition] = field(default_factory=dict)
    section_cuts: dict[str, SectionCut] = field(default_factory=dict)
    diaphragms: dict[str, dict] = field(default_factory=dict)
    joint_constraints: dict[str, str] = field(default_factory=dict)
    frame_modifiers: dict[str, dict] = field(default_factory=dict)
    frame_design_procs: dict[str, str] = field(default_factory=dict)
    frame_auto_mesh: dict[str, dict] = field(default_factory=dict)
    catalog_sections: dict[str, Section] = field(default_factory=dict)

    def __post_init__(self):
        self.scene.project = self

    # ------------------------------------------------------------------
    def add_polygon(self, polygon: Polygon) -> None:
        self.polygons[polygon.unique_id] = polygon

    def remove_polygon(self, polygon_id: int) -> None:
        self.polygons.pop(polygon_id, None)

    # ------------------------------------------------------------------
    def _add(self, registry: dict, obj, key: str = "name") -> None:
        registry[getattr(obj, key)] = obj

    def add_material(self, m): self._add(self.materials, m)
    def add_section(self, s): self._add(self.sections, s)
    def add_area_section(self, s): self._add(self.area_sections, s)
    def add_link_prop(self, p): self._add(self.link_props, p)
    def add_load_pattern(self, p): self._add(self.load_patterns, p)
    def add_load_case(self, c): self._add(self.load_cases, c)
    def add_modal_case(self, c): self._add(self.modal_cases, c)
    def add_combination(self, c): self._add(self.combinations, c)
    def add_spectrum_function(self, s): self._add(self.spectrum_functions, s)
    def add_response_spectrum_case(self, r): self._add(self.response_spectrum_cases, r)
    def add_auto_seismic(self, a): self._add(self.auto_seismics, a, "load_pattern")
    def add_section_cut(self, s): self._add(self.section_cuts, s)
    def add_constraint_definition(self, c): self._add(self.constraint_definitions, c)

    def get_section_cut(self, name): return self.section_cuts.get(name)
    def get_section_by_name(self, name): return self.sections.get(name)
    def get_material_by_name(self, name): return self.materials.get(name)
    def get_link_prop_by_name(self, name): return self.link_props.get(name)

    # ------------------------------------------------------------------
    def grid_planes(self) -> list[Plane]:
        if not self._grid_planes_cache:
            self._grid_planes_cache = {}
            for z in sorted(set(self.grid.z_coords)):
                p = Plane.from_axis_offset("z", z, name=f"XY_Z{z:g}")
                self._grid_planes_cache[p.name] = p
            for y in sorted(set(self.grid.y_coords)):
                p = Plane.from_axis_offset("y", y, name=f"XZ_Y{y:g}")
                self._grid_planes_cache[p.name] = p
            for x in sorted(set(self.grid.x_coords)):
                p = Plane.from_axis_offset("x", x, name=f"YZ_X{x:g}")
                self._grid_planes_cache[p.name] = p
        return list(self._grid_planes_cache.values())

    def invalidate_grid_planes(self):
        self._grid_planes_cache.clear()

    def all_planes(self) -> dict[str, Plane]:
        result = {p.name: p for p in self.grid_planes()}
        result.update(self.custom_planes)
        return result

    def get_plane(self, name: str) -> Plane | None:
        return self.all_planes().get(name)

    def get_plane_by_id(self, plane_id: str) -> Plane | None:
        for p in self.all_planes().values():
            if p.plane_id == plane_id:
                return p
        return None

    def plane_names(self) -> list[str]:
        return sorted(self.all_planes())

    def add_plane(self, plane: Plane) -> Plane:
        self.custom_planes[plane.name] = plane
        return plane

    def remove_plane(self, name: str) -> bool:
        if name not in self.custom_planes:
            return False
        plane = self.custom_planes.pop(name)
        if self._active_plane_id == getattr(plane, "plane_id", None):
            self._active_plane_id = None
        return True

    @property
    def active_plane_id(self) -> str | None:
        if self._active_plane_id and self.get_plane_by_id(self._active_plane_id) is None:
            self._active_plane_id = None
        return self._active_plane_id

    @property
    def active_plane(self) -> Plane | None:
        pid = self.active_plane_id
        return self.get_plane_by_id(pid) if pid else None

    def activate_plane(self, plane: str | Plane) -> Plane:
        if isinstance(plane, Plane):
            registered = self.get_plane_by_id(plane.plane_id)
        else:
            registered = self.get_plane(plane) or self.get_plane_by_id(plane)
        if registered is None:
            raise KeyError(f"Plane bulunamadı: {plane}")
        self._active_plane_id = registered.plane_id
        return registered

    def deactivate_plane(self) -> Plane | None:
        active = self.active_plane
        self._active_plane_id = None
        return active

    def planes_containing(self, pt) -> list[Plane]:
        return [p for p in self.all_planes().values() if p.contains_pt(pt)]

    # ------------------------------------------------------------------
    def grid_levels(self, orientation: str) -> list[float]:
        m = {"XY": self.grid.z_coords, "XZ": self.grid.y_coords, "YZ": self.grid.x_coords}
        return sorted(set(m.get(orientation.upper(), [])))

    def create_grid_plane(self, orientation: str, level: float,
                          depth_minus: float = 0.0, depth_plus: float = 0.0,
                          name: str = "") -> Plane | None:
        axis_map = {"XY": "z", "XZ": "y", "YZ": "x"}
        axis = axis_map.get(orientation.upper())
        if axis is None:
            return None
        plane = Plane.from_axis_offset(
            axis, float(level),
            depth_minus=float(depth_minus), depth_plus=float(depth_plus),
            name=name or f"Grid_{orientation}_{level:g}",
        )
        xs, ys, zs = self.grid.x_coords, self.grid.y_coords, self.grid.z_coords
        bounds = {"XY": (xs, ys), "XZ": (xs, zs), "YZ": (ys, zs)}.get(orientation.upper())
        if bounds and bounds[0] and bounds[1]:
            plane.set_bounds(min(bounds[0]), max(bounds[0]),
                             min(bounds[1]), max(bounds[1]))
        return plane

    # ------------------------------------------------------------------
    def create_tbdy2018_spectrum(self, name, ss, s1, site_class="ZC",
                                  r_coeff=1.0, d_coeff=1.0, i_coeff=1.0,
                                  tl=6.0, num_points=200) -> SpectrumFunction:
        fs, f1 = get_tsc2018_site_coefficients(ss, s1, site_class)
        sds, sd1 = ss * fs, s1 * f1
        ta = 0.2 * sd1 / sds if sds > 0 else 0.0
        tb = sd1 / sds if sds > 0 else 0.0
        dt = max(tl + 2.0, 8.0) / num_points
        points = []
        for k in range(num_points + 1):
            t = k * dt
            if ta > 0 and t < ta:
                sae = (0.4 + 0.6 * t / ta) * sds
            elif t <= tb:
                sae = sds
            elif t <= tl:
                sae = sd1 / t
            else:
                sae = sd1 * tl / (t * t)
            ra = ((d_coeff + (r_coeff / i_coeff - d_coeff) * t / tb)
                  if (t < tb and tb > 0) else r_coeff / i_coeff)
            points.append((round(t, 4), round(sae / ra, 6)))
        spec = SpectrumFunction(
            name=name, source_type=SpectrumSourceType.TSC_2018,
            ss=ss, s1=s1, tl=tl, site_class=site_class, fs=fs, f1=f1,
            r_coeff=r_coeff, d_coeff=d_coeff, i_coeff=i_coeff, points=points,
        )
        self.add_spectrum_function(spec)
        return spec

    # ------------------------------------------------------------------
    def save(self, filepath: str) -> None:
        path = Path(filepath)
        if path.suffix != ".cd4":
            path = path.with_suffix(".cd4")
        save_project_file(self, path)

    @classmethod
    def load(cls, filepath: str) -> "Project":
        path = Path(filepath)
        if not path.exists():
            return cls()
        return load_project_file(path)

    def sync_grid_from_s2k_lines(self, grid_lines: list[dict]) -> None:
        if not grid_lines:
            return
        xs, ys, zs = [], [], []
        for gl in grid_lines:
            direction = str(gl.get("axis_dir", gl.get("line_type", "X"))).upper()
            v = float(gl.get("ordinate", 0.0))
            if "X" in direction:
                xs.append(v)
            elif "Y" in direction or "V" in direction:
                ys.append(v)
            elif "Z" in direction:
                zs.append(v)
        self.grid = Grid(
            x_coords=sorted(set(xs)), y_coords=sorted(set(ys)),
            z_coords=sorted(set(zs)),
        )
        self.invalidate_grid_planes()

    # ------------------------------------------------------------------
    def _migrate_materials(self):
        pass

    def __repr__(self) -> str:
        return (f"<Project unit={self.unit_system.value} "
                f"materials={len(self.materials)} sections={len(self.sections)} "
                f"patterns={len(self.load_patterns)} cases={len(self.load_cases)}>")

    def summary(self) -> str:
        return (
            f"Project [{self.unit_system.value}]\n"
            f"  Materials: {len(self.materials)}\n"
            f"  Sections: {len(self.sections)}\n"
            f"  AreaSections: {len(self.area_sections)}\n"
            f"  LinkProps: {len(self.link_props)}\n"
            f"  LoadPatterns: {len(self.load_patterns)}\n"
            f"  LoadCases: {len(self.load_cases)}\n"
            f"  Combinations: {len(self.combinations)}\n"
            f"{self.scene.summary()}"
        )