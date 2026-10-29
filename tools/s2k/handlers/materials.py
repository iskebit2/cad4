# tools/s2k/handlers/materials.py
"""MATERIAL PROPERTIES 01/02/03x/04/06/09 — v10 + v25 uyumlu."""
from __future__ import annotations

import logging

import pandas as pd

from data.enums import MatType
from domain.definition import Material
from tools.s2k.context import LoadContext
from tools.s2k.handlers._colors import color_from_string

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YARDIMCILAR
# ---------------------------------------------------------------------------
def _safe_float(row, key, default=0.0) -> float:
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _bool(row, key, default=False) -> bool:
    val = row.get(key)
    if val is None:
        return default
    return str(val).strip().upper() in ("YES", "TRUE", "1")


def _parse_mat_type(row) -> MatType:
    """v25: Type = Steel/Concrete/Rebar/Tendon/... ; v10: Type = Isotropic + DesignType = Concrete."""
    raw = str(row.get("Type", "")).upper().strip()
    if raw in ("STEEL", "CONCRETE", "REBAR", "TENDON", "ALUMINUM", "COLDFORMED"):
        return {
            "STEEL": MatType.STEEL, "CONCRETE": MatType.CONCRETE,
            "REBAR": MatType.REBAR, "TENDON": MatType.TENDON,
            "ALUMINUM": MatType.ALUMINUM, "COLDFORMED": MatType.COLDFORMED,
        }[raw]

    # v10: Type=Isotropic, DesignType=Concrete/Steel/...
    design = str(row.get("DesignType", "")).upper().strip()
    if design in ("CONCRETE", "STEEL"):
        return MatType.CONCRETE if design == "CONCRETE" else MatType.STEEL

    return MatType.NODESIGN


# ---------------------------------------------------------------------------
# 01 - GENERAL  (v25: meta; v10: meta + E/U/UnitMass/UnitWeight)
# ---------------------------------------------------------------------------
def handle_material_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    """MATERIAL PROPERTIES 01 - GENERAL.

    v25: Material Type Grade SymType TempDepend Color GUID Notes
    v10: Material Type DesignType UnitMass UnitWeight E U
         (E ve U buradadır; v25'te 02 tablosundadır)
    """
    # v10 tespiti: 01 tablosunda E ve UnitMass kolonları var mı?
    is_v10 = ("E" in df.columns and "UnitMass" in df.columns)

    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue

        mat = ctx.materials.get(name)
        if mat is None:
            mat = Material(name=name)
            ctx.materials[name] = mat

        mat.mat_type = _parse_mat_type(row)
        mat.color = color_from_string(str(row.get("Color", "Gray8Dark")))
        mat.grade = str(row.get("Grade", "")).strip()
        mat.sym_type = str(row.get("SymType", "Isotropic")).strip()
        mat.temp_depend = _bool(row, "TempDepend", False)
        mat.notes = str(row.get("Notes", "")).strip()
        mat.design_type = str(row.get("DesignType", "")).strip()

        # v10: E ve U burada
        if is_v10:
            E = _safe_float(row, "E", 0.0)
            nu = _safe_float(row, "U", 0.3)
            if E > 0:
                mat.E1 = mat.E2 = mat.E3 = E
                mat.nu12 = mat.nu13 = mat.nu23 = nu
                # G türet: G = E / (2(1+ν))
                if 0 < nu < 0.5:
                    G = E / (2.0 * (1.0 + nu))
                    mat.G12 = mat.G13 = mat.G23 = G
            unit_mass = _safe_float(row, "UnitMass", 0.0)
            if unit_mass > 0:
                mat.density = unit_mass
            # v10 Concrete için Fc henüz yok; 04 tablosundan gelecek


# ---------------------------------------------------------------------------
# 02 - BASIC MECHANICAL PROPERTIES (v25)
# ---------------------------------------------------------------------------
def handle_material_mech(ctx: LoadContext, df: pd.DataFrame) -> None:
    """MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES (yalnızca v25)."""
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))

        E = _safe_float(row, "E1", 0.0)
        G = _safe_float(row, "G12", 0.0)
        nu = _safe_float(row, "U12", 0.3)

        if E > 0:
            mat.E1 = mat.E2 = mat.E3 = E
        if G > 0:
            mat.G12 = mat.G13 = mat.G23 = G
        elif E > 0 and 0 < nu < 0.5:
            mat.G12 = mat.G13 = mat.G23 = E / (2.0 * (1.0 + nu))
        mat.nu12 = mat.nu13 = mat.nu23 = nu

        unit_mass = _safe_float(row, "UnitMass", 0.0)
        if unit_mass > 0:
            mat.density = unit_mass


# ---------------------------------------------------------------------------
# 03A - STEEL DATA (v25)
# ---------------------------------------------------------------------------
def handle_material_steel(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.mat_type = MatType.STEEL
        mat.fy = _safe_float(row, "Fy", mat.fy)
        mat.fu = _safe_float(row, "Fu", mat.fu)
        mat.eff_fy = _safe_float(row, "EffFy", 0.0)
        mat.eff_fu = _safe_float(row, "EffFu", 0.0)
        mat.ss_curve_opt = str(row.get("SSCurveOpt", "Simple")).strip()
        mat.ss_hys_type = str(row.get("SSHysType", "Kinematic")).strip()
        mat.s_hard = _safe_float(row, "SHard", 0.0)
        mat.s_max = _safe_float(row, "SMax", 0.0)
        mat.s_rup = _safe_float(row, "SRup", 0.0)
        mat.final_slope = _safe_float(row, "FinalSlope", -0.1)
        mat.coup_mod_type = str(row.get("CoupModType", "Von Mises")).strip()


# ---------------------------------------------------------------------------
# 03B - CONCRETE DATA (v25)
# ---------------------------------------------------------------------------
def handle_material_concrete(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.mat_type = MatType.CONCRETE
        mat.fc = _safe_float(row, "Fc", 0.0)
        mat.efc = _safe_float(row, "eFc", 0.0)
        mat.ltwt_conc = _bool(row, "LtWtConc", False)
        mat.ss_curve_opt = str(row.get("SSCurveOpt", "Mander")).strip()
        mat.ss_hys_type = str(row.get("SSHysType", "Takeda")).strip()
        mat.sfc = _safe_float(row, "SFc", 0.0)
        mat.s_cap = _safe_float(row, "SCap", 0.0)
        mat.final_slope = _safe_float(row, "FinalSlope", -0.1)
        mat.f_angle = _safe_float(row, "FAngle", 0.0)
        mat.d_angle = _safe_float(row, "DAngle", 0.0)
        mat.coup_mod_type = str(row.get("CoupModType", "Modified Darwin-Pecknold")).strip()


# ---------------------------------------------------------------------------
# 03E - REBAR DATA (v25)
# ---------------------------------------------------------------------------
def handle_material_rebar(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.mat_type = MatType.REBAR
        mat.fy = _safe_float(row, "Fy", mat.fy)
        mat.fu = _safe_float(row, "Fu", mat.fu)
        mat.eff_fy = _safe_float(row, "EffFy", 0.0)
        mat.eff_fu = _safe_float(row, "EffFu", 0.0)
        mat.rebar_ss_curve_opt = str(row.get("SSCurveOpt", "Simple")).strip()
        mat.rebar_ss_hys_type = str(row.get("SSHysType", "Kinematic")).strip()
        mat.rebar_s_hard = _safe_float(row, "SHard", 0.0)
        mat.rebar_s_cap = _safe_float(row, "SCap", 0.0)
        mat.rebar_use_ct_def = _bool(row, "UseCTDef", False)
        mat.coup_mod_type = str(row.get("CoupModType", "Von Mises")).strip()


# ---------------------------------------------------------------------------
# 03F - TENDON DATA (v25)
# ---------------------------------------------------------------------------
def handle_material_tendon(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.mat_type = MatType.TENDON
        mat.fy = _safe_float(row, "Fy", mat.fy)
        mat.fu = _safe_float(row, "Fu", mat.fu)
        mat.tendon_ss_curve_opt = str(row.get("SSCurveOpt", "")).strip()
        mat.tendon_ss_hys_type = str(row.get("SSHysType", "Kinematic")).strip()
        mat.final_slope = _safe_float(row, "FinalSlope", -0.1)
        mat.coup_mod_type = str(row.get("CoupModType", "Von Mises")).strip()


# ---------------------------------------------------------------------------
# 03J - COUPLED NONLINEAR VON MISES (v25)
# ---------------------------------------------------------------------------
def handle_material_von_mises(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.yield_stress = _safe_float(row, "YieldStress", 0.0)
        mat.lin_iso_hard = _bool(row, "LinIsoHard", False)
        mat.lin_kin_hard = _bool(row, "LinKinHard", False)
        mat.nl_iso_sa_hard = _bool(row, "NLIsoSaHard", False)


# ---------------------------------------------------------------------------
# 04 - DESIGN CONCRETE (yalnızca v10)
# ---------------------------------------------------------------------------
def handle_material_design_concrete_v10(ctx: LoadContext, df: pd.DataFrame) -> None:
    """MATERIAL PROPERTIES 04 - DESIGN CONCRETE (v10).

    Kolonlar: Material, Fc, RebarFy, RebarFys, LtWtConc, LtWtFact
    """
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.fc = _safe_float(row, "Fc", mat.fc)
        mat.rebar_fy = _safe_float(row, "RebarFy", 0.0)
        mat.rebar_fys = _safe_float(row, "RebarFys", 0.0)
        mat.ltwt_conc = _bool(row, "LtWtConc", mat.ltwt_conc)
        mat.ltwt_fact = _safe_float(row, "LtWtFact", 1.0)


# ---------------------------------------------------------------------------
# 06 - DAMPING PARAMETERS (v25)
# ---------------------------------------------------------------------------
def handle_material_damping(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.modal_ratio = _safe_float(row, "ModalRatio", 0.0)
        mat.vis_mass = _safe_float(row, "VisMass", 0.0)
        mat.vis_stiff = _safe_float(row, "VisStiff", 0.0)
        mat.hys_mass = _safe_float(row, "HysMass", 0.0)
        mat.hys_stiff = _safe_float(row, "HysStiff", 0.0)


# ---------------------------------------------------------------------------
# 09 - ACCEPTANCE CRITERIA (v25)
# ---------------------------------------------------------------------------
def handle_material_acceptance(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))
        mat.io_tens = _safe_float(row, "IOTens", 0.0)
        mat.ls_tens = _safe_float(row, "LSTens", 0.0)
        mat.cp_tens = _safe_float(row, "CPTens", 0.0)
        mat.io_comp = _safe_float(row, "IOComp", 0.0)
        mat.ls_comp = _safe_float(row, "LSComp", 0.0)
        mat.cp_comp = _safe_float(row, "CPComp", 0.0)
        mat.ignore_tens = _bool(row, "IgnoreTens", False)