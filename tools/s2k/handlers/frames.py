# tools/s2k/handlers/frames.py
"""FRAME CONNECTIVITY, ASSIGNMENTS, RELEASES, MODIFIERS, DESIGN PROCS, AUTO MESH."""
import logging

import pandas as pd

from tools.s2k.context import LoadContext

logger = logging.getLogger(__name__)

def _to_bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().upper() in ("YES", "TRUE", "1")

def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return default
    try:
        f = float(val)
        if f != f:   # NaN
            return default
        return f
    except (TypeError, ValueError):
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
    """FRAME OUTPUT STATION ASSIGNMENTS.

    Kolonlar: Frame, StationType, MinNumSta, AddAtElmInt, AddAtPtLoad, MaxStaSpcg
    """
    if df is None or df.empty:
        return
    ctx.df_frame_output_stations = df
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        ctx.frame_output_stations[fid] = {
            "station_type": str(r.get("StationType", "MinNumSta")).strip(),
            "min_num_sta": int(_safe_float(r, "MinNumSta", 3)),
            "add_at_elm_int": _to_bool(r.get("AddAtElmInt"), True),
            "add_at_pt_load": _to_bool(r.get("AddAtPtLoad"), True),
            "max_sta_spcg": _safe_float(r, "MaxStaSpcg", 0.0) or None,
        }

def handle_frame_insertion_points(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME INSERTION POINT ASSIGNMENTS.

    Kolonlar: Frame, CardinalPt, Mirror2, Mirror3, Transform, CoordSys,
              JtOffsetXI/YI/ZI, JtOffsetXJ/YJ/ZJ
    """
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        ctx.frame_insertion_points[fid] = {
            "cardinal_pt": str(r.get("CardinalPt", "10 (centroid)")).strip(),
            "mirror2": _to_bool(r.get("Mirror2")),
            "mirror3": _to_bool(r.get("Mirror3")),
            "transform": _to_bool(r.get("Transform"), True),
            "coord_sys": str(r.get("CoordSys", "Local")).strip(),
            "jt_offset_xi": _safe_float(r, "JtOffsetXI"),
            "jt_offset_yi": _safe_float(r, "JtOffsetYI"),
            "jt_offset_zi": _safe_float(r, "JtOffsetZI"),
            "jt_offset_xj": _safe_float(r, "JtOffsetXJ"),
            "jt_offset_yj": _safe_float(r, "JtOffsetYJ"),
            "jt_offset_zj": _safe_float(r, "JtOffsetZJ"),
        }


def handle_frame_end_offsets(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME OFFSET ALONG LENGTH ASSIGNMENTS.

    Kolonlar: Frame, Type, LengthI, LengthJ, RigidFactor
    """
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
    """FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL.

    Kolonlar: Frame, Angle, MirrorAbt2, MirrorAbt3
    """
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid:
            continue
        ctx.frame_local_axes[fid] = {
            "angle": _safe_float(r, "Angle", 0.0),
            "mirror_abt2": _to_bool(r.get("MirrorAbt2")),
            "mirror_abt3": _to_bool(r.get("MirrorAbt3")),
        }


def handle_frame_load_transfer(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME LOAD TRANSFER OPTIONS.

    Kolonlar: Frame, Transfer
    """
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if fid:
            ctx.frame_load_transfer[fid] = _to_bool(r.get("Transfer"), True)



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
    """FRAME SECTION PROPERTIES 13 - TIME DEPENDENT.

    Kolonlar: SectionName, TypeSize, AutoSFSize
    """
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if sec:
            ctx.frame_time_dependent[sec] = {
                "type_size": str(r.get("TypeSize", "Auto")).strip(),
                "auto_sf_size": _safe_float(r, "AutoSFSize", 1.0),
            }