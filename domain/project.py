# domain/project.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.units import UnitSystem
from data.serializer import load_project_file, save_project_file
from domain.definition import (
    AnalysisManager,
    AreaSection,
    AutoSeismicTSC2018,
    GeneralProjectInfo,
    GridConfig,
    LinkProp,
    LoadCase,
    LoadCombination,
    LoadManager,
    LoadPattern,
    Material,
    ModalCase,
    ProjectConfig,
    ProjectInfo,
    ReportManager,
    ResponseSpectrumCase,
    Section,
    SectionCut,
    SiteInformation,
    SpectrumFunction,
    SpectrumSourceType,
    get_tsc2018_site_coefficients,
)
from domain.plane import Plane
from domain.plane_manager import PlaneManager
from domain.scene import Scene


@dataclass
class Project:
    info: ProjectInfo = field(default_factory=ProjectInfo)
    general_info: GeneralProjectInfo = field(default_factory=GeneralProjectInfo)
    site_info: SiteInformation = field(default_factory=SiteInformation)
    config: ProjectConfig = field(default_factory=ProjectConfig)
    scene: Scene = field(default_factory=Scene)
    loads: LoadManager = field(default_factory=LoadManager)
    analysis: AnalysisManager = field(default_factory=AnalysisManager)
    report: ReportManager = field(default_factory=ReportManager)
    unit_system: UnitSystem = UnitSystem.N_MM
    grid: GridConfig = field(default_factory=GridConfig)
    planes: dict[str, Plane] = field(default_factory=dict)

    # --- ESKİ DEFINITION MANAGER MİRASI (Doğrudan Project'e monte edildi) ---
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
    section_cuts: dict[str, SectionCut] = field(default_factory=dict)
    diaphragms: dict[str, dict] = field(default_factory=dict)
    grid_lines: list[dict[str, Any]] = field(default_factory=list)
    joint_constraints: dict[str, str] = field(default_factory=dict)
    frame_modifiers: dict[str, dict] = field(default_factory=dict)
    frame_design_procs: dict[str, str] = field(default_factory=dict)
    frame_auto_mesh: dict[str, dict] = field(default_factory=dict)

    catalog_sections: dict[str, Section] = field(default_factory=dict)

    def __post_init__(self):
        # Scene, projeye referans versin ki kendi içinden malzemelere/kesitlere ulaşabilsin
        self.scene.project = self

    def add_material(self, m: Material):        self.materials[m.name] = m
    def add_section(self, s: Section):          self.sections[s.name] = s
    def add_area_section(self, s: AreaSection): self.area_sections[s.name] = s
    def add_link_prop(self, p: LinkProp):       self.link_props[p.name] = p
    def add_load_pattern(self, p: LoadPattern): self.load_patterns[p.name] = p
    def add_load_case(self, c: LoadCase):       self.load_cases[c.name] = c
    def add_modal_case(self, c: ModalCase):     self.modal_cases[c.name] = c
    def add_combination(self, c: LoadCombination): self.combinations[c.name] = c
    def add_spectrum_function(self, spec: SpectrumFunction): self.spectrum_functions[spec.name] = spec
    def add_response_spectrum_case(self, rs: ResponseSpectrumCase): self.response_spectrum_cases[rs.name] = rs
    def add_auto_seismic(self, a: AutoSeismicTSC2018): self.auto_seismics[a.load_pattern] = a
    def add_section_cut(self, sc: SectionCut): 
        self.section_cuts[sc.name] = sc

    def get_section_cut(self, name: str) -> SectionCut | None:
        return self.section_cuts.get(name)
    def get_section_by_name(self, name: str) -> Section | None:     return self.sections.get(name)
    def get_material_by_name(self, name: str) -> Material | None:   return self.materials.get(name)
    def get_link_prop_by_name(self, name: str) -> LinkProp | None:  return self.link_props.get(name)
    # ---- Plane CRUD (PlaneManager'a delege) ----
    @property
    def plane_mgr(self) -> PlaneManager:
        # Lazy — her erişimde yeni sarmalayıcı (hafif)
        return PlaneManager(self)

    def add_plane(self, plane: Plane) -> Plane:
        return self.plane_mgr.add(plane)

    def get_plane(self, name: str) -> Plane | None:
        return self.planes.get(name)

    def remove_plane(self, name: str) -> bool:
        return self.plane_mgr.remove(name)

    def plane_names(self) -> list[str]:
        return self.plane_mgr.names()


    def create_tbdy2018_spectrum(
        self, name, ss, s1, site_class="ZC",
        r_coeff=1.0, d_coeff=1.0, i_coeff=1.0,
        tl=6.0, num_points=200,
    ) -> SpectrumFunction:
        fs, f1 = get_tsc2018_site_coefficients(ss, s1, site_class)
        sds, sd1 = ss * fs, s1 * f1
        ta = 0.2 * sd1 / sds if sds > 0 else 0.0
        tb = sd1 / sds if sds > 0 else 0.0
        points = []
        max_t = max(tl + 2.0, 8.0)
        dt = max_t / num_points
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
            ra = (d_coeff + (r_coeff / i_coeff - d_coeff) * t / tb) if (t < tb and tb > 0) else r_coeff / i_coeff
            points.append((round(t, 4), round(sae / ra, 6)))

        spec = SpectrumFunction(
            name=name, source_type=SpectrumSourceType.TSC_2018,
            ss=ss, s1=s1, tl=tl, site_class=site_class,
            fs=fs, f1=f1,
            r_coeff=r_coeff, d_coeff=d_coeff, i_coeff=i_coeff,
            points=points,
        )
        self.add_spectrum_function(spec)
        return spec

    # ==================================================================
    # FILE I/O (Serializer'a delege edilir)
    # ==================================================================
    def save(self, filepath: str):
        
        path = Path(filepath)
        if path.suffix != ".cd4":
            path = path.with_suffix(".cd4")
        save_project_file(self, path)

    @classmethod
    def load(cls, filepath: str) -> "Project":
        path = Path(filepath)
        if not path.exists():
            return cls()
        p = load_project_file(path)
        p._migrate_materials()
        return p

    def sync_grid_from_s2k_lines(self):
        """S2K'dan gelen ham grid_lines verilerini CAD4 GridConfig yapısına senkronize eder."""
        if not self.grid_lines:
            return

        xs, ys, zs = [], [], []

        for gl in self.grid_lines:
            axis_dir = str(gl.get('axis_dir', gl.get('line_type', 'X'))).upper()
            ordinate = float(gl.get('ordinate', 0.0))
            
            # AxisDir değerine göre doğru koordinat listesine atıyoruz
            if 'X' in axis_dir:
                xs.append(ordinate)
            elif 'Y' in axis_dir or 'V' in axis_dir:
                ys.append(ordinate)
            elif 'Z' in axis_dir:
                zs.append(ordinate)

        if xs:
            self.grid.x_coords = sorted(list(set(xs)))
        if ys:
            self.grid.y_coords = sorted(list(set(ys)))
        if zs:
            self.grid.z_coords = sorted(list(set(zs)))

    def _migrate_materials(self):
        import logging
        log = logging.getLogger(__name__)
        logged = set()

        def _fix_density(mat):
            name = getattr(mat, "name", "?")
            rho = float(mat.density or 0.0)
            if rho <= 0 or 1e-8 <= rho <= 1e-4:
                return
            if 1e-13 < rho < 1e-8:
                new = rho * 1000.0
            elif 1e-3 <= rho < 1.0:
                new = rho * 9.80665e-6
            elif 1.0 <= rho < 25.0:
                new = rho * 1e-6
            elif 100.0 <= rho < 25000.0:
                new = rho * 1e-9
            else:
                return
            mat.density = new
            if ("density", name) not in logged:
                log.info("[Migrate] %s.density: %g → %g kg/mm³", name, rho, new)
                logged.add(("density", name))
            

        def _fix_E1(mat):
            e = float(mat.E1 or 0.0)
            if e <= 0:
                return
            if 1e3 <= e <= 5e5:                           # MPa (max 500 GPa)
                return
            if 5e5 < e <= 1e10:
                new = e * 9.80665e-3                      # tonf/m² → MPa
            elif e > 1e10:
                new = e * 6.89476e-3                      # psi → MPa
            else:
                return
            mat.E1 = new
            mat.E2 = new
            mat.E3 = new
            log.warning("[Migrate] %s.E1: %g → %g MPa",
                        getattr(mat, "name", "?"), e, new)

        def _fix_G12(mat):
            g = float(mat.G12 or 0.0)
            if g <= 0:
                return
            if 1e3 <= g <= 5e5:
                return
            if 5e5 < g <= 1e10:
                new = g * 9.80665e-3
            elif g > 1e10:
                new = g * 6.89476e-3
            else:
                return
            mat.G12 = new
            mat.G13 = new
            mat.G23 = new
            log.warning("[Migrate] %s.G12: %g → %g MPa",
                        getattr(mat, "name", "?"), g, new)

        def _fix(mat):
            if mat is None:
                return
            _fix_density(mat)
            _fix_E1(mat)
            _fix_G12(mat)

        # ---------- tüm Material kopyalarını bul ----------
        

        def _visit(mat):
            if mat is None or id(mat) in _seen:
                return
            _seen.add(id(mat))
            _fix_density(mat)
            _fix_E1(mat)
            _fix_G12(mat)

        _seen = set()
        for m in self.materials.values():
            _visit(m)
        for sec in self.sections.values():
            _visit(getattr(sec, "material", None))
        for frame in self.scene.frames.values():
            sec = getattr(frame, "section", None)
            _visit(getattr(sec, "material", None) if sec else None)
        for area in self.scene.areas.values():
            _visit(getattr(area, "material", None))

        if _seen:
            log.info("[Migrate] %d Material nesnesi işlendi", len(_seen))

    def __repr__(self) -> str:
        return (
            f"<Project unit={self.unit_system.value} "
            f"materials={len(self.materials)} sections={len(self.sections)} "
            f"patterns={len(self.load_patterns)} cases={len(self.load_cases)}>"
        )

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