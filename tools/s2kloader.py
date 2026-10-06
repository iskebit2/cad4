from domain.definition import AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad, AutoSeismicTSC2018, ComboItem, FrameDistributedLoad, FrameGravityLoad, GeneralProjectInfo, LinkProp, LinkPropLinear, LinkPropType, LoadCase, LoadCombination, LoadDirection, LoadPattern, MatType, Material, ModalCase, PointLoad, QuadDefinition, ResponseSpectrumCase, ResponseSpectrumLoadAssignment, Section, SectionCut, SectionCutDefinedBy, SectionCutResultType, SectionType, SiteInformation, SpectrumFunction, SpectrumSourceType, StaticLoadAssignment
from logging_config import CadLogger
logger = CadLogger.get(__name__)

import numpy as np
from typing import Optional, Callable, List, Tuple, Dict
from dataclasses import dataclass, field
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder
from domain.element import Node, Frame, Area, Link

import re
import pandas as pd
from pathlib import Path

# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları
- Material, Section, LinkProp, LoadPattern, LoadCase, Combo, Restraint
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
import uuid

from domain.sap_enums import (
    LOAD_PATTERN_TYPES,
    LOAD_CASE_TYPES,
    LOAD_CASE_DESIGN_TYPES,
    COMBOTYPE
)

# ============================================================================
# TBDY 2018 DEPREM TABLOLARI VE KATSAYILARI (LOOKUP TABLES)
# ============================================================================

# Tablo 2.1 – Kısa periyot bölgesi için Yerel Zemin Etki Katsayıları (Fs)
TSC_2018_FS_TABLE = {
    # Zemin Sınıfı: [(Ss_sınırı, Fs_değeri), ...] -> İnterpolasyon için
    "ZA": [(0.25, 0.8), (0.50, 0.8), (0.75, 0.8), (1.00, 0.8), (1.25, 0.8), (1.50, 0.8)],
    "ZB": [(0.25, 0.9), (0.50, 0.9), (0.75, 0.9), (1.00, 0.9), (1.25, 0.9), (1.50, 0.9)],
    "ZC": [(0.25, 1.3), (0.50, 1.3), (0.75, 1.2), (1.00, 1.2), (1.25, 1.2), (1.50, 1.2)],
    "ZD": [(0.25, 1.6), (0.50, 1.4), (0.75, 1.2), (1.00, 1.1), (1.25, 1.0), (1.50, 1.0)],
    "ZE": [(0.25, 2.4), (0.50, 1.7), (0.75, 1.3), (1.00, 1.1), (1.25, 0.9), (1.50, 0.8)],
}

# Tablo 2.2 – 1.0 saniye periyot için Yerel Zemin Etki Katsayıları (F1)
TSC_2018_F1_TABLE = {
    "ZA": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZB": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZC": [(0.10, 1.5), (0.20, 1.5), (0.30, 1.5), (0.40, 1.4), (0.50, 1.3), (0.60, 1.2)],
    "ZD": [(0.10, 2.4), (0.20, 2.2), (0.30, 2.0), (0.40, 1.8), (0.50, 1.6), (0.60, 1.5)],
    "ZE": [(0.10, 4.2), (0.20, 3.3), (0.30, 2.8), (0.40, 2.4), (0.50, 2.2), (0.60, 2.0)],
}

def get_tsc2018_site_coefficients(ss: float, s1: float, site_class: str) -> Tuple[float, float]:
    """
    TBDY 2018 Tablo 2.1 ve 2.2'ye göre doğrusal interpolasyon ile Fs ve F1 katsayılarını hesaplar.
    ZF sınıfında sahaya özel zemin davranışı analizi gerektiğinden varsayılan 1.0 döner.
    """
    site_class = site_class.upper()
    if site_class not in TSC_2018_FS_TABLE or site_class == "ZF":
        return 1.0, 1.0

    def interpolate(val: float, points: List[Tuple[float, float]]) -> float:
        if val <= points[0][0]:
            return points[0][1]
        if val >= points[-1][0]:
            return points[-1][1]
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if x0 <= val <= x1:
                return y0 + (y1 - y0) * (val - x0) / (x1 - x0)
        return 1.0

    fs = interpolate(ss, TSC_2018_FS_TABLE[site_class])
    f1 = interpolate(s1, TSC_2018_F1_TABLE[site_class])
    return fs, f1



from logging_config import CadLogger
logger = CadLogger.get(__name__)

import numpy as np
from typing import Optional, Callable, List, Tuple, Dict
from dataclasses import dataclass, field
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder
#from domain.definition import (AreaGravityLoad, AreaRefTemperatureLoad, AreaStrainLoad, AreaSurfacePressureLoad, AreaTemperatureLoad, AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad, AutoSeismicTSC2018, ComboItem, ComboType, ElementType, FrameDistributedLoad, FrameGravityLoad, FramePointLoad, FrameTemperatureLoad, GeneralProjectInfo, LinkProp, LinkPropLinear, LinkPropType, LoadCase, LoadCaseType, LoadCombination, LoadDirection, LoadPattern, LoadPatternType, LoadType, MatType, Material, ModalCase, ObjType, PointLoad, ResponseSpectrumCase, ResponseSpectrumLoadAssignment, Restraint, Section, SectionType, SiteInformation, SpectrumFunction, SpectrumSourceType, StaticLoadAssignment)
from domain.element import Node, Frame, Area, Link

import re
import pandas as pd
from pathlib import Path

class UnitConverter:
    """SAP2000 birim sistemi → yerel (N, mm, °C)."""

    LENGTH_FACTORS = {'MM': 1.0, 'CM': 10.0, 'M': 1000.0, 'IN': 25.4, 'FT': 304.8}
    FORCE_FACTORS = {
        'N': 1.0, 'KN': 1000.0, 'KG': 9.80665, 'KGF': 9.80665,
        'TON': 9806.65, 'KIP': 4448.22, 'LB': 4.44822,
    }

    def __init__(self, currunits_str: str = "N, mm, C"):
        self.length_scale = 1.0
        self.force_scale = 1.0
        self.temp_unit = "C"
        self.raw_string = currunits_str
        self.parse_units(currunits_str)

    def parse_units(self, currunits_str: str):
        self.raw_string = currunits_str.strip()
        parts = [p.strip().upper() for p in currunits_str.split(',')]
        if len(parts) >= 2:
            self.force_scale = self.FORCE_FACTORS.get(parts[0], 1.0)
            self.length_scale = self.LENGTH_FACTORS.get(parts[1], 1.0)
        if len(parts) >= 3:
            self.temp_unit = parts[2]

    # Dönüşüm metodları
    def L(self, v): return v * self.length_scale
    def F(self, v): return v * self.force_scale
    def M(self, v): return v * self.force_scale * self.length_scale
    def E(self, v): return v * self.force_scale / (self.length_scale ** 2)
    def w(self, v): return v * self.force_scale / self.length_scale
    def area_w(self, v): return v * self.force_scale / (self.length_scale ** 2)
    def acc(self, v): return v * self.length_scale

    def temp(self, v):
        """Sıcaklık farkı °C cinsine."""
        if self.temp_unit == "F":
            return v * (5.0 / 9.0)
        return v

    def temp_grad(self, v):
        """Sıcaklık gradyanı °C/mm."""
        return self.temp(v) / self.length_scale

    def __str__(self) -> str:
        """İnsan-okunabilir birim string'i."""
        return self.raw_string

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
    # Section Cuts
    section_cuts: Dict[str, float] = field(default_factory=dict)

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

    # Sectiom Cut Tabloları (Ham)
    df_section_cut_gen: Optional[pd.DataFrame] = None
    df_section_cut_quad: Optional[pd.DataFrame] = None


def get_color_from_string(color_str: str) -> Tuple[float, float, float]:
    """SAP2000 renk adı → RGB."""
    color_map = {
        'Red': (1.0, 0.0, 0.0), 'Green': (0.0, 1.0, 0.0), 'Blue': (0.0, 0.0, 1.0),
        'Yellow': (1.0, 1.0, 0.0), 'Cyan': (0.0, 1.0, 1.0), 'Magenta': (1.0, 0.0, 1.0),
        'White': (1.0, 1.0, 1.0), 'Black': (0.0, 0.0, 0.0),
        'Gray8Dark': (0.3, 0.3, 0.3), 'Gray8Light': (0.7, 0.7, 0.7),
    }
    return color_map.get(color_str, (0.8, 0.8, 0.8))


def parse_sap_mat_type(row) -> 'MatType':
    """SAP2000 material tipini tespit et."""

    raw_type = str(row.get('Type', '')).upper().strip()
    raw_grade = str(row.get('Grade', '')).upper().strip()
    raw_name = str(row.get('Material', '')).upper().strip()

    mapping = {
        "STEEL": MatType.STEEL, "CONCRETE": MatType.CONCRETE,
        "REBAR": MatType.REBAR, "TENDON": MatType.TENDON,
        "ALUMINUM": MatType.ALUMINUM, "COLDFORMED": MatType.COLDFORMED,
    }
    if raw_type in mapping:
        return mapping[raw_type]

    if raw_type == "OTHER":
        if any(k in raw_grade for k in ("WOOD", "TIMBER", "OSB")):
            return getattr(MatType, 'TIMBER', MatType.NODESIGN)
        if any(k in raw_name for k in ("TAS", "DUVAR", "MASONRY", "BRICK")):
            return getattr(MatType, 'MASONRY', MatType.NODESIGN)

    return MatType.NODESIGN


def map_sap_to_local_params(row) -> Tuple[SectionType, Dict[str, float]]:
    """SAP2000 kesit → yerel parametreler."""
    s_type = str(row.get('Shape', 'Rectangle')).strip()

    def sf(key, default=0.0, allow_zero=True):
        val = row.get(key)
        if val is None or str(val).strip() in ("", "None", "nan"):
            return default
        try:
            f = float(val)
            return f if (allow_zero or abs(f) > 1e-12) else default
        except (ValueError, TypeError):
            return default

    # Analiz parametreleri (her kesitte ortak)
    analysis = {
        'Area': sf('Area'), 'J': sf('TorsConst'),
        'I33': sf('I33'), 'I22': sf('I22'), 'I23': sf('I23'),
        'AS2': sf('AS2'), 'AS3': sf('AS3'),
        'S33Top': sf('S33Top'), 'S33Bot': sf('S33Bot'),
        'S22Left': sf('S22Left'), 'S22Right': sf('S22Right'),
        'Z33': sf('Z33'), 'Z22': sf('Z22'),
        'R33': sf('R33'), 'R22': sf('R22'),
        'Cw': sf('Cw'),
        'AMod': sf('AMod', 1.0), 'A2Mod': sf('A2Mod', 1.0), 'A3Mod': sf('A3Mod', 1.0),
        'JMod': sf('JMod', 1.0), 'I2Mod': sf('I2Mod', 1.0), 'I3Mod': sf('I3Mod', 1.0),
        'MMod': sf('MMod', 1.0), 'WMod': sf('WMod', 1.0),
    }

    if s_type in ("I/Wide Flange", "I"):
        geom = {"h": sf('t3', 200), "b": sf('t2', 100),
                "tw": sf('tw', 10), "tf": sf('tf', 14)}
        return SectionType.I, {**geom, **analysis}

    if s_type in ("Rectangle", "Rectangular"):
        return SectionType.RECT, {"h": sf('t3', 200), "b": sf('t2', 100), **analysis}

    if s_type in ("Pipe", "Circular", "Circle"):
        t3, tw = sf('t3', 120), sf('tw', 10)
        return SectionType.PIPE, {
            "ro": t3 / 2, "ri": max(0.1, (t3 - 2 * tw) / 2), "n": 24, **analysis,
        }

    if s_type in ("Channel", "C"):
        return SectionType.C, {
            "h": sf('t3', 100), "b": sf('t2', 80), "t": sf('tw', 6), **analysis,
        }

    if s_type in ("Angle", "L"):
        return SectionType.L, {
            "h": sf('t3', 100), "b": sf('t2', 80), "t": sf('tw', 8), **analysis,
        }

    if s_type in ("Tube", "Box"):
        return SectionType.TUBE, {
            "h": sf('t3', 200), "b": sf('t2', 100), "t": sf('tw', 10), **analysis,
        }

    return SectionType.RECT, {"h": 200.0, "b": 100.0, **analysis}


def safe_float(row, key, default=0.0, allow_zero=True):
    """Güvenli float dönüşümü."""
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan"):
        return default
    try:
        f = float(val)
        return f if (allow_zero or abs(f) > 1e-12) else default
    except (ValueError, TypeError):
        return default



def build_scene(ctx: LoadContext) -> Scene:
    builder = SceneBuilder()

    _register_definitions(builder, ctx)
    node_map = _create_nodes(builder, ctx)
    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    area_map, n_areas = _create_areas(builder, ctx, node_map)
    n_links = _create_links(builder, ctx, node_map)
    _assign_loads(ctx, node_map, frame_map, area_map)

    logger.info(
        f"[Builder] {len(node_map)} node, {n_frames} frame, "
        f"{n_areas} area, {n_links} link"
    )
    scene = builder.scene
    scene.units = str(ctx.units)
    # scene.project_info = ctx.project_info
    return scene


def _register_definitions(builder: SceneBuilder, ctx: LoadContext):
    def_mgr = builder.def_mgr

    def_mgr.project_info = ctx.project_info
    for mat in ctx.materials.values():
        def_mgr.add_material(mat)
    for sec in ctx.sections.values():
        def_mgr.add_section(sec)
    for prop in ctx.link_props.values():
        def_mgr.add_link_prop(prop)

    def_mgr.load_patterns = ctx.load_patterns
    def_mgr.load_cases = ctx.load_cases
    def_mgr.modal_cases = ctx.modal_cases
    def_mgr.combinations = ctx.load_combos
    def_mgr.mass_source_map = dict(ctx.mass_source_map)

    # Dinamik tanımların aktarımı
    def_mgr.spectrum_functions = ctx.spectrum_functions
    def_mgr.response_spectrum_cases = ctx.response_spectrum_cases
    def_mgr.auto_seismics = ctx.auto_seismics

    # Section cut
    def_mgr.section_cuts = ctx.section_cuts



def _create_nodes(builder: SceneBuilder, ctx: LoadContext) -> Dict[str, Node]:
    node_map: Dict[str, Node] = {}
    if ctx.df_joints is None or ctx.df_joints.empty:
        return node_map

    restraints = _parse_restraints(ctx.df_restraints)

    for _, row in ctx.df_joints.iterrows():
        joint_id = str(row.get('Joint', '')).strip()
        if not joint_id:
            continue

        try:
            x = ctx.units.L(float(row.get('XorR', row.get('X', 0))))
            y = ctx.units.L(float(row.get('Y', 0)))
            z = ctx.units.L(float(row.get('Z', 0)))
        except (ValueError, TypeError):
            logger.warning(f"Node {joint_id}: geçersiz koordinat")
            continue

        node = builder.create_node(
            x, y, z,
            label=f"N{joint_id}",
            restraint=restraints.get(joint_id),
        )
        node_map[joint_id] = node

    return node_map


def _parse_restraints(df: pd.DataFrame) -> Dict[str, dict]:
    if df is None or df.empty:
        return {}

    dof_map = {'U1': 'ux', 'U2': 'uy', 'U3': 'uz',
               'R1': 'rx', 'R2': 'ry', 'R3': 'rz'}

    restraints = {}
    for _, row in df.iterrows():
        joint_id = str(row.get('Joint', '')).strip()
        if not joint_id:
            continue

        rel = {
            our: True for sap, our in dof_map.items()
            if str(row.get(sap, '')).strip().upper() == 'YES'
        }
        if rel:
            restraints[joint_id] = rel

    return restraints


def _create_frames(builder: SceneBuilder, ctx: LoadContext, node_map: Dict[str, Node]) -> Tuple[Dict[str, Frame], int]:
    frame_map: Dict[str, Frame] = {}
    if ctx.df_frame_conn is None or ctx.df_frame_conn.empty:
        return frame_map, 0

    # Context parametresi dâhil edildi
    frame_assign = _parse_frame_assign(ctx.df_frame_assign, ctx)
    frame_release = _parse_frame_release(ctx.df_frame_release)
    fallback = _get_fallback_section(builder, ctx)

    count = 0
    for _, row in ctx.df_frame_conn.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        joint_i = str(row.get('JointI', '')).strip()
        joint_j = str(row.get('JointJ', '')).strip()

        if not frame_id or joint_i not in node_map or joint_j not in node_map:
            continue

        sect_name, rotation = frame_assign.get(frame_id, ("", 0.0))
        if sect_name not in ctx.sections:
            sect_name = fallback

        try:
            frame = builder.create_frame(
                node_map[joint_i],
                node_map[joint_j],
                sect_name,
                rotation_deg=rotation,
                label=f"F{frame_id}",
            )

            if frame_id in frame_release:
                frame.release_i = frame_release[frame_id]['i']
                frame.release_j = frame_release[frame_id]['j']

            frame_map[frame_id] = frame
            count += 1
        except ValueError as e:
            logger.warning(f"Frame {frame_id}: {e}")

    return frame_map, count


def _parse_frame_assign(df: pd.DataFrame, ctx: LoadContext = None) -> Dict[str, Tuple[str, float]]:
    if df is None or df.empty or 'Frame' not in df.columns:
        return {}

    result = {}
    for _, row in df.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        if not frame_id:
            continue

        sect = (str(row.get('AnalSect', '')).strip() or str(row.get('Section', '')).strip())

        if ctx and sect in ctx.auto_select_lists:
            members = ctx.auto_select_lists[sect]
            if members:
                mid_idx = len(members) // 2
                original = sect
                sect = members[mid_idx]
                logger.debug(f"Frame {frame_id}: '{original}' → '{sect}' (liste ortası)")

        try:
            rotation = float(row.get('Angle', 0.0))
        except (ValueError, TypeError):
            rotation = 0.0

        result[frame_id] = (sect, rotation)

    return result


def _parse_frame_release(df: pd.DataFrame) -> Dict[str, dict]:
    if df is None or df.empty or 'Frame' not in df.columns:
        return {}

    i_cols = {'R1': 'PI', 'R2': 'V2I', 'R3': 'V3I', 'R4': 'TI', 'R5': 'M2I', 'R6': 'M3I'}
    j_cols = {'R1': 'PJ', 'R2': 'V2J', 'R3': 'V3J', 'R4': 'TJ', 'R5': 'M2J', 'R6': 'M3J'}

    releases = {}
    for _, row in df.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        if not frame_id:
            continue

        rel_i = {code: str(row.get(col, 'No')).strip().upper() == 'YES' for code, col in i_cols.items()}
        rel_j = {code: str(row.get(col, 'No')).strip().upper() == 'YES' for code, col in j_cols.items()}

        if any(rel_i.values()) or any(rel_j.values()):
            releases[frame_id] = {'i': rel_i, 'j': rel_j}

    return releases


def _get_fallback_section(builder: SceneBuilder, ctx: LoadContext) -> str:
    if ctx.sections:
        return next(iter(ctx.sections.keys()))

    default = Section(
        name="DEFAULT",
        profile_type=SectionType.RECT,
        profile_params={"h": 200.0, "b": 100.0},
        color=(0.5, 0.5, 0.5),
    )
    builder.def_mgr.add_section(default)
    ctx.sections["DEFAULT"] = default
    return "DEFAULT"


def _create_areas(builder: SceneBuilder, ctx: LoadContext, node_map: Dict[str, Node]) -> Tuple[Dict[str, Area], int]:
    area_map = {}
    if ctx.df_area_conn is None or ctx.df_area_conn.empty:
        return area_map, 0

    area_assign = _parse_area_assign(ctx.df_area_assign)

    for _, row in ctx.df_area_conn.iterrows():
        area_id = str(row.get('Area', '')).strip()

        joints = [node_map[j] for i in range(1, 5) if (j := str(row.get(f'Joint{i}', '')).strip()) in node_map]
        if len(joints) < 3:
            continue

        section_name = area_assign.get(area_id, "")
        section_data = ctx.area_sections.get(section_name, {})
        thickness = ctx.units.L(section_data.get("thickness", 100.0))

        area = builder.create_area(joints, thickness=thickness, label=f"A{area_id}")
        area.material = section_data.get("material")
        area.section_name = section_name

        area_map[area_id] = area

    return area_map, len(area_map)


def _parse_area_assign(df: pd.DataFrame) -> Dict[str, str]:
    if df is None or df.empty or 'Area' not in df.columns:
        return {}

    result = {}
    for _, row in df.iterrows():
        area_id = str(row.get('Area', '')).strip()
        if not area_id:
            continue
        result[area_id] = str(row.get('Section', '')).strip()

    return result

def _parse_link_assign(df) -> Dict[str, str]:
    if df is None or df.empty or 'Link' not in df.columns:
        return {}
    result = {}
    for _, r in df.iterrows():
        lid = str(r.get('Link', '')).strip()
        if not lid:
            continue
        prop = str(r.get('Prop', r.get('LinkProp', r.get('PropName', '')))).strip()
        if prop:
            result[lid] = prop
    return result

def _create_links(builder, ctx, node_map):
    if ctx.df_link_conn is None or ctx.df_link_conn.empty:
        return 0

    prop_map = _parse_link_assign(ctx.df_link_assign)
    default_prop = next(iter(ctx.link_props), None)

    if default_prop is None:
        logger.warning("[Links] Hiç link property yok, link'ler atlanıyor")
        return 0

    count = 0
    for _, row in ctx.df_link_conn.iterrows():
        link_id = str(row.get('Link', '')).strip()
        joint_i = str(row.get('JointI', '')).strip()
        joint_j = str(row.get('JointJ', '')).strip()
        if not link_id or joint_i not in node_map or joint_j not in node_map:
            continue

        prop_name = prop_map.get(link_id, default_prop)

        try:
            builder.create_link(
                node_map[joint_i], node_map[joint_j],
                prop_name=prop_name, label=f"L{link_id}",
            )
            count += 1
        except Exception as e:
            logger.warning(f"Link {link_id}: {e}")

    return count


def _assign_loads(ctx: LoadContext, node_map: Dict[str, Node], frame_map: Dict[str, Frame], area_map: Dict[str, Area]):
    _load_joint_loads(ctx, node_map)
    _load_frame_loads(ctx, frame_map)
    _load_area_loads(ctx, area_map)


def _parse_direction(dir_str: str) -> LoadDirection:
    d = str(dir_str).strip().upper()
    mapping = {
        "1": LoadDirection.LOCAL_1, "LOCAL1": LoadDirection.LOCAL_1,
        "2": LoadDirection.LOCAL_2, "LOCAL2": LoadDirection.LOCAL_2,
        "3": LoadDirection.LOCAL_3, "LOCAL3": LoadDirection.LOCAL_3,
        "X": LoadDirection.GLOBAL_X, "GX": LoadDirection.GLOBAL_X,
        "Y": LoadDirection.GLOBAL_Y, "GY": LoadDirection.GLOBAL_Y,
        "Z": LoadDirection.GLOBAL_Z, "GZ": LoadDirection.GLOBAL_Z,
        "GRAV": LoadDirection.GRAVITY, "GRAVITY": LoadDirection.GRAVITY,
        "PX": LoadDirection.PROJECTED_X,
        "PY": LoadDirection.PROJECTED_Y,
        "PZ": LoadDirection.PROJECTED_Z,
    }
    return mapping.get(d, LoadDirection.GRAVITY)


def _load_joint_loads(ctx: LoadContext, node_map: Dict[str, Node]):
    df = ctx.df_joint_loads
    if df is None or df.empty:
        return

    for _, r in df.iterrows():
        j_id = str(r.get('Joint', '')).strip()
        node = node_map.get(j_id)
        if not node:
            continue

        node.loads.append(PointLoad(
            pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
            fx=ctx.units.F(safe_float(r, 'F1')),
            fy=ctx.units.F(safe_float(r, 'F2')),
            fz=ctx.units.F(safe_float(r, 'F3')),
            mx=ctx.units.M(safe_float(r, 'M1')),
            my=ctx.units.M(safe_float(r, 'M2')),
            mz=ctx.units.M(safe_float(r, 'M3')),
        ))


def _load_frame_loads(ctx: LoadContext, frame_map: Dict[str, Frame]):
    df_g = ctx.df_frame_gravity
    if df_g is not None and not df_g.empty:
        for _, r in df_g.iterrows():
            frame = frame_map.get(str(r.get('Frame', '')).strip())
            if frame:
                frame.gravity_loads.append(FrameGravityLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    multiplier_x=safe_float(r, 'MultiplierX'),
                    multiplier_y=safe_float(r, 'MultiplierY'),
                    multiplier_z=safe_float(r, 'MultiplierZ'),
                ))

    df_d = ctx.df_frame_distributed
    if df_d is not None and not df_d.empty:
        for _, r in df_d.iterrows():
            frame = frame_map.get(str(r.get('Frame', '')).strip())
            if not frame:
                continue

            ftype = str(r.get('Type', 'Force')).upper()
            is_rel = "REL" in str(r.get('DistType', 'RelDist')).upper()

            d1 = safe_float(r, 'RelDistA') if is_rel else ctx.units.L(safe_float(r, 'AbsDistA'))
            d2 = safe_float(r, 'RelDistB') if is_rel else ctx.units.L(safe_float(r, 'AbsDistB'))

            p1_raw = safe_float(r, 'FOverLA')
            p2_raw = safe_float(r, 'FOverLB', default=p1_raw)

            if ftype == 'FORCE':
                p1, p2 = ctx.units.w(p1_raw), ctx.units.w(p2_raw)
            else:
                p1 = ctx.units.M(p1_raw) / ctx.units.length_scale
                p2 = ctx.units.M(p2_raw) / ctx.units.length_scale

            frame.dist_loads.append(FrameDistributedLoad(
                pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                force_or_moment=ftype,
                direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                p1=p1, p2=p2, d1=d1, d2=d2, is_relative=is_rel,
            ))


def _load_area_loads(ctx: LoadContext, area_map: Dict[str, Area]):
    df_u = ctx.df_area_uniform
    if df_u is not None and not df_u.empty:
        for _, r in df_u.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                area.uniform_loads.append(AreaUniformLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                    value=ctx.units.area_w(safe_float(r, 'UnifLoad', 0.0)),
                ))

    df_utf = ctx.df_area_uniform_to_frame
    if df_utf is not None and not df_utf.empty:
        for _, r in df_utf.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                area.uniform_to_frame_loads.append(AreaUniformToFrameLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                    value=ctx.units.area_w(safe_float(r, 'UnifLoad', 0.0)),
                    dist_type=str(r.get('DistType', 'One way')).strip(),
                ))

    df_w = ctx.df_area_wind
    if df_w is not None and not df_w.empty:
        for _, r in df_w.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                is_ww = str(r.get('Windward', 'Yes')).strip().upper() == 'YES'
                area.wind_pressures.append(AreaWindPressureLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    cp=safe_float(r, 'Cp'),
                    windward=is_ww,
                    dist_type=str(r.get('DistType', 'To Joints')).strip(),
                ))



def handle_program_control(ctx: LoadContext, df: pd.DataFrame):
    """PROGRAM CONTROL → birim ayarları."""
    if 'CurrUnits' in df.columns:
        units_str = str(df.iloc[0]['CurrUnits'])
        ctx.units = UnitConverter(units_str)
        logger.info(f"[Units] {units_str}")


def handle_project_information(ctx: LoadContext, df: pd.DataFrame):
    """PROJECT INFORMATION → proje bilgileri."""
    info = {}
    for _, row in df.iterrows():
        key = str(row.get('Item', '')).strip()
        val = str(row.get('Data', '')).strip()
        if key:
            info[key] = val

    ctx.project_info['gen'] = GeneralProjectInfo(
        company_name=info.get('Company Name', ''),
        client_name=info.get('Client Name', ''),
        project_name=info.get('Project Name', 'CAD Model'),
        project_number=info.get('Project Number', ''),
        model_name=info.get('Model Name', ''),
        model_description=info.get('Model Description', ''),
        revision_number=info.get('Revision Number', 'R0'),
        frame_type=info.get('Frame Type', ''),
        engineer=info.get('Engineer', ''),
        checker=info.get('Checker', ''),
        supervisor=info.get('Supervisor', ''),
        issue_code=info.get('Issue Code', ''),
        design_code=info.get('Design Code', ''),
    )
    ctx.project_info['site'] = SiteInformation(
            cadastral_info='--- / --',
            live_load_factor= 0.3,
            date='xx.xx.20xx',
            soil_class='ZD',
            subgrade_modulus_kn_m3 = 1500,

        )


# ============================================================
# 3. MALZEME
# ============================================================

def handle_material_props(ctx: LoadContext, df: pd.DataFrame):
    """MATERIAL PROPERTIES 01 - GENERAL."""
    for _, row in df.iterrows():
        name = str(row.get('Material', '')).strip()
        if not name:
            continue

        mat_type = parse_sap_mat_type(row)
        color = get_color_from_string(row.get('Color', 'Gray8Dark'))

        ctx.materials[name] = Material(
            name=name,
            mat_type=mat_type,
            color=color,
        )


def handle_material_mech(ctx: LoadContext, df: pd.DataFrame):
    """MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('Material', '')).strip()
        if not name:
            continue

        if name not in ctx.materials:
            ctx.materials[name] = Material(name=name)

        mat = ctx.materials[name]
        e1 = safe_float(row, 'E1', 2.0e8)
        mat.E1 = e1
        mat.E2 = safe_float(row, 'E2', e1)
        mat.E3 = safe_float(row, 'E3', e1)
        mat.G12 = safe_float(row, 'G12', 7.7e7)
        mat.G13 = safe_float(row, 'G13', mat.G12)
        mat.G23 = safe_float(row, 'G23', mat.G12)
        mat.nu12 = safe_float(row, 'U12', 0.3)
        mat.nu13 = safe_float(row, 'U13', mat.nu12)
        mat.nu23 = safe_float(row, 'U23', mat.nu12)
        mat.density = safe_float(row, 'UnitMass', 7.85e-9)


# ============================================================
# 4. KESİTLER
# ============================================================

def handle_frame_props(ctx: LoadContext, df: pd.DataFrame):
    """FRAME SECTION PROPERTIES 01 - GENERAL."""
    if df.empty:
        return

    name_col = next((c for c in ('SectionName', 'Section', 'Name') if c in df.columns), None)
    if name_col is None:
        logger.error("Kesit isim kolonu bulunamadı")
        return

    skipped = 0
    loaded = 0

    for _, row in df.iterrows():
        sect_name = str(row.get(name_col, '')).strip()
        if not sect_name:
            continue

        shape = str(row.get('Shape', '')).strip()
        if 'auto select' in shape.lower():
            skipped += 1
            continue

        s_type, s_params = map_sap_to_local_params(row)
        color = get_color_from_string(row.get('Color', 'Gray8Dark'))

        mat_name = str(row.get('Material', '')).strip()
        mat_obj = ctx.materials.get(mat_name) if mat_name and mat_name.lower() != 'nan' else None

        if mat_obj is None and mat_name and mat_name.lower() != 'nan':
            mat_obj = Material(name=mat_name, mat_type=MatType.STEEL)
            ctx.materials[mat_name] = mat_obj
            logger.warning(f"Kesit '{sect_name}': malzeme '{mat_name}' bulunamadı, geçici oluşturuldu")

        ctx.sections[sect_name] = Section(
            name=sect_name,
            profile_type=s_type,
            profile_params=s_params,
            material=mat_obj,
            color=color,
        )
        loaded += 1

    if skipped > 0:
        logger.info(f"[Sections] {skipped} Auto Select listesi atlandı, {loaded} gerçek kesit yüklendi")


def handle_auto_select_lists(ctx: LoadContext, df: pd.DataFrame):
    """FRAME SECTION PROPERTIES 04 - AUTO SELECT."""
    if df.empty:
        return

    for _, row in df.iterrows():
        list_name = str(row.get('ListName', '')).strip()
        member = str(row.get('SectionName', '')).strip()

        if not list_name or not member:
            continue

        if list_name not in ctx.auto_select_lists:
            ctx.auto_select_lists[list_name] = []

        ctx.auto_select_lists[list_name].append(member)

    logger.info(f"[AutoSelect] {len(ctx.auto_select_lists)} liste yüklendi")


def handle_area_props(ctx: LoadContext, df: pd.DataFrame):
    """AREA SECTION PROPERTIES."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('Section', '')).strip()
        if not name:
            continue

        thickness = safe_float(row, 'Thickness', 100.0)
        ctx.area_thicknesses[name] = thickness

        mat_name = str(row.get('Material', '')).strip()
        mat_obj = ctx.materials.get(mat_name) if mat_name else None

        if mat_obj is None and mat_name:
            mat_obj = Material(name=mat_name)
            ctx.materials[mat_name] = mat_obj

        ctx.area_sections[name] = {
            "material": mat_obj,
            "thickness": thickness,
            "area_type": str(row.get('AreaType', 'Shell')).strip(),
            "type": str(row.get('Type', 'Shell-Thin')).strip(),
            "color": get_color_from_string(row.get('Color', 'Gray8Dark')),
        }


def handle_link_props(ctx: LoadContext, df: pd.DataFrame):
    """LINK PROPERTY DEFINITIONS 01 - GENERAL."""
    if df.empty:
        return

    for _, row in df.iterrows():
        # LinkProp adı: 'Link' veya 'LinkProp' veya 'Name'
        name = str(
            row.get('Link', row.get('LinkProp', row.get('Name', '')))
        ).strip()
        if not name:
            continue

        if name in ctx.link_props:
            logger.warning(f"LinkProp '{name}' zaten var, atlanıyor")
            continue

        # ✅ Enum ile tip parse
        link_type_str = str(row.get('LinkType', 'LINEAR')).strip()
        prop_type = LinkPropType.from_sap(link_type_str)

        # ✅ Alt sınıf seçimi (enum ile)
        prop = _make_link_prop(name, prop_type)

        ctx.link_props[name] = prop
        logger.debug(
            f"LinkProp '{name}': SAP='{link_type_str}' → {prop_type.name}"
        )


def _make_link_prop(name: str, prop_type: LinkPropType):
    """LinkPropType → doğru LinkProp alt sınıfı."""
    factory = {
        LinkPropType.LINEAR: LinkPropLinear,
        LinkPropType.DAMPER: LinkPropLinear,      # şimdilik
        LinkPropType.GAP: LinkPropLinear,          # şimdilik
        LinkPropType.HOOK: LinkPropLinear,         # şimdilik
        LinkPropType.PLASTIC_WEN: LinkPropLinear,  # şimdilik
        LinkPropType.ISOLATOR1: LinkPropLinear,    # şimdilik
        LinkPropType.ISOLATOR2: LinkPropLinear,    # şimdilik
        LinkPropType.MULTILINEAR_ELASTIC: LinkPropLinear,
        LinkPropType.MULTILINEAR_PLASTIC: LinkPropLinear,
        LinkPropType.ISOLATOR3: LinkPropLinear,
    }
    cls = factory.get(prop_type, LinkPropLinear)
    return cls(name=name, prop_type=prop_type)

# ============================================================
# 5. GEOMETRİ & ATAMALAR (Ham DataFrames)
# ============================================================

def handle_joints(ctx: LoadContext, df: pd.DataFrame): ctx.df_joints = df
def handle_joint_restraints(ctx: LoadContext, df: pd.DataFrame): ctx.df_restraints = df
def handle_frame_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_conn = df
def handle_area_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_conn = df
def handle_link_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_link_conn = df
def handle_frame_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_assign = df
def handle_area_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_assign = df
def handle_link_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_link_assign = df
def handle_frame_releases(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_release = df


# ============================================================
# 6. YÜK TANIMLARI & ANALİZ CASE'LERİ
# ============================================================

def handle_load_patterns(ctx: LoadContext, df: pd.DataFrame):
    """LOAD PATTERN DEFINITIONS."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('LoadPat', '')).strip()
        if not name:
            continue

        ctx.load_patterns[name] = LoadPattern(
            name=name,
            design_type=str(row.get('DesignType', 'Dead')).strip(),
            self_wt_mult=safe_float(row, 'SelfWtMult', 0.0),

        )


def handle_load_cases(ctx: LoadContext, df: pd.DataFrame):
    """LOAD CASE DEFINITIONS."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('Case', '')).strip()
        if not name:
            continue

        run_str = str(row.get('RunCase', 'Yes')).strip().upper()
        ctx.load_cases[name] = LoadCase(
            name=name,
            case_type=str(row.get('Type', 'LinStatic')).strip(),
            initial_cond=str(row.get('InitialCond', 'Zero')).strip(),
            design_type=str(row.get('DesignType', 'Dead')).strip(),
            design_act=str(row.get('DesignAct', 'Non-Composite')).strip(),
            auto_type=str(row.get('AutoType', 'None')).strip(),
            run_case=(run_str == 'YES'),

        )


def handle_static_assignments(ctx: LoadContext, df: pd.DataFrame):
    """CASE - STATIC 1 - LOAD ASSIGNMENTS."""
    if df.empty:
        return

    for _, row in df.iterrows():
        case_name = str(row.get('Case', '')).strip()
        case = ctx.load_cases.get(case_name)
        if not case:
            continue

        case.static_assignments.append(StaticLoadAssignment(
            load_type=str(row.get('LoadType', 'Load pattern')).strip(),
            load_name=str(row.get('LoadName', '')).strip(),
            load_sf=safe_float(row, 'LoadSF', 1.0),
        ))


def handle_modal_cases(ctx: LoadContext, df: pd.DataFrame):
    """CASE - MODAL 1 - GENERAL."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('Case', '')).strip()
        if not name:
            continue

        ctx.modal_cases[name] = ModalCase(
            name=name,
            mode_type=str(row.get('ModeType', 'Eigen')).strip(),
            max_num_modes=int(safe_float(row, 'MaxNumModes', 12)),
            min_num_modes=int(safe_float(row, 'MinNumModes', 1)),
            eigen_shift=safe_float(row, 'EigenShift', 0.0),
            eigen_cutoff=safe_float(row, 'EigenCutoff', 0.0),
            eigen_tol=safe_float(row, 'EigenTol', 1e-9),
            auto_shift=(str(row.get('AutoShift', 'Yes')).strip().upper() == 'YES'),
        )


def handle_combinations(ctx: LoadContext, df: pd.DataFrame):
    """COMBINATION DEFINITIONS."""
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('ComboName', '')).strip()
        if not name:
            continue

        if name not in ctx.load_combos:
            auto_des_str = str(row.get('AutoDesign', 'No')).strip().upper()
            ctx.load_combos[name] = LoadCombination(
                name=name,
                combo_type=str(row.get('ComboType', 'Linear Add')).strip(),
                auto_design=(auto_des_str == 'YES'),

            )

        case_or_pat = str(row.get('CaseName', '')).strip()
        if case_or_pat:
            ctx.load_combos[name].items.append(ComboItem(
                case_or_pattern_name=case_or_pat,
                scale_factor=safe_float(row, 'ScaleFactor', 1.0),
            ))


def handle_mass_source(ctx: LoadContext, df: pd.DataFrame):
    """MASS SOURCE."""
    if df.empty:
        return

    for _, row in df.iterrows():
        pattern = str(row.get('LoadPat', '')).strip()
        if not pattern:
            continue

        ctx.mass_source_map[pattern] = safe_float(row, 'Multiplier', 1.0)

    logger.info(f"[MassSource] {len(ctx.mass_source_map)} pattern")


# ============================================================
# 7. YÜKLER (Ham DataFrames)
# ============================================================

def handle_joint_loads(ctx: LoadContext, df: pd.DataFrame): ctx.df_joint_loads = df
def handle_frame_gravity(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_gravity = df
def handle_frame_distributed(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_distributed = df
def handle_frame_points(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_points = df
def handle_frame_temperature(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_temperature = df
def handle_area_uniform(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_uniform = df
def handle_area_uniform_to_frame(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_uniform_to_frame = df
def handle_area_wind(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_wind = df


# ============================================================
# 8. DİNAMİK / SPEKTRUM & AUTO SEISMIC PARSER
# ============================================================

def handle_spectrum_functions_TSC(ctx: LoadContext, df: pd.DataFrame):
    """FUNCTION - RESPONSE SPECTRUM - TSC-2018."""
    if df.empty: return
    for _, r in df.iterrows():
        name = str(r.get('Name', '')).strip()
        if not name: continue

        ctx.spectrum_functions[name] = SpectrumFunction(
            name=name,
            source_type=SpectrumSourceType.TSC_2018,
            damp=safe_float(r, 'FuncDamp', 0.05),
            spec_dir=str(r.get('SpecDir', 'Horizontal')).strip(),
            ss=safe_float(r, 'Ss'),
            s1=safe_float(r, 'S1'),
            tl=safe_float(r, 'TL', 6.0),
            site_class=str(r.get('SiteClass', 'ZD')).strip(),
            fs=safe_float(r, 'Fs', 1.0),
            f1=safe_float(r, 'F1', 1.0),
            r_coeff=safe_float(r, 'R', 1.0),
            d_coeff=safe_float(r, 'D', 1.0),
            i_coeff=safe_float(r, 'I', 1.0)
        )


def handle_spectrum_functions_file(ctx: LoadContext, df: pd.DataFrame):
    """FUNCTION - RESPONSE SPECTRUM - FROM FILE."""
    if df.empty: return
    for _, r in df.iterrows():
        name = str(r.get('Name', '')).strip()
        if not name: continue

        ctx.spectrum_functions[name] = SpectrumFunction(
            name=name,
            source_type=SpectrumSourceType.FROM_FILE,
            damp=safe_float(r, 'FuncDamp', 0.05),
            data_type=str(r.get('DataType', 'Period vs Accel')).strip(),
            file_path=str(r.get('FileName', '')).strip()
        )


def handle_spectrum_functions_user(ctx: LoadContext, df: pd.DataFrame):
    """FUNCTION - RESPONSE SPECTRUM - USER."""
    if df.empty: return
    for _, r in df.iterrows():
        name = str(r.get('Name', '')).strip()
        if not name: continue

        p_val = safe_float(r, 'Period')
        a_val = safe_float(r, 'Accel')

        if name not in ctx.spectrum_functions:
            ctx.spectrum_functions[name] = SpectrumFunction(
                name=name,
                source_type=SpectrumSourceType.USER,
                damp=safe_float(r, 'FuncDamp', 0.05)
            )
        ctx.spectrum_functions[name].points.append((p_val, a_val))


def handle_response_spectrum_gen(ctx: LoadContext, df: pd.DataFrame):
    """CASE - RESPONSE SPECTRUM 1 - GENERAL."""
    ctx.df_spec_gen = df


def handle_response_spectrum_assign(ctx: LoadContext, df: pd.DataFrame):
    """CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS."""
    ctx.df_spec_ass = df
    _process_response_spectrum_cases(ctx)


def _process_response_spectrum_cases(ctx: LoadContext):
    """Genel ve atama tabloları yüklendiğinde Spektrum Case nesnelerini türetir."""
    if ctx.df_spec_gen is None or ctx.df_spec_gen.empty:
        return

    cases: Dict[str, ResponseSpectrumCase] = {}

    for _, r in ctx.df_spec_gen.iterrows():
        c_name = str(r.get('Case', '')).strip()
        if not c_name: continue

        cases[c_name] = ResponseSpectrumCase(
            name=c_name,
            modal_combo=str(r.get('ModalCombo', 'CQC')).strip(),
            dir_combo=str(r.get('DirCombo', 'SRSS')).strip(),
            damping=safe_float(r, 'ConstDamp', 0.05),
            eccentricity=safe_float(r, 'EccenRatio', 0.0)
        )

    if ctx.df_spec_ass is not None and not ctx.df_spec_ass.empty:
        for _, r in ctx.df_spec_ass.iterrows():
            c_name = str(r.get('Case', '')).strip()
            if case_obj := cases.get(c_name):
                raw_sf = safe_float(r, 'TransAccSF', 9810.0)
                scaled_sf = ctx.units.acc(raw_sf)

                assignment = ResponseSpectrumLoadAssignment(
                    load_name=str(r.get('LoadName', 'U1')).strip(),
                    function_name=str(r.get('Function', '')).strip(),
                    angle=safe_float(r, 'Angle', 0.0),
                    sf=scaled_sf
                )
                case_obj.assignments.append(assignment)

    ctx.response_spectrum_cases = cases


def handle_auto_seismic(ctx: LoadContext, df: pd.DataFrame):
    """AUTO SEISMIC - TSC-2018."""
    if df.empty: return
    for _, r in df.iterrows():
        pat_name = str(r.get('LoadPat', '')).strip()
        if not pat_name: continue

        ctx.auto_seismics[pat_name] = AutoSeismicTSC2018(
            load_pattern=pat_name,
            direction=str(r.get('Dir', 'X')).strip(),
            percent_ecc=safe_float(r, 'PercentEcc', 0.05),
            period_calc=str(r.get('PeriodCalc', 'Prog Calc')).strip(),
            ct_and_x=str(r.get('CtAndX', '0.10m, 0.75')).strip(),
            r_coeff=safe_float(r, 'R', 2.5),
            d_coeff=safe_float(r, 'D', 2.5),
            i_coeff=safe_float(r, 'I', 1.2),
            ss=safe_float(r, 'Ss'),
            s1=safe_float(r, 'S1'),
            tl=safe_float(r, 'TL', 8.0),
            site_class=str(r.get('SiteClass', 'ZC')).strip(),
            fs=safe_float(r, 'Fs', 1.0),
            f1=safe_float(r, 'F1', 1.0)
        )

# 9 Section Cuts
def handle_section_cuts_gen(ctx: LoadContext, df: pd.DataFrame):
    """SECTION CUTS 1 - GENERAL."""
    if df.empty:
        return
    if not hasattr(ctx, 'section_cuts'):
        ctx.section_cuts = {}

    for _, row in df.iterrows():
        name = str(row.get('CutName', '')).strip()
        if not name:
            continue

        # Parse DefinedBy enum safely
        defined_by_str = str(row.get('DefinedBy', 'Quad')).strip()
        try:
            defined_by = SectionCutDefinedBy(defined_by_str)
        except ValueError:
            defined_by = SectionCutDefinedBy.QUAD

        # Parse ResultType enum safely
        result_type_str = str(row.get('ResultType', 'Analysis')).strip()
        try:
            result_type = SectionCutResultType(result_type_str)
        except ValueError:
            result_type = SectionCutResultType.ANALYSIS

        ctx.section_cuts[name] = SectionCut(
            name=name,
            defined_by=defined_by,
            group=str(row.get('Group', 'All')).strip(),
            result_type=result_type,
            default_loc=(str(row.get('DefaultLoc', 'Yes')).strip().upper() == 'YES'),
            global_x=ctx.units.L(safe_float(row, 'GlobalX')),
            global_y=ctx.units.L(safe_float(row, 'GlobalY')),
            global_z=ctx.units.L(safe_float(row, 'GlobalZ')),
            angle_a=safe_float(row, 'AngleA'),
            angle_b=safe_float(row, 'AngleB'),
            angle_c=safe_float(row, 'AngleC'),
            elem_side=str(row.get('ElemSide', 'Positive')).strip(),
            quad=QuadDefinition(points=[])
        )


def handle_section_cuts_quad(ctx: LoadContext, df: pd.DataFrame):
    """SECTION CUTS 3 - QUADRILATERAL DEFINITIONS."""
    if df.empty:
        return
    if not hasattr(ctx, 'section_cuts'):
        ctx.section_cuts = {}

    for _, row in df.iterrows():
        name = str(row.get('SectionCut', '')).strip()
        if not name:
            continue

        if name not in ctx.section_cuts:
            # If general definitions have not loaded yet, create a placeholder
            ctx.section_cuts[name] = SectionCut(name=name, quad=QuadDefinition(points=[]))

        x = ctx.units.L(safe_float(row, 'X'))
        y = ctx.units.L(safe_float(row, 'Y'))
        z = ctx.units.L(safe_float(row, 'Z'))

        sc_obj = ctx.section_cuts[name]
        if sc_obj.quad is None:
            sc_obj.quad = QuadDefinition(points=[])
        sc_obj.quad.points.append((x, y, z))

PRIORITY = {
    # 1. Program ve birimler
    "PROGRAM CONTROL":                                  10,
    "PROJECT INFORMATION":                              11,

    # 2. Malzemeler
    "MATERIAL PROPERTIES 01 - GENERAL":                 20,
    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": 21,

    # 3. Kesitler
    "FRAME SECTION PROPERTIES 01 - GENERAL":            30,
    "FRAME SECTION PROPERTIES 04 - AUTO SELECT":         31,
    "AREA SECTION PROPERTIES":                          32,
    "LINK PROPERTY DEFINITIONS 01 - GENERAL":           33,

    # 4. Yük & Analiz Tanımları
    "LOAD PATTERN DEFINITIONS":                         40,
    "LOAD CASE DEFINITIONS":                            41,
    "CASE - STATIC 1 - LOAD ASSIGNMENTS":               42,
    "CASE - MODAL 1 - GENERAL":                         43,
    "COMBINATION DEFINITIONS":                          44,
    "MASS SOURCE":                                      45,

    # 5. Geometri
    "JOINT COORDINATES":                                50,
    "JOINT RESTRAINT ASSIGNMENTS":                      51,
    "CONNECTIVITY - FRAME":                             52,
    "CONNECTIVITY - AREA":                              53,
    "CONNECTIVITY - LINK":                              54,

    # 6. Atamalar
    "FRAME SECTION ASSIGNMENTS":                        60,
    "AREA SECTION ASSIGNMENTS":                         61,
    "LINK PROPERTY ASSIGNMENTS":                        62,
    "FRAME RELEASE ASSIGNMENTS 1 - GENERAL":            63,

    # 7. Yükler
    "JOINT LOADS - FORCE":                              70,
    "FRAME LOADS - GRAVITY":                            71,
    "FRAME LOADS - DISTRIBUTED":                        72,
    "FRAME LOADS - POINTS":                             73,
    "FRAME LOADS - TEMPERATURE":                        74,
    "AREA LOADS - UNIFORM":                             75,
    "AREA LOADS - UNIFORM TO FRAME":                    76,
    "AREA LOADS - WIND PRESSURE COEFFICIENTS":          77,

    # 8. Spektrum & Seismic
    "FUNCTION - RESPONSE SPECTRUM - TSC-2018":          80,
    "FUNCTION - RESPONSE SPECTRUM - FILE":              81,
    "FUNCTION - RESPONSE SPECTRUM - USER":              82,
    "CASE - RESPONSE SPECTRUM 1 - GENERAL":             83,
    "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS":    84,
    "AUTO SEISMIC - TSC-2018":                          85,
    # 9.SECTION CUTS
    "SECTION CUTS 1 - GENERAL":                         90,
    "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS":       91,

}


def get_priority(table_name: str) -> int:
    return PRIORITY.get(table_name, 999)


def build_router() -> Dict[str, Callable]:
    return {
        "PROGRAM CONTROL":                                  handle_program_control,
        "PROJECT INFORMATION":                              handle_project_information,

        "MATERIAL PROPERTIES 01 - GENERAL":                 handle_material_props,
        "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": handle_material_mech,

        "FRAME SECTION PROPERTIES 01 - GENERAL":            handle_frame_props,
        "FRAME SECTION PROPERTIES 04 - AUTO SELECT":         handle_auto_select_lists,
        "AREA SECTION PROPERTIES":                          handle_area_props,
        "LINK PROPERTY DEFINITIONS 01 - GENERAL":           handle_link_props,

        "LOAD PATTERN DEFINITIONS":                         handle_load_patterns,
        "LOAD CASE DEFINITIONS":                            handle_load_cases,
        "CASE - STATIC 1 - LOAD ASSIGNMENTS":               handle_static_assignments,
        "CASE - MODAL 1 - GENERAL":                         handle_modal_cases,
        "COMBINATION DEFINITIONS":                          handle_combinations,
        "MASS SOURCE":                                      handle_mass_source,

        "JOINT COORDINATES":                                handle_joints,
        "JOINT RESTRAINT ASSIGNMENTS":                      handle_joint_restraints,
        "CONNECTIVITY - FRAME":                             handle_frame_conn,
        "CONNECTIVITY - AREA":                              handle_area_conn,
        "CONNECTIVITY - LINK":                              handle_link_conn,

        "FRAME SECTION ASSIGNMENTS":                        handle_frame_assign,
        "AREA SECTION ASSIGNMENTS":                         handle_area_assign,
        "LINK PROPERTY ASSIGNMENTS":                        handle_link_assign,
        "FRAME RELEASE ASSIGNMENTS 1 - GENERAL":            handle_frame_releases,

        "JOINT LOADS - FORCE":                              handle_joint_loads,
        "FRAME LOADS - GRAVITY":                            handle_frame_gravity,
        "FRAME LOADS - DISTRIBUTED":                        handle_frame_distributed,
        "FRAME LOADS - POINTS":                             handle_frame_points,
        "FRAME LOADS - TEMPERATURE":                        handle_frame_temperature,
        "AREA LOADS - UNIFORM":                             handle_area_uniform,
        "AREA LOADS - UNIFORM TO FRAME":                    handle_area_uniform_to_frame,
        "AREA LOADS - WIND PRESSURE COEFFICIENTS":          handle_area_wind,

        "FUNCTION - RESPONSE SPECTRUM - TSC-2018":          handle_spectrum_functions_TSC,
        "FUNCTION - RESPONSE SPECTRUM - FILE":              handle_spectrum_functions_file,
        "FUNCTION - RESPONSE SPECTRUM - USER":              handle_spectrum_functions_user,
        "CASE - RESPONSE SPECTRUM 1 - GENERAL":             handle_response_spectrum_gen,
        "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS":    handle_response_spectrum_assign,
        "AUTO SEISMIC - TSC-2018":                          handle_auto_seismic,

        "SECTION CUTS 1 - GENERAL":                         handle_section_cuts_gen,
        "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS":       handle_section_cuts_quad,

    }


def build_sorted_router() -> List[Tuple[str, Callable]]:
    router = build_router()
    items = [(name, handler, get_priority(name)) for name, handler in router.items()]
    items.sort(key=lambda x: x[2])
    return [(name, handler) for name, handler, _ in items]

class S2KParser:
    """SAP2000 .s2k dosyası → tablo DataFrame'leri."""

    PAIR_PATTERN = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        if self.file_path:
            self._parse(self.file_path)

    def _parse(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Dosya bulunamadı: {file_path}")
            return

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Dosya okuma hatası: {e}")
            return

        logger.info(f"[Parser] Dosya: {path.name}, boyut: {len(content)} bytes")

        # Satır devamı ( _\n ) birleştir
        content = re.sub(r' _\r?\n', ' ', content)

        # Tabloları ayır
        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[Parser] {len(raw_tables)} potansiyel tablo")

        for raw in raw_tables:
            if not raw.strip():
                continue

            lines = raw.strip().split('\n')
            table_name = lines[0].strip().strip('"')
            rows = []

            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                pairs = self.PAIR_PATTERN.findall(line)
                if pairs:
                    row = {}
                    for k, v in pairs:
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        row[k] = v
                    rows.append(row)

            if rows:
                self.tables[table_name] = pd.DataFrame(rows)

        logger.info(f"[Parser] {len(self.tables)} tablo yüklendi")

    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables

def show_file_dialog() -> Optional[str]:
    from tools.s2k.dialog import show_file_dialog as _dlg
    return _dlg()


class S2KLoader:
    """SAP2000 .$2k dosyasından Scene yükler."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or show_file_dialog()

        if not self.file_path:
            logger.warning("[Loader] Dosya seçilmedi")
            self.parser = None
            return

        self.parser = S2KParser(self.file_path)
        self.units = None

    def load(self) -> Scene:
        """S2K dosyasını yükle → Scene."""
        if self.parser is None:
            return Scene()

        logger.info("[Loader] Model inşa ediliyor...")

        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed_tables = set()

        # ───── SIRALI HANDLER ÇAĞRISI ─────
        for table_name, handler in build_sorted_router():
            if table_name not in tables:
                continue

            df = tables[table_name]
            processed_tables.add(table_name)

            if df.empty:
                continue

            try:
                handler(ctx, df)
            except Exception as e:
                logger.error(f"'{table_name}' handler hatası: {e}", exc_info=True)

        # ───── SIRADA OLMAYAN/EK TABLOLARI İŞLE ─────
        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue

            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.debug(f"Ek tablo işlendi: {table_name}")
                except Exception as e:
                    logger.error(f"'{table_name}': {e}", exc_info=True)

        self.units = ctx.units
        scene = build_scene(ctx)
        
        # Section cut nesnelerini sahne tanım yöneticisine doğrudan bağlıyoruz
        if hasattr(ctx, 'section_cuts'):
            scene.def_mgr.section_cuts = ctx.section_cuts

        logger.info("[Scene] "
                    f"{len(scene.nodes)} node, "
                    f"{len(scene.frames)} frame, "
                    f"{len(scene.areas)} area, "
                    f"{len(scene.links)} link")

        return scene

if __name__ == "__main__":
    app = S2KLoader("examples/model3d.s2k")
    scene = app.load()
    # print(scene.links)
    key_list = ['materials', 'sections', 'link_props', 'load_patterns', 'load_cases', 'modal_cases', 'combinations', 'spectrum_functions', 'response_spectrum_cases', 'auto_seismics', 'mass_source_map', 'project_info']
    for key_ in key_list:
        print()
        print(key_)
        dict_= getattr(scene.def_mgr, key_, {})
        for k in dict_:
            v= dict_[k]
            print(" >", k, type(v))
            print("   >", v)