# domain/project.py
from dataclasses import dataclass, field
import json
import zipfile
from pathlib import Path
from typing import Dict, Optional, List, Any

from data.enums import UnitSystem
from domain.element import Area, Frame, Link, Node, Polygon
from domain.scene import Scene
from domain.definition import (
    AnalysisManager, GeneralProjectInfo, GridConfig, LoadManager, ProjectConfig, ProjectInfo,
    ReportManager, SiteInformation,
    Material, Section, LinkProp, LoadPattern, LoadCase, ModalCase,
    LoadCombination, SpectrumFunction, ResponseSpectrumCase, AutoSeismicTSC2018,
    SpectrumSourceType, get_tsc2018_site_coefficients
)

from data.serializer import save_project_file, load_project_file


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

    # --- ESKİ DEFINITION MANAGER MİRASI (Doğrudan Project'e monte edildi) ---
    materials: Dict[str, Material] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    link_props: Dict[str, LinkProp] = field(default_factory=dict)
    load_patterns: Dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: Dict[str, ModalCase] = field(default_factory=dict)
    combinations: Dict[str, LoadCombination] = field(default_factory=dict)
    spectrum_functions: Dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: Dict[str, ResponseSpectrumCase] = field(default_factory=dict)
    auto_seismics: Dict[str, AutoSeismicTSC2018] = field(default_factory=dict)
    mass_source_map: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        # Scene, projeye referans versin ki kendi içinden malzemelere/kesitlere ulaşabilsin
        self.scene.project = self

    def add_material(self, m: Material):        self.materials[m.name] = m
    def add_section(self, s: Section):          self.sections[s.name] = s
    def add_link_prop(self, p: LinkProp):       self.link_props[p.name] = p
    def add_load_pattern(self, p: LoadPattern): self.load_patterns[p.name] = p
    def add_load_case(self, c: LoadCase):       self.load_cases[c.name] = c
    def add_modal_case(self, c: ModalCase):     self.modal_cases[c.name] = c
    def add_combination(self, c: LoadCombination): self.combinations[c.name] = c
    def add_spectrum_function(self, spec: SpectrumFunction): self.spectrum_functions[spec.name] = spec
    def add_response_spectrum_case(self, rs: ResponseSpectrumCase): self.response_spectrum_cases[rs.name] = rs
    def add_auto_seismic(self, a: AutoSeismicTSC2018): self.auto_seismics[a.load_pattern] = a

    def get_section_by_name(self, name: str) -> Optional[Section]:     return self.sections.get(name)
    def get_material_by_name(self, name: str) -> Optional[Material]:   return self.materials.get(name)
    def get_link_prop_by_name(self, name: str) -> Optional[LinkProp]:  return self.link_props.get(name)

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
        return load_project_file(path)