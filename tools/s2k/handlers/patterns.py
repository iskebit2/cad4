# tools/s2k/handlers/patterns.py
"""LOAD PATTERN, CASE, COMBO, MASS SOURCE."""
import pandas as pd

from domain.definition import (
    ComboItem,
    LoadCase,
    LoadCombination,
    LoadPattern,
    ModalCase,
    StaticLoadAssignment,
)
from tools.s2k.context import LoadContext


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def handle_load_patterns(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("LoadPat", "")).strip()
        if not name:
            continue
        ctx.load_patterns[name] = LoadPattern(
            name=name,
            design_type=str(row.get("DesignType", "Dead")).strip(),
            self_wt_mult=_safe_float(row, "SelfWtMult", 0.0),
        )


def handle_load_cases(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Case", "")).strip()
        if not name:
            continue
        ctx.load_cases[name] = LoadCase(
            name=name,
            case_type=str(row.get("Type", "LinStatic")).strip(),
            initial_cond=str(row.get("InitialCond", "Zero")).strip(),
            design_type=str(row.get("DesignType", "Dead")).strip(),
            design_act=str(row.get("DesignAct", "Non-Composite")).strip(),
            auto_type=str(row.get("AutoType", "None")).strip(),
            run_case=str(row.get("RunCase", "Yes")).strip().upper() == "YES",
        )


def handle_static_assignments(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        case = ctx.load_cases.get(str(row.get("Case", "")).strip())
        if case is None:
            continue
        case.static_assignments.append(StaticLoadAssignment(
            load_type=str(row.get("LoadType", "Load pattern")).strip(),
            load_name=str(row.get("LoadName", "")).strip(),
            load_sf=_safe_float(row, "LoadSF", 1.0),
        ))


def handle_modal_cases(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Case", "")).strip()
        if not name:
            continue
        ctx.modal_cases[name] = ModalCase(
            name=name,
            mode_type=str(row.get("ModeType", "Eigen")).strip(),
            max_num_modes=int(_safe_float(row, "MaxNumModes", 12)),
            min_num_modes=int(_safe_float(row, "MinNumModes", 1)),
            eigen_shift=_safe_float(row, "EigenShift", 0.0),
            eigen_cutoff=_safe_float(row, "EigenCutoff", 0.0),
            eigen_tol=_safe_float(row, "EigenTol", 1e-9),
            auto_shift=str(row.get("AutoShift", "Yes")).strip().upper() == "YES",
        )


def handle_combinations(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("ComboName", "")).strip()
        if not name:
            continue
        if name not in ctx.load_combos:
            ctx.load_combos[name] = LoadCombination(
                name=name,
                combo_type=str(row.get("ComboType", "Linear Add")).strip(),
                auto_design=str(row.get("AutoDesign", "No")).strip().upper() == "YES",
            )
        case_or_pat = str(row.get("CaseName", "")).strip()
        if case_or_pat:
            ctx.load_combos[name].items.append(ComboItem(
                case_or_pattern_name=case_or_pat,
                scale_factor=_safe_float(row, "ScaleFactor", 1.0),
            ))


def handle_mass_source(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        pattern = str(row.get("LoadPat", "")).strip()
        if pattern:
            ctx.mass_source_map[pattern] = _safe_float(row, "Multiplier", 1.0)