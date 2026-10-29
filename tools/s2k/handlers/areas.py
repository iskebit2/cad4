# tools/s2k/handlers/areas.py
"""AREA CONNECTIVITY, ASSIGNMENTS."""
import pandas as pd

from tools.s2k.context import LoadContext

def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def handle_area_conn(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_conn = df


def handle_area_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_assign = df

def handle_area_section_design(ctx: LoadContext, df: pd.DataFrame) -> None:
    """AREA SECTION PROPERTY DESIGN PARAMETERS."""
    ctx.df_area_section_design = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get("Section", "")).strip()
        if not name:
            continue
        ctx.area_section_design_params[name] = {
            "rebar_mat": str(r.get("RebarMat", "")).strip(),
            "rebar_opt": str(r.get("RebarOpt", "Default")).strip(),
        }


def handle_area_section_time_dep(ctx: LoadContext, df: pd.DataFrame) -> None:
    """AREA SECTION PROPERTY - TIME DEPENDENT."""
    ctx.df_area_section_time_dep = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get("Section", "")).strip()
        if not name:
            continue
        ctx.area_section_time_dependent[name] = {
            "type_size": str(r.get("TypeSize", "Auto")).strip(),
            "auto_sf_size": _safe_float(r, "AutoSFSize", 1.0),
        }