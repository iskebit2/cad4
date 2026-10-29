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
        if not fid:
            continue
        # v25: AutoMesh, v10: AutoDivide
        auto_val = r.get("AutoMesh", r.get("AutoDivide", "No"))
        ctx.frame_auto_mesh[fid] = {
            "auto_mesh": str(auto_val).strip().upper() == "YES",
            "at_joints": str(r.get("AtJoints", "Yes")).strip().upper() == "YES",
            "at_frames": str(r.get("AtFrames", "No")).strip().upper() == "YES",
            "num_segments": _safe_float(r, "NumSegments", 0.0),
            "max_length": _safe_float(r, "MaxLength", 0.0),
            "max_degrees": _safe_float(r, "MaxDegrees", 0.0),
        }

def handle_frame_output_stations(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME OUTPUT STATION ASSIGNMENTS (v25) / FRAME OUTPUT STATION ASSIGNMENTS (v10)."""
    ctx.df_frame_output_stations = df


def handle_frame_insertion_points(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME INSERTION POINT ASSIGNMENTS."""
    ctx.df_frame_insertion = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        ctx.frame_insertion_points[fid] = {
            "cardinal_pt": str(r.get("CardinalPt", "10 (centroid)")).strip(),
            "mirror2": str(r.get("Mirror2", "No")).strip(),
            "mirror3": str(r.get("Mirror3", "No")).strip(),
            "transform": str(r.get("Transform", "Yes")).strip(),
            "coord_sys": str(r.get("CoordSys", "Local")).strip(),
            "jt_offset_xi": _safe_float(r, "JtOffsetXI"),
            "jt_offset_yi": _safe_float(r, "JtOffsetYI"),
            "jt_offset_zi": _safe_float(r, "JtOffsetZI"),
            "jt_offset_xj": _safe_float(r, "JtOffsetXJ"),
            "jt_offset_yj": _safe_float(r, "JtOffsetYJ"),
            "jt_offset_zj": _safe_float(r, "JtOffsetZJ"),
        }


def handle_frame_end_offsets(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME OFFSET ALONG LENGTH ASSIGNMENTS."""
    ctx.df_frame_end_offsets = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        ctx.frame_end_offsets[fid] = {
            "type": str(r.get("Type", "User")).strip(),
            "length_i": _safe_float(r, "LengthI"),
            "length_j": _safe_float(r, "LengthJ"),
            "rigid_factor": _safe_float(r, "RigidFactor"),
        }


def handle_frame_local_axes(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL."""
    ctx.df_frame_local_axes = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        # rotation_deg zaten _parse_frame_assign'dan geliyor; v10 ek alanları sakla
        ctx.frame_local_axes[fid] = {
            "angle": _safe_float(r, "Angle", 0.0),
            "mirror_abt2": str(r.get("MirrorAbt2", "No")).strip(),
            "mirror_abt3": str(r.get("MirrorAbt3", "No")).strip(),
        }


def handle_frame_load_transfer(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME LOAD TRANSFER OPTIONS."""
    ctx.df_frame_load_transfer = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if fid:
            ctx.frame_load_transfer[fid] = str(r.get("Transfer", "Yes")).strip()


def handle_frame_section_rebar_col(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        ctx.frame_section_rebar.setdefault(sec, {}).update({
            "rebar_mat_l": str(r.get("RebarMatL", "")).strip(),
            "rebar_mat_c": str(r.get("RebarMatC", "")).strip(),
            "reinf_config": str(r.get("ReinfConfig", "")).strip(),
            "lat_reinf": str(r.get("LatReinf", "")).strip(),
            "cover": _safe_float(r, "Cover"),
            "num_bars3_dir": int(_safe_float(r, "NumBars3Dir", 0)),
            "num_bars2_dir": int(_safe_float(r, "NumBars2Dir", 0)),
            "bar_size_l": str(r.get("BarSizeL", "")).strip(),
            "bar_size_c": str(r.get("BarSizeC", "")).strip(),
            "spacing_c": _safe_float(r, "SpacingC"),
            "num_cbars2": int(_safe_float(r, "NumCBars2", 0)),
            "num_cbars3": int(_safe_float(r, "NumCBars3", 0)),
            "reinf_type": str(r.get("ReinfType", "")).strip(),
        })


def handle_frame_section_rebar_beam(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 03 - CONCRETE BEAM."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        ctx.frame_section_rebar.setdefault(sec, {}).update({
            "rebar_mat_l": str(r.get("RebarMatL", "")).strip(),
            "rebar_mat_c": str(r.get("RebarMatC", "")).strip(),
            "top_cover": _safe_float(r, "TopCover"),
            "bot_cover": _safe_float(r, "BotCover"),
            "top_left_area": _safe_float(r, "TopLeftArea"),
            "top_rght_area": _safe_float(r, "TopRghtArea"),
            "bot_left_area": _safe_float(r, "BotLeftArea"),
            "bot_rght_area": _safe_float(r, "BotRghtArea"),
        })


def handle_frame_time_dependent(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 13 - TIME DEPENDENT."""
    ctx.df_frame_time_dependent = df