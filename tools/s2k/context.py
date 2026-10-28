# tools/s2k/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from domain.definition import (
    GeneralProjectInfo,
    LinkProp,
    LoadCase,
    LoadCombination,
    LoadPattern,
    Material,
    ModalCase,
    PointLoad,
    SDSection,
    Section,
    SiteInformation,
    SpectrumFunction,
)


@dataclass
class LoadContext:
    """S2K handler'larının veri topladığı merkezi kutu."""

    # --- S2K CurrUnits (string) ---
    units_source_string: str = "N, mm, C"

    # --- Proje bilgisi ---
    project_info: dict[str, Any] = field(
        default_factory=lambda: {"gen": GeneralProjectInfo(), "site": SiteInformation()}
    )

    # --- Tanımlar ---
    materials: dict[str, Material] = field(default_factory=dict)
    sections: dict[str, Section] = field(default_factory=dict)
    auto_select_lists: dict[str, list[str]] = field(default_factory=dict)
    area_sections: dict[str, dict] = field(default_factory=dict)
    area_thicknesses: dict[str, float] = field(default_factory=dict)
    link_props: dict[str, LinkProp] = field(default_factory=dict)

    # --- Yük tanımları ---
    load_patterns: dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: dict[str, ModalCase] = field(default_factory=dict)
    load_combos: dict[str, LoadCombination] = field(default_factory=dict)

    # --- Spektrum ---
    spectrum_functions: dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: dict[str, Any] = field(default_factory=dict)
    auto_seismics: dict[str, Any] = field(default_factory=dict)

    # --- Kütle / kesit ---
    mass_source_map: dict[str, float] = field(default_factory=dict)
    section_cuts: dict[str, Any] = field(default_factory=dict)

    # --- Diğer ---
    diaphragms: dict[str, dict] = field(default_factory=dict)
    frame_modifiers: dict[str, dict] = field(default_factory=dict)
    frame_design_procs: dict[str, str] = field(default_factory=dict)
    frame_auto_mesh: dict[str, dict] = field(default_factory=dict)
    joint_added_mass: dict[str, dict] = field(default_factory=dict)
    frame_insertion_points: dict[str, dict] = field(default_factory=dict)
    frame_end_offsets: dict[str, dict] = field(default_factory=dict)
    frame_section_rebar: dict[str, dict] = field(default_factory=dict)
    rebar_sizes: dict[str, dict] = field(default_factory=dict)
    sd_sections: dict[str, SDSection] = field(default_factory=dict)
    joint_loads: dict[str, list[PointLoad]] = field(default_factory=dict)
    joint_constraints: dict[str, str] = field(default_factory=dict)
    grid_lines: list[dict] = field(default_factory=list)

    # --- Ham DataFrame'ler (handler'lar doldurur, scene_builder okur) ---
    df_joints: pd.DataFrame | None = None
    df_restraints: pd.DataFrame | None = None
    df_frame_conn: pd.DataFrame | None = None
    df_area_conn: pd.DataFrame | None = None
    df_link_conn: pd.DataFrame | None = None
    df_frame_assign: pd.DataFrame | None = None
    df_area_assign: pd.DataFrame | None = None
    df_link_assign: pd.DataFrame | None = None
    df_frame_release: pd.DataFrame | None = None

    df_joint_loads: pd.DataFrame | None = None
    df_frame_gravity: pd.DataFrame | None = None
    df_frame_distributed: pd.DataFrame | None = None
    df_frame_points: pd.DataFrame | None = None
    df_frame_temperature: pd.DataFrame | None = None
    df_area_uniform: pd.DataFrame | None = None
    df_area_uniform_to_frame: pd.DataFrame | None = None
    df_area_wind: pd.DataFrame | None = None

    df_spec_gen: pd.DataFrame | None = None
    df_spec_ass: pd.DataFrame | None = None
    df_section_cut_gen: pd.DataFrame | None = None
    df_section_cut_quad: pd.DataFrame | None = None
    df_diaphragms: pd.DataFrame | None = None
    df_frame_modifiers: pd.DataFrame | None = None
    df_frame_design_procs: pd.DataFrame | None = None
    df_frame_auto_mesh: pd.DataFrame | None = None
    df_grid_lines: pd.DataFrame | None = None
    df_joint_constraints: pd.DataFrame | None = None
    df_link_props_linear: pd.DataFrame | None = None

    # --- Uyarılar ---
    warnings: list[str] = field(default_factory=list)