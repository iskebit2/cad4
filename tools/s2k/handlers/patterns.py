# tools/s2k/handlers/patterns.py
"""LOAD PATTERN, CASE, COMBO, MASS SOURCE — v10 + v25 uyumlu."""
from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _str(row, key, default="") -> str:
    v = row.get(key)
    if v is None:
        return default
    s = str(v).strip()
    return s if s and s.lower() != "nan" else default


# ============================================================================
# v25 — LOAD PATTERN DEFINITIONS
# ============================================================================
def _handle_load_patterns_v25(ctx: LoadContext, df: pd.DataFrame) -> None:
    """v25: LoadPat, DesignType, SelfWtMult."""
    for _, row in df.iterrows():
        name = _str(row, "LoadPat")
        if not name:
            continue
        ctx.load_patterns[name] = LoadPattern(
            name=name,
            design_type=_str(row, "DesignType", "Dead"),
            self_wt_mult=_safe_float(row, "SelfWtMult", 0.0),
        )


# ============================================================================
# v10 — LOAD CASE DEFINITIONS (aslında load pattern)
# ============================================================================
def _handle_load_patterns_v10(ctx: LoadContext, df: pd.DataFrame) -> None:
    """v10: LoadCase, DesignType, SelfWtMult — bu tablo LOAD PATTERN'dir."""
    for _, row in df.iterrows():
        name = _str(row, "LoadCase")
        if not name:
            continue
        ctx.load_patterns[name] = LoadPattern(
            name=name,
            design_type=_str(row, "DesignType", "Dead"),
            self_wt_mult=_safe_float(row, "SelfWtMult", 0.0),
        )


# ============================================================================
# v25 — LOAD CASE DEFINITIONS
# ============================================================================
def _handle_load_cases_v25(ctx: LoadContext, df: pd.DataFrame) -> None:
    """v25: Case, Type, InitialCond, DesignType, ..."""
    for _, row in df.iterrows():
        name = _str(row, "Case")
        if not name:
            continue
        ctx.load_cases[name] = LoadCase(
            name=name,
            case_type=_str(row, "Type", "LinStatic"),
            initial_cond=_str(row, "InitialCond", "Zero"),
            design_type=_str(row, "DesignType", "Dead"),
            design_act=_str(row, "DesignAct", "Non-Composite"),
            auto_type=_str(row, "AutoType", "None"),
            run_case=_str(row, "RunCase", "Yes").upper() == "YES",
        )


# ============================================================================
# v10 — ANALYSIS CASE DEFINITIONS
# ============================================================================
def _handle_load_cases_v10(ctx: LoadContext, df: pd.DataFrame) -> None:
    """v10: ANALYSIS CASE DEFINITIONS — Case, Type, InitialCond, RunCase, ModalCase."""
    for _, row in df.iterrows():
        name = _str(row, "Case")
        if not name:
            continue
        ctx.load_cases[name] = LoadCase(
            name=name,
            case_type=_str(row, "Type", "LinStatic"),
            initial_cond=_str(row, "InitialCond", "Zero"),
            run_case=_str(row, "RunCase", "Yes").upper() == "YES",
        )


# ============================================================================
# UNIFIED — tablo adı aynı, kolonlara göre ayırt et
# ============================================================================
def handle_load_patterns(ctx: LoadContext, df: pd.DataFrame) -> None:
    """LOAD PATTERN DEFINITIONS — v25 (v10'da bu tablo yok)."""
    if df is None or df.empty:
        return
    _handle_load_patterns_v25(ctx, df)


def handle_load_cases(ctx: LoadContext, df: pd.DataFrame) -> None:
    """LOAD CASE DEFINITIONS — v25 (v10'da bu tablo LOAD PATTERN).

    Kolon kontrolü:
      - v25: 'Case' + 'Type' var → LoadCase
      - v10: 'LoadCase' var → LoadPattern
    """
    if df is None or df.empty:
        return

    if "Case" in df.columns and "Type" in df.columns:
        _handle_load_cases_v25(ctx, df)
    elif "LoadCase" in df.columns:
        _handle_load_patterns_v10(ctx, df)
    else:
        logger.debug(
            "[LoadCase] Bilinmeyen şema: %s", list(df.columns),
        )


def handle_analysis_cases_v10(ctx: LoadContext, df: pd.DataFrame) -> None:
    """v10: ANALYSIS CASE DEFINITIONS → LoadCase."""
    if df is None or df.empty:
        return
    _handle_load_cases_v10(ctx, df)


# ============================================================================
# STATIC / MODAL / COMBO / MASS — değişmedi
# ============================================================================
def handle_static_assignments(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        case = ctx.load_cases.get(_str(row, "Case"))
        if case is None:
            continue
        case.static_assignments.append(StaticLoadAssignment(
            load_type=_str(row, "LoadType", "Load pattern"),
            load_name=_str(row, "LoadName"),
            load_sf=_safe_float(row, "LoadSF", 1.0),
        ))


def handle_modal_cases(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = _str(row, "Case")
        if not name:
            continue
        ctx.modal_cases[name] = ModalCase(
            name=name,
            mode_type=_str(row, "ModeType", "Eigen"),
            max_num_modes=int(_safe_float(row, "MaxNumModes", 12)),
            min_num_modes=int(_safe_float(row, "MinNumModes", 1)),
            eigen_shift=_safe_float(row, "EigenShift", 0.0),
            eigen_cutoff=_safe_float(row, "EigenCutoff", 0.0),
            eigen_tol=_safe_float(row, "EigenTol", 1e-9),
            auto_shift=_str(row, "AutoShift", "Yes").upper() == "YES",
        )


def handle_combinations(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = _str(row, "ComboName")
        if not name:
            continue
        if name not in ctx.load_combos:
            ctx.load_combos[name] = LoadCombination(
                name=name,
                combo_type=_str(row, "ComboType", "Linear Add"),
                auto_design=_str(row, "AutoDesign", "No").upper() == "YES",
            )
        case_or_pat = _str(row, "CaseName")
        if case_or_pat:
            ctx.load_combos[name].items.append(ComboItem(
                case_or_pattern_name=case_or_pat,
                scale_factor=_safe_float(row, "ScaleFactor", 1.0),
            ))


def handle_mass_source(ctx: LoadContext, df: pd.DataFrame) -> None:
    # v25: MassSource Elements Masses Loads IsDefault (tek satır)
    # v10: LoadPat, Multiplier (çok satır)
    if "MassSource" in df.columns:
        # v25 — global mass source, pattern map yok
        return
    for _, row in df.iterrows():
        pattern = _str(row, "LoadPat")
        if pattern:
            ctx.mass_source_map[pattern] = _safe_float(row, "Multiplier", 1.0)