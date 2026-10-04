# tools/s2k/handlers.py
"""
Router handler'ları — DataFrame → LoadContext.
"""
from typing import Dict

import pandas as pd

from logging_config import CadLogger
from domain.definition import (
    AutoSeismicTSC2018, MatType, Material, ResponseSpectrumCase, 
    ResponseSpectrumLoadAssignment, Section, LinkPropLinear, LinkPropType,
    LoadPattern, LoadCase, LoadCombination, ModalCase,
    ComboItem, SiteInformation, SpectrumFunction, SpectrumSourceType, StaticLoadAssignment, SiteInformation, GeneralProjectInfo,
)
from tools.s2k.context import LoadContext
from tools.s2k.units import UnitConverter
from tools.s2k.utils import (
    get_color_from_string, parse_sap_mat_type,
    map_sap_to_local_params, safe_float
)

logger = CadLogger.get(__name__)


# ============================================================
# 1. PROGRAM & PROJE BİLGİLERİ
# ============================================================

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
# 2. MALZEME
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
# 3. KESİTLER
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
        link_id = str(row.get('Link', '')).strip()
        prop_name = str(row.get('LinkType', 'LINEAR')).strip()
        if not link_id:
            continue
        
        ctx.link_props[link_id] = LinkPropLinear(
            name=prop_name,
            prop_type=LinkPropType.LINEAR,
        )


# ============================================================
# 4. GEOMETRİ & ATAMALAR (Ham DataFrames)
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
# 5. YÜK TANIMLARI & ANALİZ CASE'LERİ
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
            guid=str(row.get('GUID', '')).strip() or None,
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
            guid=str(row.get('GUID', '')).strip() or None,
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
                guid=str(row.get('GUID', '')).strip() or None,
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
# 6. YÜKLER (Ham DataFrames)
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
# 7. DİNAMİK / SPEKTRUM & AUTO SEISMIC PARSER
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