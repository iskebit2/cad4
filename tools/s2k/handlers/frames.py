# tools/s2k/handlers/frames.py
"""FRAME CONNECTIVITY, ASSIGNMENTS, RELEASES, MODIFIERS, DESIGN PROCS, AUTO MESH."""
import logging

import pandas as pd

from tools.s2k.context import LoadContext

logger = logging.getLogger(__name__)


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def handle_frame_conn(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_conn = df


def handle_frame_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_assign = df


def handle_frame_releases(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_release = df


def handle_frame_modifiers(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_modifiers = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if fid:
            ctx.frame_modifiers[fid] = {
                "amod": _safe_float(r, "AMod", 1.0),
                "as2mod": _safe_float(r, "AS2Mod", 1.0),
                "as3mod": _safe_float(r, "AS3Mod", 1.0),
                "jmod": _safe_float(r, "JMod", 1.0),
                "i22mod": _safe_float(r, "I22Mod", 1.0),
                "i33mod": _safe_float(r, "I33Mod", 1.0),
                "massmod": _safe_float(r, "MassMod", 1.0),
                "weightmod": _safe_float(r, "WeightMod", 1.0),
            }


def handle_frame_design_procs(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_design_procs = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if fid:
            ctx.frame_design_procs[fid] = str(r.get("DesignProc", "From Material")).strip()


def handle_frame_auto_mesh(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_auto_mesh = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if fid:
            ctx.frame_auto_mesh[fid] = {
                "auto_mesh": str(r.get("AutoMesh", "No")).strip().upper() == "YES",
                "at_joints": str(r.get("AtJoints", "Yes")).strip().upper() == "YES",
                "max_length": _safe_float(r, "MaxLength", 0.0),
            }