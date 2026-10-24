# tools/s2k/context.py
"""
LoadContext — S2K handler'larının veri topladığı merkezi kutu.
Sadece VERİ taşır; iş mantığı handler'larda.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import pandas as pd

from tools.s2k.units_adapter import UnitConverter
from domain.definition import (
    GeneralProjectInfo, SiteInformation,
    Material, Section, LinkProp,
    LoadPattern, LoadCase, ModalCase, LoadCombination,
    SpectrumFunction, ResponseSpectrumCase, AutoSeismicTSC2018,
    SectionCut, SDSection,
)


@dataclass
class LoadContext:
    """Tüm handler'ların veri topladığı merkezi kutu."""

    # --- Birim ---
    units: UnitConverter = field(default_factory=UnitConverter)

    # --- Proje bilgisi ---
    project_info: Dict[str, Any] = field(
        default_factory=lambda: {"gen": GeneralProjectInfo(), "site": SiteInformation()}
    )

    # --- Tanımlar ---
    materials: Dict[str, Material] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    auto_select_lists: Dict[str, List[str]] = field(default_factory=dict)
    area_sections: Dict[str, dict] = field(default_factory=dict)
    area_thicknesses: Dict[str, float] = field(default_factory=dict)
    link_props: Dict[str, LinkProp] = field(default_factory=dict)

    # --- Yük tanımları ---
    load_patterns: Dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: Dict[str, ModalCase] = field(default_factory=dict)
    load_combos: Dict[str, LoadCombination] = field(default_factory=dict)

    # --- Spektrum ---
    spectrum_functions: Dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: Dict[str, ResponseSpectrumCase] = field(default_factory=dict)
    auto_seismics: Dict[str, AutoSeismicTSC2018] = field(default_factory=dict)

    # --- Kütle / kesit ---
    mass_source_map: Dict[str, float] = field(default_factory=dict)
    section_cuts: Dict[str, SectionCut] = field(default_factory=dict)

    # --- Diğer ---
    diaphragms: Dict[str, dict] = field(default_factory=dict)
    frame_modifiers: Dict[str, dict] = field(default_factory=dict)
    frame_design_procs: Dict[str, str] = field(default_factory=dict)
    frame_auto_mesh: Dict[str, dict] = field(default_factory=dict)

    joint_added_mass: Dict[str, dict] = field(default_factory=dict)
    frame_insertion_points: Dict[str, dict] = field(default_factory=dict)
    frame_end_offsets: Dict[str, dict] = field(default_factory=dict)
    frame_section_rebar: Dict[str, dict] = field(default_factory=dict)
    rebar_sizes: Dict[str, dict] = field(default_factory=dict)

    sd_sections: Dict[str, SDSection] = field(default_factory=dict)

    joint_constraints: Dict[str, str] = field(default_factory=dict)
    grid_lines: List[dict] = field(default_factory=list)

    # --- Ham DataFrame'ler (handler'lar doldurur, scene_builder okur) ---
    df_joints: Optional[pd.DataFrame] = None
    df_restraints: Optional[pd.DataFrame] = None
    df_frame_conn: Optional[pd.DataFrame] = None
    df_area_conn: Optional[pd.DataFrame] = None
    df_link_conn: Optional[pd.DataFrame] = None
    df_frame_assign: Optional[pd.DataFrame] = None
    df_area_assign: Optional[pd.DataFrame] = None
    df_link_assign: Optional[pd.DataFrame] = None
    df_frame_release: Optional[pd.DataFrame] = None

    df_joint_loads: Optional[pd.DataFrame] = None
    df_frame_gravity: Optional[pd.DataFrame] = None
    df_frame_distributed: Optional[pd.DataFrame] = None
    df_frame_points: Optional[pd.DataFrame] = None
    df_frame_temperature: Optional[pd.DataFrame] = None
    df_area_uniform: Optional[pd.DataFrame] = None
    df_area_uniform_to_frame: Optional[pd.DataFrame] = None
    df_area_wind: Optional[pd.DataFrame] = None

    df_spec_gen: Optional[pd.DataFrame] = None
    df_spec_ass: Optional[pd.DataFrame] = None
    df_section_cut_gen: Optional[pd.DataFrame] = None
    df_section_cut_quad: Optional[pd.DataFrame] = None
    df_diaphragms: Optional[pd.DataFrame] = None
    df_frame_modifiers: Optional[pd.DataFrame] = None
    df_frame_design_procs: Optional[pd.DataFrame] = None
    df_frame_auto_mesh: Optional[pd.DataFrame] = None
    df_grid_lines: Optional[pd.DataFrame] = None
    df_joint_constraints: Optional[pd.DataFrame] = None
    df_link_props_linear: Optional[pd.DataFrame] = None

    # --- Uyarılar ---
    warnings: List[str] = field(default_factory=list)