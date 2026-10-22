# tools/s2k_utils.py

from domain.definition import (
    AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad, 
    AutoSeismicTSC2018, ComboItem, DistType, FrameDistributedLoad, 
    FrameGravityLoad, GeneralProjectInfo, LinkProp, LinkPropLinear, 
    LinkPropType, LoadCase, LoadCombination, LoadDirection, LoadPattern, 
    MatType, Material, ModalCase, PointLoad, QuadDefinition, 
    ResponseSpectrumCase, ResponseSpectrumLoadAssignment, SDPolygonPoint, SDSection, SDShape, Section, 
    SectionCut, SectionCutDefinedBy, SectionCutResultType, SectionType, 
    SiteInformation, SpectrumFunction, SpectrumSourceType, StaticLoadAssignment
)
from typing import Optional, Callable, List, Tuple, Dict
from dataclasses import dataclass, field
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder
from domain.element import Node, Frame, Area, Link
import pandas as pd

from logging_config import CadLogger
logger = CadLogger.get(__name__)

from data.unit_enums import (
    UnitSystem,
    UnitDef,
    UNIT_DEFINITIONS_MAP,
    unit_system_from_sap_string,
    G_MM_S2,          # 9806.65 mm/s²
)

class UnitConverter:
    """
    SAP2000 CurrUnits string'i → yerel (N, mm, °C) dönüşümleri.

    Kullanım:
        uc = UnitConverter('Tonf, m, C')
        uc.L(3.0)        # 3000.0 mm
        uc.F(1.0)        # 9806.65 N
        uc.M(1.0)        # 9806.65 * 1000 N·mm
        uc.E(1.0)        # 9806.65 / (1000**2) MPa = 0.00980665 MPa
    """

    def __init__(self, curr_units_str: str = "N, mm, C"):
        self.raw_string = (curr_units_str or "N, mm, C").strip()
        self.unit_system: UnitSystem = unit_system_from_sap_string(self.raw_string)
        self.unit_def: UnitDef = self.unit_system.unit_def

        # Sıcaklık birimini string'den override et (enum'da C/F ayrımı yok)
        parts = [p.strip() for p in self.raw_string.split(",")]
        temp = parts[2].upper() if len(parts) > 2 else "C"
        self.temp_unit = temp if temp in ("C", "F") else "C"

    # ---------------------------------------------------------------
    # Temel büyüklükler
    # ---------------------------------------------------------------
    def L(self, v: float) -> float: return float(v) * self.unit_def.length_to_mm
    def L2(self, v: float) -> float: return float(v) * (self.unit_def.length_to_mm ** 2)
    def L3(self, v: float) -> float: return float(v) * (self.unit_def.length_to_mm ** 3)
    def L4(self, v: float) -> float: return float(v) * (self.unit_def.length_to_mm ** 4)
    def F(self, v: float) -> float: return float(v) * self.unit_def.force_to_N
    def M(self, v: float) -> float: return float(v) * self.unit_def.moment_to_Nmm
    def E(self, v: float) -> float: return float(v) * self.unit_def.stress_to_MPa
    def w(self, v: float) -> float: return float(v) * self.unit_def.line_load_to_N_per_mm
    def area_w(self, v: float) -> float: return float(v) * self.unit_def.area_load_to_N_per_mm2
    def mass(self, v: float) -> float:return float(v) * self.unit_def.force_to_N / (self.unit_def.length_to_mm / 1000.0)
    def density(self, v: float) -> float: return float(v)

    def mmi(self, v: float) -> float:
        """Kütle atalet momenti: F·L² → kg·mm²."""
        return float(v) * self.unit_def.mass_to_kg * (self.unit_def.length_to_mm ** 2)
    # ---------------------------------------------------------------
    # İvme
    # ---------------------------------------------------------------
    def acc(self, v: float) -> float: return float(v) * self.unit_def.length_to_mm

    def acc_from_g(self, v: float) -> float: return float(v) * G_MM_S2

    # ---------------------------------------------------------------
    # Sıcaklık
    # ---------------------------------------------------------------
    def temp_abs(self, v: float) -> float:
        """Mutlak sıcaklık → °C."""
        if self.temp_unit == "F":
            return (float(v) - 32.0) * 5.0 / 9.0
        return float(v)

    def temp_diff(self, v: float) -> float:
        """Sıcaklık farkı → °C farkı."""
        if self.temp_unit == "F":
            return float(v) * 5.0 / 9.0
        return float(v)

    def __str__(self) -> str:
        return self.raw_string

@dataclass
class LoadContext:
    """Tüm handler'ların veri topladığı merkezi kutu."""

    units: UnitConverter = field(default_factory=UnitConverter)
    project_info: Dict[str, GeneralProjectInfo | SiteInformation] = field(
        default_factory=lambda: {
            "gen": GeneralProjectInfo(),
            "site": SiteInformation(),
        }
    )

    materials: Dict[str, Material] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    auto_select_lists: Dict[str, list] = field(default_factory=dict)
    area_sections: Dict[str, dict] = field(default_factory=dict)
    area_thicknesses: Dict[str, float] = field(default_factory=dict)
    link_props: Dict[str, LinkProp] = field(default_factory=dict)

    load_patterns: Dict[str, LoadPattern] = field(default_factory=dict)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    modal_cases: Dict[str, ModalCase] = field(default_factory=dict)
    load_combos: Dict[str, LoadCombination] = field(default_factory=dict)

    spectrum_functions: Dict[str, SpectrumFunction] = field(default_factory=dict)
    response_spectrum_cases: Dict[str, ResponseSpectrumCase] = field(default_factory=dict)
    auto_seismics: Dict[str, AutoSeismicTSC2018] = field(default_factory=dict)

    mass_source_map: Dict[str, float] = field(default_factory=dict)
    section_cuts: Dict[str, float] = field(default_factory=dict)

    # Yeni eklenen tablolara ait haritalar/DataFrame'ler
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
    df_sd_general: Optional[pd.DataFrame] = None
    df_sd_polygon: Optional[pd.DataFrame] = None
    df_sd_rect: Optional[pd.DataFrame] = None

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

    # Yeni Ham DataFrame alanları
    df_diaphragms: Optional[pd.DataFrame] = None
    df_frame_modifiers: Optional[pd.DataFrame] = None
    df_frame_design_procs: Optional[pd.DataFrame] = None
    df_frame_auto_mesh: Optional[pd.DataFrame] = None

    df_grid_lines: Optional[pd.DataFrame] = None
    df_joint_constraints: Optional[pd.DataFrame] = None
    df_link_props_linear: Optional[pd.DataFrame] = None
    
    joint_constraints: Dict[str, str] = field(default_factory=dict)
    grid_lines: list = field(default_factory=list)


def get_color_from_string(color_str: str) -> Tuple[float, float, float]:
    color_map = {
        'Red': (1.0, 0.0, 0.0), 'Green': (0.0, 1.0, 0.0), 'Blue': (0.0, 0.0, 1.0),
        'Yellow': (1.0, 1.0, 0.0), 'Cyan': (1.0, 1.0, 1.0), 'Magenta': (1.0, 0.0, 1.0),
        'White': (1.0, 1.0, 1.0), 'Black': (0.0, 0.0, 0.0),
        'Gray8Dark': (0.3, 0.3, 0.3), 'Gray8Light': (0.7, 0.7, 0.7),
    }
    return color_map.get(color_str, (0.8, 0.8, 0.8))


def parse_sap_mat_type(row) -> 'MatType':
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


def map_sap_to_local_params(row, units: UnitConverter) -> Tuple[SectionType, Dict[str, float]]:
    """
    SAP2000 'FRAME SECTION PROPERTIES 01 - GENERAL' satırını yerel SectionType + params'a çevirir.
    Not: SD Section için geometri burada BAĞLANMAZ — handle_frame_props,
    ctx.sd_sections'tan çekip Section.sd_section alanına yazar.
    """

    s_type = str(row.get('Shape', 'Rectangle')).strip()

    # ---- yardımcılar ----
    def L(key, default=0.0):
        return units.L(safe_float(row, key, default))

    def L2(key, default=0.0):
        return units.L(safe_float(row, key, default)) ** 2

    def L3(key, default=0.0):
        return units.L(safe_float(row, key, default)) ** 3

    def L4(key, default=0.0):
        return units.L(safe_float(row, key, default)) ** 4

    def dim(key, default=1.0):
        v = safe_float(row, key, default)
        return v if v != 0 else default

    # ---- analiz özellikleri (tüm tipler için ortak) ----
    analysis = {
        'Area':  L2('Area'),
        'J':     L4('TorsConst'),
        'I33':   L4('I33'),
        'I22':   L4('I22'),
        'I23':   L4('I23'),
        'AS2':   L2('AS2'),
        'AS3':   L2('AS3'),
        'S33Top':  L3('S33Top'),
        'S33Bot':  L3('S33Bot'),
        'S22Left': L3('S22Left'),
        'S22Right':L3('S22Right'),
        'Z33':     L3('Z33'),
        'Z22':     L3('Z22'),
        'R33':     L3('R33'),
        'R22':     L3('R22'),
        'Cw':      L4('Cw'),
        'AMod':   dim('AMod', 1.0),
        'A2Mod':  dim('A2Mod', 1.0),
        'A3Mod':  dim('A3Mod', 1.0),
        'JMod':   dim('JMod', 1.0),
        'I2Mod':  dim('I2Mod', 1.0),
        'I3Mod':  dim('I3Mod', 1.0),
        'MMod':   dim('MMod', 1.0),
        'WMod':   dim('WMod', 1.0),
    }

    # ==================================================================
    # GEOMETRİK PARAMETRELER (mm)
    # ==================================================================

    if s_type in ("I/Wide Flange", "I"):
        return SectionType.I, {
            "h":  L('t3', 200.0),
            "b":  L('t2', 100.0),
            "tw": L('tw', 10.0),
            "tf": L('tf', 14.0),
            "t2b": L('t2b', L('t2', 100.0)),
            "tfb": L('tfb', L('tf', 14.0)),
            **analysis,
        }

    if s_type in ("Tee", "T"):
        return SectionType.T, {
            "h":  L('t3', 200.0),
            "b":  L('t2', 100.0),
            "tw": L('tw', 10.0),
            "tf": L('tf', 14.0),
            **analysis,
        }

    if s_type == "SD Section":
        # Geometri handle_frame_props'ta ctx.sd_sections'tan bağlanacak.
        # Bayrak YOK; ayrımı handle_frame_props sd_section varlığıyla yapacak.
        logger.debug(f"[SectionMap] 'SD Section' — geometri handle_frame_props'ta bağlanacak")
        return SectionType.CUSTOM, {**analysis}

    if s_type == "General":
        # SAP "General" = kullanıcı tanımlı analiz özellikleri (SD değil)
        logger.debug(f"[SectionMap] 'General' — sadece analiz özellikleri")
        return SectionType.CUSTOM, {**analysis}

    if s_type in ("Rectangle", "Rectangular"):
        return SectionType.RECT, {
            "h": L('t3', 200.0),
            "b": L('t2', 100.0),
            **analysis,
        }

    if s_type in ("Pipe", "Circular", "Circle"):
        d = L('t3', 120.0)
        tw = L('tw', 10.0)
        return SectionType.PIPE, {
            "ro": d / 2.0,
            "ri": max(0.1, (d - 2.0 * tw) / 2.0),
            "n": 24,
            **analysis,
        }

    if s_type in ("Channel", "C"):
        return SectionType.C, {
            "h": L('t3', 100.0),
            "b": L('t2', 80.0),
            "t": L('tw', 6.0),
            "tf": L('tf', 6.0),
            **analysis,
        }

    if s_type in ("Angle", "L"):
        return SectionType.L, {
            "h": L('t3', 100.0),
            "b": L('t2', 80.0),
            "t": L('tw', 8.0),
            **analysis,
        }

    if s_type in ("Tube", "Box"):
        return SectionType.TUBE, {
            "h": L('t3', 200.0),
            "b": L('t2', 100.0),
            "t": L('tw', 10.0),
            **analysis,
        }

    # Bilinmeyen shape → RECT fallback
    logger.warning(f"[SectionMap] Bilinmeyen Shape='{s_type}', RECT fallback")
    return SectionType.RECT, {
        "h": L('t3', 200.0),
        "b": L('t2', 100.0),
        **analysis,
    }


def safe_float(row, key, default=0.0, allow_zero=True):
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan"):
        return default
    try:
        f = float(val)
        return f if (allow_zero or abs(f) > 1e-12) else default
    except (ValueError, TypeError):
        return default


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


def _create_frames(builder, ctx, node_map):
    frame_map = {}
    if ctx.df_frame_conn is None or ctx.df_frame_conn.empty:
        logger.warning("[Frames] df_frame_conn BOŞ")
        return frame_map, 0

    frame_assign = _parse_frame_assign(ctx.df_frame_assign, ctx)
    logger.info(f"[Frames] {len(frame_assign)} frame ataması")

    frame_release = _parse_frame_release(ctx.df_frame_release)
    fallback = _get_fallback_section(builder, ctx)
    logger.info(f"[Frames] fallback kesit: '{fallback}'")

    count = 0
    errors = 0
    no_section = 0
    for _, row in ctx.df_frame_conn.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        joint_i = str(row.get('JointI', '')).strip()
        joint_j = str(row.get('JointJ', '')).strip()

        if not frame_id or joint_i not in node_map or joint_j not in node_map:
            errors += 1
            continue

        sect_name, rotation = frame_assign.get(frame_id, ("", 0.0))
        if not sect_name:
            no_section += 1
            sect_name = fallback
        elif sect_name not in ctx.sections:
            no_section += 1
            if no_section <= 3:
                logger.warning(f"[Frames] Frame {frame_id}: '{sect_name}' ctx.sections'ta yok, "
                               f"mevcut: {list(ctx.sections.keys())[:5]}...")
            sect_name = fallback

        try:
            frame = builder.create_frame(
                node_map[joint_i], node_map[joint_j],
                sect_name, rotation_deg=rotation, label=f"F{frame_id}",
            )
            if frame_id in frame_release:
                frame.release_i = frame_release[frame_id]['i']
                frame.release_j = frame_release[frame_id]['j']
            frame_map[frame_id] = frame
            count += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                logger.error(f"[Frames] Frame {frame_id} oluşturma HATASI: {e}", exc_info=True)

    logger.info(f"[Frames] SONUÇ: created={count}, no_section={no_section}, errors={errors}, "
                f"total={len(ctx.df_frame_conn)}")
    return frame_map, count


def _parse_frame_assign(df: pd.DataFrame, ctx: LoadContext = None) -> Dict[str, Tuple[str, float]]:
    if df is None or df.empty or 'Frame' not in df.columns:
        logger.warning("[FrameAssign] Tablo BOŞ veya None")
        return {}
    
    if 'Frame' not in df.columns:
        logger.error(f"[FrameAssign] 'Frame' kolonu YOK! Kolonlar: {list(df.columns)}")
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
                sect = members[mid_idx]

        try:
            rotation = float(row.get('Angle', 0.0))
        except (ValueError, TypeError):
            rotation = 0.0

        result[frame_id] = (sect, rotation)

    logger.info(f"[FrameAssign] {len(result)} atama parse edildi")
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
    ctx.sections["DEFAULT"] = default
    # ✅ KRİTİK: project'e de ekle!
    builder.project.add_section(default)
    return "DEFAULT"


def _create_areas(builder, ctx, node_map):
    area_map = {}
    if ctx.df_area_conn is None or ctx.df_area_conn.empty:
        return area_map, 0

    area_assign = _parse_area_assign(ctx.df_area_assign)

    for _, row in ctx.df_area_conn.iterrows():
        area_id = str(row.get('Area', '')).strip()
        joints = [node_map[j] for i in range(1, 5)
                  if (j := str(row.get(f'Joint{i}', '')).strip()) in node_map]
        if len(joints) < 3:
            continue

        section_name = area_assign.get(area_id, "")
        section_data = ctx.area_sections.get(section_name, {})

        # DİKKAT: thickness artık mm; dönüştürme YOK
        thickness = section_data.get("thickness", 100.0)

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
    if df_d is None or df_d.empty:
        return

    def _sap_dir_to_our(dir_str: str) -> str:
        d = str(dir_str).strip()
        mapping = {
            "1": "1", "2": "2", "3": "3",
            "X": "4", "Y": "5", "Z": "6",
            "Global X": "4", "Global Y": "5", "Global Z": "6",
            "Gravity": "7", "GRAV": "7",
            "ProjectedX": "8", "ProjectedY": "9", "ProjectedZ": "10",
            "Proj X": "8", "Proj Y": "9", "Proj Z": "10",
        }
        if d in mapping:
            return mapping[d]
        for k, v in mapping.items():
            if k.lower() == d.lower():
                return v
        return "2"

    from collections import defaultdict
    per_frame: Dict[str, list] = defaultdict(list)

    for _, r in df_d.iterrows():
        frame_id = str(r.get('Frame', '')).strip()
        if not frame_id or frame_id not in frame_map:
            continue

        pattern = str(r.get('LoadPat', 'DEFAULT')).strip()
        csys = str(r.get('CoordSys', 'Local')).strip()
        dir_sap = str(r.get('Dir', 'Gravity')).strip()
        our_load_dir = _sap_dir_to_our(dir_sap)
        is_rel = "REL" in str(r.get('DistType', 'RelDist')).upper()

        if is_rel:
            x1 = safe_float(r, 'RelDistA', 0.0)
            x2 = safe_float(r, 'RelDistB', 1.0)
        else:
            # Mutlak mesafe → normalize et
            L = frame.get_length()
            x1 = safe_float(r, 'DistA', 0.0) / L if L > 0 else 0.0
            x2 = safe_float(r, 'DistB', L) / L if L > 0 else 1.0

        ftype = str(r.get('Type', 'Force')).upper()
        v1 = safe_float(r, 'FOverLA', 0.0)
        v2 = safe_float(r, 'FOverLB', default=v1)

        if ftype == 'FORCE':
            v1 = ctx.units.w(v1)
            v2 = ctx.units.w(v2)

        per_frame[frame_id].append({
            "pattern": pattern,
            "csys": csys,
            "load_dir": our_load_dir,
            "is_rel": is_rel,
            "x1": x1, "x2": x2,
            "v1": v1, "v2": v2,
        })

    for frame_id, rows in per_frame.items():
        frame = frame_map[frame_id]
        by_pattern: Dict[str, list] = defaultdict(list)
        for row in rows:
            by_pattern[row["pattern"]].append(row)

        for pattern, items in by_pattern.items():
            first = items[0]
            csys_norm = "Global" if first["csys"].lower().startswith("g") else "Local"

            load_set = FrameDistributedLoad(
                pattern_name=pattern,
                coord_sys=csys_norm,
                load_dir=first["load_dir"],
                mode="REPLACE",
                is_relative=first["is_rel"],
                segments=[],
            )

            for it in items:
                load_set.add_segment(
                    x1=float(it["x1"]),
                    x2=float(it["x2"]),
                    q1=float(it["v1"]),
                    q2=float(it["v2"]),
                )

            frame.dist_load_sets[pattern] = load_set

            for sap_load in load_set.to_sap_loads():
                frame.dist_loads.append(sap_load)


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
                raw_dist = r.get('DistType', 'One way')
                area.uniform_to_frame_loads.append(AreaUniformToFrameLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                    value=ctx.units.area_w(safe_float(r, 'UnifLoad', 0.0)),
                    dist_type=DistType.from_input(raw_dist),
                    coordinate_system=str(r.get('CoordSys', 'GLOBAL')).strip(),
                ))

def parse_sd_polygon_table(df, ctx):
    """Aynı (SectionName, ShapeName) grubunu tek SDShape'e birleştirir."""
    if df is None or df.empty:
        return
    grouped = {}   # (section, shape) -> list of rows (sıralı!)
    for _, row in df.iterrows():
        sec = str(row.get('SectionName','')).strip()
        shp = str(row.get('ShapeName','')).strip()
        if not sec or not shp: continue
        grouped.setdefault((sec, shp), []).append(row)
    
    for (sec, shp), rows in grouped.items():
        # İlk satırdan meta oku
        first = rows[0]
        material = str(first.get('ShapeMat','')).strip()
        try: z_order = int(float(first.get('ZOrder', 1)))
        except: z_order = 1
        color = get_color_from_string(str(first.get('FillColor','Gray8Dark')))
        
        pts = []
        for r in rows:
            x = ctx.units.L(safe_float(r, 'X'))
            y = ctx.units.L(safe_float(r, 'Y'))
            rad = ctx.units.L(safe_float(r, 'Radius'))
            pts.append(SDPolygonPoint(x, y, rad))
        
        shape = SDShape(name=shp, shape_kind="Polygon", material=material,
                        z_order=z_order, fill_color=color, points=pts)
        
        sd = ctx.sd_sections.setdefault(sec, SDSection(name=sec))
        sd.shapes.append(shape)
        logger.info(f"[SD Polygon] {sec}/{shp}: {len(pts)} köşe, mat={material}")
        
def handle_program_control(ctx: LoadContext, df: pd.DataFrame):
    if 'CurrUnits' in df.columns and not df.empty:
        raw = str(df.iloc[0]['CurrUnits']).strip()
        if raw:
            ctx.units = UnitConverter(raw)
            logger.info(f"[Units] CurrUnits='{raw}' → {ctx.units.unit_system.name}")
            return
    logger.info("[Units] CurrUnits bulunamadı, varsayılan N_MM kullanılıyor")
    ctx.units = UnitConverter("N, mm, C")


def handle_project_information(ctx: LoadContext, df: pd.DataFrame):
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


def handle_material_props(ctx: LoadContext, df: pd.DataFrame):
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
        raw_unit_mass = safe_float(row, 'UnitMass', 7.85e-6)
        # SAP UnitMass = kg/mm³ (pratikte); dönüşüm yok
        mat.density = ctx.units.density(raw_unit_mass)


def handle_joint_added_mass(ctx: LoadContext, df: pd.DataFrame):
    """JOINT ADDED MASS ASSIGNMENTS → ctx.joint_added_mass[joint_id]"""
    if df.empty:
        return
    for _, r in df.iterrows():
        jid = str(r.get('Joint', '')).strip()
        if not jid:
            continue
        ctx.joint_added_mass[jid] = {
            'm1': ctx.units.mass(safe_float(r, 'Mass1', 0.0)),
            'm2': ctx.units.mass(safe_float(r, 'Mass2', 0.0)),
            'm3': ctx.units.mass(safe_float(r, 'Mass3', 0.0)),
            'mmi1': ctx.units.mmi(safe_float(r, 'MMI1', 0.0)),  # MMI: kg·mm²
            'mmi2': ctx.units.mmi(safe_float(r, 'MMI2', 0.0)),
            'mmi3': ctx.units.mmi(safe_float(r, 'MMI3', 0.0)),
        }

def _attach_sd_geometry(sect_name: str, shape: str, ctx: LoadContext):
    """
    'SD Section' satırları için Section Designer geometrisini ctx.sd_sections'tan çeker.
    SD olmayan satırlar için None döner.
    """
    if shape != "SD Section":
        return None

    sd = ctx.sd_sections.get(sect_name)
    if sd is None:
        logger.warning(
            f"[FrameProps] SD Section '{sect_name}' için "
            f"ctx.sd_sections'ta geometri YOK"
        )
        return None

    n_shapes = len(sd.shapes)
    n_pts = sum(len(sh.points) for sh in sd.shapes)
    logger.info(
        f"[FrameProps] SD Section '{sect_name}': "
        f"{n_shapes} shape, {n_pts} toplam köşe noktası bağlandı"
    )
    return sd

def _resolve_material(ctx: LoadContext, mat_name_raw) -> Optional[Material]:
    mat_name = str(mat_name_raw or '').strip()
    if not mat_name or mat_name.lower() == 'nan':
        return None
    mat = ctx.materials.get(mat_name)
    if mat is None:
        mat = Material(name=mat_name, mat_type=MatType.STEEL)
        ctx.materials[mat_name] = mat
    return mat

def handle_frame_props(ctx: LoadContext, df: pd.DataFrame):
    logger.info(f"[FrameProps] ÇAĞRILDI! {len(df)} satır")
    if df.empty:
        logger.warning("[FrameProps] DataFrame BOŞ")
        return

    name_col = next((c for c in ('SectionName', 'Section', 'Name') if c in df.columns), None)
    if name_col is None:
        logger.error(f"[FrameProps] Kesit isim kolonu YOK! Kolonlar: {list(df.columns)}")
        return

    loaded = skipped = failed = 0

    for idx, row in df.iterrows():
        sect_name = str(row.get(name_col, '')).strip()
        if not sect_name:
            continue

        shape = str(row.get('Shape', '')).strip()
        auto_type = str(row.get('AutoType', '')).strip().upper()

        if 'auto select' in shape.lower() or auto_type in ('YES', 'AUTOSELECT'):
            skipped += 1
            continue

        try:
            s_type, s_params = map_sap_to_local_params(row, ctx.units)
        except Exception as e:
            failed += 1
            logger.error(
                f"[FrameProps] '{sect_name}' (satır {idx}) dönüşüm HATASI: {e}",
                exc_info=True,
            )
            continue

        mat_obj = _resolve_material(ctx, row.get('Material', ''))

        # SD Section ise geometriyi ctx.sd_sections'tan bağla
        # (General vb. CUSTOM'lar için helper None döner)
        sd_section = None
        if s_type == SectionType.CUSTOM:
            sd_section = _attach_sd_geometry(sect_name, shape, ctx)

        ctx.sections[sect_name] = Section(
            name=sect_name,
            profile_type=s_type,
            profile_params=s_params,     # ← artık _is_sd yok
            material=mat_obj,
            color=get_color_from_string(row.get('Color', 'Gray8Dark')),
            sd_section=sd_section,
        )
        loaded += 1

    logger.info(
        f"[FrameProps] SONUÇ: loaded={loaded}, skipped={skipped}, "
        f"failed={failed}, total={len(df)}"
    )


def handle_auto_select_lists(ctx: LoadContext, df: pd.DataFrame):
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


def handle_area_props(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(row.get('Section', '')).strip()
        if not name:
            continue

        # HAM değeri oku (CurrUnits cinsinden, ör. m)
        raw_thickness = safe_float(row, 'Thickness', 0.1)  # varsayılan 0.1 m
        thickness_mm = ctx.units.L(raw_thickness)          # → mm

        ctx.area_thicknesses[name] = thickness_mm

        mat_name = str(row.get('Material', '')).strip()
        mat_obj = ctx.materials.get(mat_name) if mat_name else None
        if mat_obj is None and mat_name:
            mat_obj = Material(name=mat_name)
            ctx.materials[mat_name] = mat_obj

        ctx.area_sections[name] = {
            "material": mat_obj,
            "thickness": thickness_mm,   # ← ARTIK mm
            "area_type": str(row.get('AreaType', 'Shell')).strip(),
            "type": str(row.get('Type', 'Shell-Thin')).strip(),
            "color": get_color_from_string(row.get('Color', 'Gray8Dark')),
            "bend_thick": ctx.units.L(safe_float(row, 'BendThick', 0.0)),
            "drill_dof": str(row.get('DrillDOF', 'No')).strip().upper() == 'YES',
            "type": str(row.get('Type', 'Shell-Thin')).strip(),
            "area_type": str(row.get('AreaType', 'Shell')).strip(),
        }


def handle_link_props(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return

    for _, row in df.iterrows():
        name = str(
            row.get('Link', row.get('LinkProp', row.get('Name', '')))
        ).strip()
        if not name:
            continue

        if name in ctx.link_props:
            continue

        link_type_str = str(row.get('LinkType', 'LINEAR')).strip()
        prop_type = LinkPropType.from_sap(link_type_str)
        prop = _make_link_prop(name, prop_type)

        ctx.link_props[name] = prop


def _make_link_prop(name: str, prop_type: LinkPropType):
    factory = {
        LinkPropType.LINEAR: LinkPropLinear,
        LinkPropType.DAMPER: LinkPropLinear,
        LinkPropType.GAP: LinkPropLinear,
        LinkPropType.HOOK: LinkPropLinear,
        LinkPropType.PLASTIC_WEN: LinkPropLinear,
        LinkPropType.ISOLATOR1: LinkPropLinear,
        LinkPropType.ISOLATOR2: LinkPropLinear,
        LinkPropType.MULTILINEAR_ELASTIC: LinkPropLinear,
        LinkPropType.MULTILINEAR_PLASTIC: LinkPropLinear,
        LinkPropType.ISOLATOR3: LinkPropLinear,
    }
    cls = factory.get(prop_type, LinkPropLinear)
    return cls(name=name, prop_type=prop_type)


# --- YENİ EKLENEN VEYA EKSİK GİDERİLEN HANDLE KODLARI ---

def handle_diaphragms(ctx: LoadContext, df: pd.DataFrame):
    """CONSTRAINT DEFINITIONS - DIAPHRAGM"""
    ctx.df_diaphragms = df
    if df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get('Name', '')).strip()
        if name:
            ctx.diaphragms[name] = {
                'coord_sys': str(r.get('CoordSys', 'GLOBAL')).strip(),
                'axis': str(r.get('Axis', 'Z')).strip(),
                'multi_level': str(r.get('MultiLevel', 'No')).strip().upper() == 'YES'
            }

def handle_frame_modifiers(ctx: LoadContext, df: pd.DataFrame):
    """FRAME PROPERTY MODIFIERS"""
    ctx.df_frame_modifiers = df
    if df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get('Frame', '')).strip()
        if fid:
            ctx.frame_modifiers[fid] = {
                'amod': safe_float(r, 'AMod', 1.0),
                'as2mod': safe_float(r, 'AS2Mod', 1.0),
                'as3mod': safe_float(r, 'AS3Mod', 1.0),
                'jmod': safe_float(r, 'JMod', 1.0),
                'i22mod': safe_float(r, 'I22Mod', 1.0),
                'i33mod': safe_float(r, 'I33Mod', 1.0),
                'massmod': safe_float(r, 'MassMod', 1.0),
                'weightmod': safe_float(r, 'WeightMod', 1.0),
            }

def handle_frame_design_procs(ctx: LoadContext, df: pd.DataFrame):
    """FRAME DESIGN PROCEDURES"""
    ctx.df_frame_design_procs = df
    if df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get('Frame', '')).strip()
        proc = str(r.get('DesignProc', 'From Material')).strip()
        if fid:
            ctx.frame_design_procs[fid] = proc

def handle_frame_auto_mesh(ctx: LoadContext, df: pd.DataFrame):
    """FRAME AUTO MESH ASSIGNMENTS"""
    ctx.df_frame_auto_mesh = df
    if df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get('Frame', '')).strip()
        if fid:
            ctx.frame_auto_mesh[fid] = {
                'auto_mesh': str(r.get('AutoMesh', 'No')).strip().upper() == 'YES',
                'at_joints': str(r.get('AtJoints', 'Yes')).strip().upper() == 'YES',
                'max_length': safe_float(r, 'MaxLength', 0.0),
            }

def handle_frame_output_stations(ctx: LoadContext, df: pd.DataFrame):
    """FRAME OUTPUT STATION ASSIGNMENTS"""
    pass

def handle_frame_load_transfer_options(ctx: LoadContext, df: pd.DataFrame):
    """FRAME LOAD TRANSFER OPTIONS"""
    pass

def handle_frame_local_axes(ctx: LoadContext, df: pd.DataFrame):
    """FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL"""
    pass


def handle_joints(ctx: LoadContext, df: pd.DataFrame): ctx.df_joints = df
def handle_joint_restraints(ctx: LoadContext, df: pd.DataFrame): ctx.df_restraints = df
def handle_frame_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_conn = df
def handle_area_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_conn = df
def handle_link_conn(ctx: LoadContext, df: pd.DataFrame): ctx.df_link_conn = df
def handle_frame_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_assign = df
def handle_area_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_assign = df
def handle_link_assign(ctx: LoadContext, df: pd.DataFrame): ctx.df_link_assign = df
def handle_frame_releases(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_release = df
def handle_joint_loads(ctx: LoadContext, df: pd.DataFrame): ctx.df_joint_loads = df
def handle_frame_gravity(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_gravity = df
def handle_frame_distributed(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_distributed = df
def handle_frame_points(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_points = df
def handle_frame_temperature(ctx: LoadContext, df: pd.DataFrame): ctx.df_frame_temperature = df
def handle_area_uniform(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_uniform = df
def handle_area_uniform_to_frame(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_uniform_to_frame = df
def handle_area_wind(ctx: LoadContext, df: pd.DataFrame): ctx.df_area_wind = df

def handle_load_patterns(ctx: LoadContext, df: pd.DataFrame):
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
    if df.empty:
        return
    for _, row in df.iterrows():
        pattern = str(row.get('LoadPat', '')).strip()
        if not pattern:
            continue
        ctx.mass_source_map[pattern] = safe_float(row, 'Multiplier', 1.0)


def handle_spectrum_functions_TSC(ctx: LoadContext, df: pd.DataFrame):
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
    ctx.df_spec_gen = df


def handle_response_spectrum_assign(ctx: LoadContext, df: pd.DataFrame):
    ctx.df_spec_ass = df
    _process_response_spectrum_cases(ctx)


def _process_response_spectrum_cases(ctx: LoadContext):
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
                sf = safe_float(r, 'TransAccSF', 1.0)

                assignment = ResponseSpectrumLoadAssignment(
                    load_name=str(r.get('LoadName', 'U1')).strip(),
                    function_name=str(r.get('Function', '')).strip(),
                    angle=safe_float(r, 'Angle', 0.0),
                    sf=sf
                )
                case_obj.assignments.append(assignment)

    ctx.response_spectrum_cases = cases


def handle_auto_seismic(ctx: LoadContext, df: pd.DataFrame):
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


def handle_section_cuts_gen(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    if not hasattr(ctx, 'section_cuts'):
        ctx.section_cuts = {}

    for _, row in df.iterrows():
        name = str(row.get('CutName', '')).strip()
        if not name:
            continue

        defined_by_str = str(row.get('DefinedBy', 'Quad')).strip()
        try:
            defined_by = SectionCutDefinedBy(defined_by_str)
        except ValueError:
            defined_by = SectionCutDefinedBy.QUAD

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
    if df.empty:
        return
    if not hasattr(ctx, 'section_cuts'):
        ctx.section_cuts = {}

    for _, row in df.iterrows():
        name = str(row.get('SectionCut', '')).strip()
        if not name:
            continue

        if name not in ctx.section_cuts:
            ctx.section_cuts[name] = SectionCut(name=name, quad=QuadDefinition(points=[]))

        x = ctx.units.L(safe_float(row, 'X'))
        y = ctx.units.L(safe_float(row, 'Y'))
        z = ctx.units.L(safe_float(row, 'Z'))

        sc_obj = ctx.section_cuts[name]
        if sc_obj.quad is None:
            sc_obj.quad = QuadDefinition(points=[])
        sc_obj.quad.points.append((x, y, z))

def handle_grid_lines(ctx: LoadContext, df: pd.DataFrame):
    """GRID LINES"""
    ctx.df_grid_lines = df
    if df.empty:
        return
    
    for _, r in df.iterrows():
        sys_name = str(r.get('CoordSys', 'Global')).strip()
        line_id = str(r.get('GridID', r.get('ID', ''))).strip()
        
        # SAP2000 tablosundaki gerçek koordinat kolonu: 'XRYZCoord'
        ordinate = safe_float(r, 'XRYZCoord', safe_float(r, 'Ordinate', 0.0))
        
        # Aks yönü: 'AxisDir' (X, Y veya Z)
        axis_dir = str(r.get('AxisDir', r.get('LineType', 'X'))).strip().upper()

        if line_id:
            ctx.grid_lines.append({
                'coord_sys': sys_name,
                'id': line_id,
                'ordinate': ctx.units.L(ordinate),
                'axis_dir': axis_dir,  # Hangi eksende olduğunu buraya kaydediyoruz
                'bubble': str(r.get('Bubble', '')).strip(),
            })

def handle_joint_constraints(ctx: LoadContext, df: pd.DataFrame):
    """JOINT CONSTRAINT ASSIGNMENTS"""
    ctx.df_joint_constraints = df
    if df.empty:
        return
    for _, r in df.iterrows():
        joint_id = str(r.get('Joint', '')).strip()
        constraint_name = str(r.get('Constraint', '')).strip()
        if joint_id and constraint_name:
            ctx.joint_constraints[joint_id] = constraint_name

def handle_link_props_linear(ctx: LoadContext, df: pd.DataFrame):
    """LINK PROPERTY DEFINITIONS 02 - LINEAR"""
    ctx.df_link_props_linear = df
    if df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get('LinkProp', r.get('Link', '') )).strip()
        if not name:
            continue
        
        if name not in ctx.link_props:
            ctx.link_props[name] = LinkPropLinear(name=name, prop_type=LinkPropType.LINEAR)
        
        prop = ctx.link_props[name]
        if isinstance(prop, LinkPropLinear):
            # U1, U2, U3, R1, R2, R3 rijitlik (stiffness) ve sönüm (damping) değerleri
            for i, dof in enumerate(['u1', 'u2', 'u3', 'rx', 'ry', 'rz'], start=1):
                k_val = safe_float(r, f'K{i}', safe_float(r, f'Stiff{i}', 0.0))
                c_val = safe_float(r, f'C{i}', safe_float(r, f'Damp{i}', 0.0))
                if hasattr(prop, f'stiff_{dof}'):
                    setattr(prop, f'stiff_{dof}', ctx.units.F(k_val) if i<=3 else ctx.units.M(k_val))
                if hasattr(prop, f'damp_{dof}'):
                    setattr(prop, f'damp_{dof}', c_val)

def handle_frame_insertion_points(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get('Frame', '')).strip()
        if not fid:
            continue
        ctx.frame_insertion_points[fid] = {
            'cardinal_pt': str(r.get('CardinalPt', '10 (centroid)')).strip(),
            'jt_offset_xi': ctx.units.L(safe_float(r, 'JtOffsetXI', 0.0)),
            'jt_offset_yi': ctx.units.L(safe_float(r, 'JtOffsetYI', 0.0)),
            'jt_offset_zi': ctx.units.L(safe_float(r, 'JtOffsetZI', 0.0)),
            'jt_offset_xj': ctx.units.L(safe_float(r, 'JtOffsetXJ', 0.0)),
            'jt_offset_yj': ctx.units.L(safe_float(r, 'JtOffsetYJ', 0.0)),
            'jt_offset_zj': ctx.units.L(safe_float(r, 'JtOffsetZJ', 0.0)),
            'mirror2': str(r.get('Mirror2', 'No')).strip().upper() == 'YES',
            'mirror3': str(r.get('Mirror3', 'No')).strip().upper() == 'YES',
            'transform': str(r.get('Transform', 'Yes')).strip().upper() == 'YES',
        }

def handle_frame_end_offsets(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get('Frame', '')).strip()
        if not fid:
            continue
        ctx.frame_end_offsets[fid] = {
            'length_i': ctx.units.L(safe_float(r, 'LengthI', 0.0)),
            'length_j': ctx.units.L(safe_float(r, 'LengthJ', 0.0)),
            'rigid_factor': safe_float(r, 'RigidFactor', 0.5),
        }

def handle_frame_section_concrete_column(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        sname = str(r.get('SectionName', '')).strip()
        if not sname:
            continue
        ctx.frame_section_rebar[sname] = {
            'rebar_mat_l': str(r.get('RebarMatL', '')).strip(),
            'rebar_mat_c': str(r.get('RebarMatC', '')).strip(),
            'reinf_config': str(r.get('ReinfConfig', 'Rectangular')).strip(),
            'lat_reinf': str(r.get('LatReinf', 'Ties')).strip(),
            'cover': ctx.units.L(safe_float(r, 'Cover', 0.04)),
            'num_bars3': int(safe_float(r, 'NumBars3Dir', 3)),
            'num_bars2': int(safe_float(r, 'NumBars2Dir', 3)),
            'bar_size_l': str(r.get('BarSizeL', '#9')).strip(),
            'bar_size_c': str(r.get('BarSizeC', '#4')).strip(),
            'spacing_c': ctx.units.L(safe_float(r, 'SpacingC', 0.15)),
            'num_cbars2': int(safe_float(r, 'NumCBars2', 3)),
            'num_cbars3': int(safe_float(r, 'NumCBars3', 3)),
            'reinf_type': str(r.get('ReinfType', 'Design')).strip(),
        }

def handle_frame_section_concrete_beam(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        sname = str(r.get('SectionName', '')).strip()
        if not sname:
            continue
        d = ctx.frame_section_rebar.setdefault(sname, {})
        d.update({
            'top_cover': ctx.units.L(safe_float(r, 'TopCover', 0.06)),
            'bot_cover': ctx.units.L(safe_float(r, 'BotCover', 0.06)),
            'top_left_area': ctx.units.L2(safe_float(r, 'TopLeftArea', 0.0)) ** 2,
            'top_right_area': ctx.units.L2(safe_float(r, 'TopRghtArea', 0.0)) ** 2,
            'bot_left_area': ctx.units.L2(safe_float(r, 'BotLeftArea', 0.0)) ** 2,
            'bot_right_area': ctx.units.L2(safe_float(r, 'BotRghtArea', 0.0)) ** 2,
        })

def handle_frame_section_time_dependent(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        sname = str(r.get('SectionName', '')).strip()
        if not sname:
            continue
        d = ctx.frame_section_rebar.setdefault(sname, {})
        d.update({
            'type_size': str(r.get('TypeSize', 'Auto')).strip(),
            'auto_sf_size': safe_float(r, 'AutoSFSize', 1.0),
        })

def handle_material_concrete_data(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get('Material', '')).strip()
        if not name:
            continue
        mat = ctx.materials.get(name)
        if mat is None:
            mat = Material(name=name, mat_type=MatType.CONCRETE)
            ctx.materials[name] = mat
        mat.fc = ctx.units.E(safe_float(r, 'Fc', 0.0))
        mat.fu = ctx.units.E(safe_float(r, 'Fu', 0.0))
        # unit weight: F/L³ → N/mm³; kg/m³'e çevirmek istersen *1e9/9.80665
        mat.unit_weight = safe_float(r, 'UnitWeight', 0.0)

def handle_material_rebar_data(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get('Material', '')).strip()
        if not name:
            continue
        mat = ctx.materials.get(name)
        if mat is None:
            mat = Material(name=name, mat_type=MatType.REBAR)
            ctx.materials[name] = mat
        mat.fy = ctx.units.E(safe_float(r, 'Fy', 0.0))
        mat.fu = ctx.units.E(safe_float(r, 'Fu', 0.0))
        mat.E1 = ctx.units.E(safe_float(r, 'E', mat.E1))

def handle_rebar_sizes(ctx: LoadContext, df: pd.DataFrame):
    if df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get('RebarSize', r.get('Name', ''))).strip()
        if not name:
            continue
        ctx.rebar_sizes[name] = {
            'diameter': ctx.units.L(safe_float(r, 'Diameter', 0.0)),
            'area': ctx.units.L2(safe_float(r, 'Area', 0.0)),
        }

def handle_sd_general(ctx, df):
    """SECTION DESIGNER PROPERTIES 01 - GENERAL"""
    ctx.df_sd_general = df
    for _, r in df.iterrows():
        name = str(r.get('SectionName','')).strip()
        if not name: continue
        sd = ctx.sd_sections.setdefault(name, SDSection(name=name))
        sd.design_type = str(r.get('DesignType','No Check/Design')).strip()
        sd.axis_angle = safe_float(r, 'AxisAngle', 90.0)
        # base material tablo 04+'da ShapeMat olarak geliyor; buradan da alabiliriz

def handle_sd_polygon(ctx, df):
    ctx.df_sd_polygon = df
    parse_sd_polygon_table(df, ctx)

def handle_sd_rebar_rect(ctx, df):
    """SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE"""
    ctx.df_sd_rect = df
    for _, r in df.iterrows():
        sec = str(r.get('SectionName','')).strip()
        if not sec: continue
        sd = ctx.sd_sections.setdefault(sec, SDSection(name=sec))
        sd.rect_rebars.append({
            'shape': str(r.get('ShapeName','')).strip(),
            'material': str(r.get('ShapeMat','')).strip(),
            'x_center': ctx.units.L(safe_float(r,'XCenter')),
            'y_center': ctx.units.L(safe_float(r,'YCenter')),
            'height': ctx.units.L(safe_float(r,'Height')),
            'width': ctx.units.L(safe_float(r,'Width')),
            'rotation': safe_float(r,'Rotation'),
        })

PRIORITY = {
    "PROGRAM CONTROL":                                  10,
    "PROJECT INFORMATION":                              11,
    "GRID LINES":                                       12,

    "MATERIAL PROPERTIES 01 - GENERAL":                 20,
    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": 21,

    "SECTION DESIGNER PROPERTIES 01 - GENERAL": 29,
    "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON": 29,
    "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": 29,
    "SECTION DESIGNER PROPERTIES 18 - SHAPE REINFORCING LINE": 29,
    "SECTION DESIGNER PROPERTIES 02 - REINFORCING AT SHAPE EDGES": 29,
    "SECTION DESIGNER PROPERTIES 03 - REINFORCING AT SHAPE CORNERS": 29,
    "SECTION DESIGNER PROPERTIES 30 - FIBER GENERAL": 29,

    "FRAME SECTION PROPERTIES 01 - GENERAL":            30,
    "FRAME SECTION PROPERTIES 04 - AUTO SELECT":         31,
    "AREA SECTION PROPERTIES":                          32,
    "LINK PROPERTY DEFINITIONS 01 - GENERAL":           33,
    "LINK PROPERTY DEFINITIONS 02 - LINEAR":            34,

    "LOAD PATTERN DEFINITIONS":                         40,
    "LOAD CASE DEFINITIONS":                            41,
    "CASE - STATIC 1 - LOAD ASSIGNMENTS":               42,
    "CASE - MODAL 1 - GENERAL":                         43,
    "COMBINATION DEFINITIONS":                          44,
    "MASS SOURCE":                                      45,

    "JOINT COORDINATES":                                50,
    "JOINT RESTRAINT ASSIGNMENTS":                      51,
    "CONNECTIVITY - FRAME":                             52,
    "CONNECTIVITY - AREA":                              53,
    "CONNECTIVITY - LINK":                              54,
    "JOINT CONSTRAINT ASSIGNMENTS":                     55,

    "FRAME SECTION ASSIGNMENTS":                        60,
    "AREA SECTION ASSIGNMENTS":                         61,
    "LINK PROPERTY ASSIGNMENTS":                        62,
    "FRAME RELEASE ASSIGNMENTS 1 - GENERAL":            63,
    "FRAME PROPERTY MODIFIERS":                         64,
    "FRAME DESIGN PROCEDURES":                          65,
    "FRAME AUTO MESH ASSIGNMENTS":                      66,
    "FRAME OUTPUT STATION ASSIGNMENTS":                 67,
    "FRAME LOAD TRANSFER OPTIONS":                      68,
    "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL":         69,
    "CONSTRAINT DEFINITIONS - DIAPHRAGM":               70,

    "JOINT LOADS - FORCE":                              75,
    "FRAME LOADS - GRAVITY":                            76,
    "FRAME LOADS - DISTRIBUTED":                        77,
    "FRAME LOADS - POINTS":                             78,
    "FRAME LOADS - TEMPERATURE":                        79,
    "AREA LOADS - UNIFORM":                             80,
    "AREA LOADS - UNIFORM TO FRAME":                    81,
    "AREA LOADS - WIND PRESSURE COEFFICIENTS":          82,

    "FUNCTION - RESPONSE SPECTRUM - TSC-2018":          85,
    "FUNCTION - RESPONSE SPECTRUM - FILE":              86,
    "FUNCTION - RESPONSE SPECTRUM - USER":              87,
    "CASE - RESPONSE SPECTRUM 1 - GENERAL":             88,
    "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS":    89,
    "AUTO SEISMIC - TSC-2018":                          90,
    
    "SECTION CUTS 1 - GENERAL":                         95,
    "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS":       96,
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
        "SECTION DESIGNER PROPERTIES 01 - GENERAL":         handle_sd_general,
        "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON":   handle_sd_polygon,
        "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": handle_sd_rebar_rect,

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
        "FRAME PROPERTY MODIFIERS":                         handle_frame_modifiers,
        "FRAME DESIGN PROCEDURES":                          handle_frame_design_procs,
        "FRAME AUTO MESH ASSIGNMENTS":                      handle_frame_auto_mesh,
        "FRAME OUTPUT STATION ASSIGNMENTS":                 handle_frame_output_stations,
        "FRAME LOAD TRANSFER OPTIONS":                      handle_frame_load_transfer_options,
        "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL":         handle_frame_local_axes,
        "CONSTRAINT DEFINITIONS - DIAPHRAGM":               handle_diaphragms,

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
        "GRID LINES":                                       handle_grid_lines,
        "LINK PROPERTY DEFINITIONS 02 - LINEAR":            handle_link_props_linear,
        "JOINT CONSTRAINT ASSIGNMENTS":                     handle_joint_constraints,
    }


def build_sorted_router() -> List[Tuple[str, Callable]]:
    router = build_router()
    items = [(name, handler, get_priority(name)) for name, handler in router.items()]
    items.sort(key=lambda x: x[2])
    return [(name, handler) for name, handler, _ in items]