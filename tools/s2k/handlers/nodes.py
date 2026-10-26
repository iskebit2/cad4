# tools/s2k/handlers/nodes.py
"""JOINT COORDINATES, RESTRAINTS, CONSTRAINTS, DIAPHRAGMS."""
import pandas as pd

from domain.definition import PointLoad
from tools.s2k.context import LoadContext


def handle_joints(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_joints = df


def handle_joint_restraints(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_restraints = df


def handle_joint_constraints(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_joint_constraints = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        jid = str(r.get("Joint", "")).strip()
        cname = str(r.get("Constraint", "")).strip()
        if jid and cname:
            ctx.joint_constraints[jid] = cname


def handle_diaphragms(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_diaphragms = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get("Name", "")).strip()
        if name:
            ctx.diaphragms[name] = {
                "coord_sys": str(r.get("CoordSys", "GLOBAL")).strip(),
                "axis": str(r.get("Axis", "Z")).strip(),
                "multi_level": str(r.get("MultiLevel", "No")).strip().upper() == "YES",
            }

def handle_joint_loads(ctx: LoadContext, df: pd.DataFrame):
    """
    S2K 'JOINT LOADS' tablosu.
    Kolonlar genelde: Joint, LoadPat, CoordSys, F1, F2, F3, M1, M2, M3
    Birim: S2K CurrUnits (from_sys) — finalize_and_convert N_MM'ye çevirir.
    """
    if df is None or df.empty:
        return

    def _f(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    for _, row in df.iterrows():
        joint = str(row.get("Joint", "")).strip()
        pattern = str(row.get("LoadPat", "")).strip()
        if not joint or not pattern:
            continue

        pl = PointLoad(
            pattern_name=pattern,
            fx=_f(row.get("F1")),
            fy=_f(row.get("F2")),
            fz=_f(row.get("F3")),
            mx=_f(row.get("M1")),
            my=_f(row.get("M2")),
            mz=_f(row.get("M3")),
        )
        ctx.joint_loads.setdefault(joint, []).append(pl)