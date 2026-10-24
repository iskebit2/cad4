# tools/s2k/handlers/loads.py
"""JOINT/FRAME/AREA LOADS — tüm birim dönüşümü UnitConverter üzerinden."""
import logging
from collections import defaultdict

import pandas as pd

from tools.s2k.context import LoadContext
from data.enums import LoadDirection
from domain.definition import PointLoad, FrameGravityLoad, FrameDistributedLoad

logger = logging.getLogger(__name__)


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _sap_dir_to_load_dir(s: str) -> LoadDirection:
    return {
        "1": LoadDirection.LOCAL_1, "2": LoadDirection.LOCAL_2, "3": LoadDirection.LOCAL_3,
        "X": LoadDirection.GLOBAL_X, "Y": LoadDirection.GLOBAL_Y, "Z": LoadDirection.GLOBAL_Z,
        "GX": LoadDirection.GLOBAL_X, "GY": LoadDirection.GLOBAL_Y, "GZ": LoadDirection.GLOBAL_Z,
        "GRAV": LoadDirection.GRAVITY, "GRAVITY": LoadDirection.GRAVITY,
        "PX": LoadDirection.PROJECTED_X, "PY": LoadDirection.PROJECTED_Y, "PZ": LoadDirection.PROJECTED_Z,
    }.get(str(s).strip().upper(), LoadDirection.GRAVITY)


def _sap_frame_dir_code(s: str) -> str:
    """Frame dist load 'Dir' → SAP internal code '1'..'10'."""
    return {
        "1": "1", "2": "2", "3": "3",
        "X": "4", "Y": "5", "Z": "6",
        "GLOBAL X": "4", "GLOBAL Y": "5", "GLOBAL Z": "6",
        "GRAVITY": "7", "GRAV": "7",
        "PROJECTEDX": "8", "PROJECTEDY": "9", "PROJECTEDZ": "10",
        "PROJ X": "8", "PROJ Y": "9", "PROJ Z": "10",
    }.get(str(s).strip().upper(), "2")


# ---------------------------------------------------------------------------
# JOINT LOADS
# ---------------------------------------------------------------------------
def handle_joint_loads(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_joint_loads = df


# ---------------------------------------------------------------------------
# FRAME LOADS
# ---------------------------------------------------------------------------
def handle_frame_gravity(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_gravity = df


def handle_frame_distributed(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_distributed = df


def handle_frame_points(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_points = df


def handle_frame_temperature(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_frame_temperature = df


# ---------------------------------------------------------------------------
# AREA LOADS
# ---------------------------------------------------------------------------
def handle_area_uniform(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_uniform = df


def handle_area_uniform_to_frame(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_uniform_to_frame = df


def handle_area_wind(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_wind = df