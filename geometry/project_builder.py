# geometry/project_builder.py
"""
ProjectBuilder — tüm proje tanımlarını ve elementlerini
`project.unit_system`'de yaratan merkezi sınıf.

- UnitSystem `build` başında set edilir (`unit_system` parametresi)
- Tüm `add_*` metodları `project.unit_system`'de değer alır
- Scene, material, section, load — hepsi `project`'e bağlı
- S2K import: `builder = ProjectBuilder(project, UnitSystem.TONF_M)`
  → tüm handler'lar `builder.add_*` → değerler `Tonf, m` → `convert_project_units(N_MM)`
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.units import UnitSystem, convert_project_units

from domain.project import Project
from domain.element import Node, Frame, Area, Link
from domain.definition import (
    Material, Section, LinkProp, LinkPropLinear,
    LoadPattern, LoadCase, ModalCase, LoadCombination,
    SpectrumFunction, ResponseSpectrumCase, AutoSeismicTSC2018,
    SectionCut, SDSection,
)

from geometry.scenebuilder import SceneBuilder


class ProjectBuilder:
    """
    Proje oluşturucu — `project.unit_system`'de tüm tanımları yaratır.

    Kullanım:
        # Yeni proje (kullanıcı N_MM seçti)
        builder = ProjectBuilder(project, UnitSystem.N_MM)
        builder.set_project_info(...)
        mat = builder.add_material("S235", E1=210000, G12=80769, density=7.85e-6)
        sec = builder.add_section("HE220B", profile_params={...})
        n1 = builder.create_node(0, 0, 0)
        f1 = builder.create_frame(n1, n2, "HE220B")

        # S2K import (CurrUnits = "Tonf, m, C")
        builder = ProjectBuilder(project, UnitSystem.from_sap("Tonf, m, C"))
        for row in df:
            builder.add_material(row["Material"], E1=float(row["E1"]), ...)
        builder.build_scene()   # scene'i finalize et
        convert_project_units(project, UnitSystem.N_MM)   # SI'ya dön
    """

    def __init__(self, project: Project, unit_system: UnitSystem):
        self.project = project
        self._orig_unit = project.unit_system
        project.unit_system = unit_system

        # Scene builder — node/frame/area/link
        self.scene = SceneBuilder(project)
        # Kısayol: scene builder'ın scene'i
        self._scene_builder = self.scene

        # Tanım kütüphaneleri
        self.materials: Dict[str, Material] = {}
        self.sections: Dict[str, Section] = {}
        self.link_props: Dict[str, LinkProp] = {}
        self.load_patterns: Dict[str, LoadPattern] = {}
        self.load_cases: Dict[str, LoadCase] = {}
        self.modal_cases: Dict[str, ModalCase] = {}
        self.combinations: Dict[str, LoadCombination] = {}
        self.spectrum_functions: Dict[str, SpectrumFunction] = {}
        self.response_spectrum_cases: Dict[str, ResponseSpectrumCase] = {}
        self.auto_seismics: Dict[str, AutoSeismicTSC2018] = {}
        self.section_cuts: Dict[str, SectionCut] = {}
        self.sd_sections: Dict[str, SDSection] = {}

        self.mass_source_map: Dict[str, float] = {}
        self.grid_lines: List[Dict] = []
        self.joint_constraints: Dict[str, str] = {}
        self.diaphragms: Dict[str, dict] = {}

    # ==================================================================
    # PROJECT INFO
    # ==================================================================
    def set_project_info(self, **kwargs):
        """ProjectInfo, GeneralProjectInfo, SiteInformation alanları."""
        from domain.definition import GeneralProjectInfo, SiteInformation, ProjectInfo
        for key, value in kwargs.items():
            if hasattr(self.project.info, key):
                setattr(self.project.info, key, value)
            elif hasattr(self.project.general_info, key):
                setattr(self.project.general_info, key, value)
            elif hasattr(self.project.site_info, key):
                setattr(self.project.site_info, key, value)

    # ==================================================================
    # MATERIAL
    # ==================================================================
    def add_material(
        self, name: str, *, mat_type=None, color=None,
        E1: float = 2.1e5, G12: float = 8.1e4, density: float = 7.85e-6,
        fy: float = 235.0, fu: float = 360.0, nu12: float = 0.3,
        **kwargs,
    ) -> Material:
        """Material `project.unit_system`'de. Değerler dönüştürülmez."""
        from data.enums import MatType
        mat = Material(
            name=name,
            mat_type=mat_type or MatType.STEEL,
            color=color or (0.8, 0.8, 0.8),
            E1=E1, E2=E1, E3=E1,
            G12=G12, G13=G12, G23=G12,
            nu12=nu12, nu13=nu12, nu23=nu12,
            density=density, fy=fy, fu=fu,
        )
        self.materials[name] = mat
        self.project.materials[name] = mat
        return mat

    # ==================================================================
    # SECTION
    # ==================================================================
    def add_section(
        self, name: str, *, profile_type, profile_params: dict,
        material: Optional[Material] = None, color=None, sd_section=None,
        catalog_props: Optional[dict] = None, catalog_source: str = "",
    ) -> Section:
        """Section `project.unit_system`'de."""
        sec = Section(
            name=name,
            profile_type=profile_type,
            profile_params=dict(profile_params),   # kopya
            material=material or self._default_material(),
            color=color or (0.8, 0.8, 0.8),
            catalog_props=dict(catalog_props) if catalog_props else {},
            catalog_source=catalog_source,
            sd_section=sd_section,
        )
        self.sections[name] = sec
        self.project.sections[name] = sec
        return sec

    def _default_material(self) -> Material:
        """Hiç material yoksa DEFAULT_STEEL."""
        if self.materials:
            return next(iter(self.materials.values()))
        from domain.definition import DEFAULT_MATERIAL
        return DEFAULT_MATERIAL

    # ==================================================================
    # LINK PROP
    # ==================================================================
    def add_link_prop(self, name: str, *, prop_type, **kwargs) -> LinkProp:
        from data.enums import LinkPropType
        if prop_type == LinkPropType.LINEAR:
            prop = LinkPropLinear(name=name, prop_type=prop_type, **kwargs)
        else:
            prop = LinkProp(name=name, prop_type=prop_type)
        self.link_props[name] = prop
        self.project.link_props[name] = prop
        return prop

    # ==================================================================
    # LOAD PATTERN / CASE / COMBO
    # ==================================================================
    def add_load_pattern(self, name: str, *, design_type: str = "Dead",
                         self_wt_mult: float = 0.0) -> LoadPattern:
        lp = LoadPattern(name=name, design_type=design_type, self_wt_mult=self_wt_mult)
        self.load_patterns[name] = lp
        self.project.load_patterns[name] = lp
        return lp

    def add_load_case(self, name: str, **kwargs) -> LoadCase:
        case = LoadCase(name=name, **kwargs)
        self.load_cases[name] = case
        self.project.load_cases[name] = case
        return case

    def add_modal_case(self, name: str, **kwargs) -> ModalCase:
        case = ModalCase(name=name, **kwargs)
        self.modal_cases[name] = case
        self.project.modal_cases[name] = case
        return case

    def add_combination(self, name: str, **kwargs) -> LoadCombination:
        combo = LoadCombination(name=name, **kwargs)
        self.combinations[name] = combo
        self.project.combinations[name] = combo
        return combo

    # ==================================================================
    # SPECTRUM / SEISMIC
    # ==================================================================
    def add_spectrum_function(self, **kwargs) -> SpectrumFunction:
        spec = SpectrumFunction(**kwargs)
        self.spectrum_functions[spec.name] = spec
        self.project.spectrum_functions[spec.name] = spec
        return spec

    def add_response_spectrum_case(self, **kwargs) -> ResponseSpectrumCase:
        rs = ResponseSpectrumCase(**kwargs)
        self.response_spectrum_cases[rs.name] = rs
        self.project.response_spectrum_cases[rs.name] = rs
        return rs

    def add_auto_seismic(self, **kwargs) -> AutoSeismicTSC2018:
        a = AutoSeismicTSC2018(**kwargs)
        self.auto_seismics[a.load_pattern] = a
        self.project.auto_seismics[a.load_pattern] = a
        return a

    # ==================================================================
    # SECTION CUT / SD
    # ==================================================================
    def add_section_cut(self, name: str, **kwargs) -> SectionCut:
        sc = SectionCut(name=name, **kwargs)
        self.section_cuts[name] = sc
        self.project.section_cuts[name] = sc
        return sc

    def add_sd_section(self, name: str, **kwargs) -> SDSection:
        sd = SDSection(name=name, **kwargs)
        self.sd_sections[name] = sd
        return sd

    # ==================================================================
    # SCENE (Node / Frame / Area / Link)
    # ==================================================================
    def create_node(self, x: float, y: float, z: float, label: str = "", restraint=None) -> Node:
        return self._scene_builder.create_node(x, y, z, label=label, restraint=restraint)

    def create_frame(self, node_i: Node, node_j: Node, section_name: str,
                     rotation_deg: float = 0.0, label: str = "") -> Frame:
        return self._scene_builder.create_frame(node_i, node_j, section_name,
                                                 rotation_deg=rotation_deg, label=label)

    def create_area(self, nodes: List[Node], thickness: float, label: str = "") -> Area:
        return self._scene_builder.create_area(nodes, thickness=thickness, label=label)

    def create_link(self, node_i: Node, node_j: Node, prop_name: str, label: str = "") -> Link:
        return self._scene_builder.create_link(node_i, node_j, prop_name=prop_name, label=label)

    # ==================================================================
    # GRID / CONSTRAINTS
    # ==================================================================
    def set_grid_lines(self, lines: List[Dict]):
        self.grid_lines = list(lines)
        self.project.grid_lines = self.grid_lines
        self.project.sync_grid_from_s2k_lines()

    def set_joint_constraints(self, constraints: Dict[str, str]):
        self.joint_constraints = dict(constraints)
        self.project.joint_constraints = self.joint_constraints

    # ==================================================================
    # FINALIZE
    # ==================================================================
    def finalize(self):
        """
        Scene'i project'e bağla, mass_source_map, load'ları kontrol et.
        `convert_project_units` ÇAĞIRMAZ — çağıran karar verir.
        """
        scene = self._scene_builder.scene
        scene.units = self.project.unit_system.value
        if hasattr(scene, "mark_dirty"):
            scene.mark_dirty()
        self.project.scene = scene

        # Mass source
        if self.mass_source_map:
            self.project.mass_source_map = dict(self.mass_source_map)

        logger.info(
            "[ProjectBuilder] finalize: %d material, %d section, %d node, %d frame",
            len(self.materials), len(self.sections),
            len(scene.nodes), len(scene.frames),
        )
        return self.project

    def finalize_and_convert(self, target: UnitSystem = UnitSystem.N_MM):
        self.finalize()
        from_sys = self.project.unit_system
        n = convert_project_units(self.project, target, reason="ProjectBuilder")

        # Grid lines — list[dict] manuel
        from core.units import convert_value, Dimension
        for gl in self.project.grid_lines:
            if "ordinate" in gl:
                gl["ordinate"] = convert_value(
                    Dimension.LENGTH, gl["ordinate"], from_sys, target,
                )

        # Grid config
        if self.project.grid:
            for attr in ("x_coords", "y_coords", "z_coords"):
                coords = getattr(self.project.grid, attr, None)
                if coords:
                    setattr(self.project.grid, attr, [
                        convert_value(Dimension.LENGTH, v, from_sys, target)
                        for v in coords
                    ])

        # Section cuts — quad points manuel
        for sc in self.project.section_cuts.values():
            sc.global_x = convert_value(Dimension.LENGTH, sc.global_x, from_sys, target)
            sc.global_y = convert_value(Dimension.LENGTH, sc.global_y, from_sys, target)
            sc.global_z = convert_value(Dimension.LENGTH, sc.global_z, from_sys, target)
            if sc.quad and sc.quad.points:
                sc.quad.points = [
                    tuple(convert_value(Dimension.LENGTH, v, from_sys, target) for v in pt)
                    for pt in sc.quad.points
                ]

        logger.info("[ProjectBuilder] %d alan dönüştürüldü (%s → %s)",
                    n, from_sys.value, target.value)
        return self.project


import logging
logger = logging.getLogger(__name__)