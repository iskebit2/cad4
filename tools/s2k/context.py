# tools/s2k/context.py
"""
Load context — handler'ların veri topladığı merkezi kutu.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

import pandas as pd

from domain.definition import (
    Material, Section, LinkProp, LoadPattern, LoadCase,
    LoadCombination, ModalCase, GeneralProjectInfo, SiteInformation,
    SpectrumFunction, ResponseSpectrumCase, AutoSeismicTSC2018
)
from tools.s2k.units import UnitConverter


@dataclass
class LoadContext:
    """Tüm handler'ların veri topladığı merkezi kutu."""
    
    # Birim dönüştürücü
    units: UnitConverter = field(default_factory=UnitConverter)
    
    # Proje bilgileri
    project_info: Dict[str, GeneralProjectInfo | SiteInformation] = field(
        default_factory=lambda: {
            "gen": GeneralProjectInfo(),
            "site": SiteInformation(),
        }
    )

    
    # Tanımlar (malzeme, kesit, ...)
    materials: Dict[str, Material] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    auto_select_lists: Dict[str, list] = field(default_factory=dict)
    area_sections: Dict[str, dict] = field(default_factory=dict)
    area_thicknesses: Dict[str, float] = field(default_factory=dict)
    link_props: Dict[str, LinkProp] = field(default_factory=dict)
    
    # Yük ve Analiz tanımları
    load_patterns: Dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: Dict[str, ModalCase] = field(default_factory=dict)
    load_combos: Dict[str, LoadCombination] = field(default_factory=dict)
    
    # Dinamik & Deprem Tanımları
    spectrum_functions: Dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: Dict[str, ResponseSpectrumCase] = field(default_factory=dict)
    auto_seismics: Dict[str, AutoSeismicTSC2018] = field(default_factory=dict)
    
    # Kütle Kaynağı
    mass_source_map: Dict[str, float] = field(default_factory=dict)

    # Ham DataFrames (Geometri)
    df_joints: Optional[pd.DataFrame] = None
    df_restraints: Optional[pd.DataFrame] = None
    df_frame_conn: Optional[pd.DataFrame] = None
    df_area_conn: Optional[pd.DataFrame] = None
    df_link_conn: Optional[pd.DataFrame] = None
    df_frame_assign: Optional[pd.DataFrame] = None
    df_area_assign: Optional[pd.DataFrame] = None
    df_link_assign: Optional[pd.DataFrame] = None
    df_frame_release: Optional[pd.DataFrame] = None
    
    # Yük atamaları (ham DataFrame'ler)
    df_joint_loads: Optional[pd.DataFrame] = None
    df_frame_gravity: Optional[pd.DataFrame] = None
    df_frame_distributed: Optional[pd.DataFrame] = None
    df_frame_points: Optional[pd.DataFrame] = None
    df_frame_temperature: Optional[pd.DataFrame] = None
    df_area_uniform: Optional[pd.DataFrame] = None
    df_area_uniform_to_frame: Optional[pd.DataFrame] = None
    df_area_wind: Optional[pd.DataFrame] = None

    # Tepki Spektrumu ve Auto Seismic Tabloları (Ham)
    df_spec_gen: Optional[pd.DataFrame] = None
    df_spec_ass: Optional[pd.DataFrame] = None