# tools/s2k/handlers/nodes.py
"""JOINT COORDINATES, RESTRAINTS, CONSTRAINTS, DIAPHRAGMS."""
import pandas as pd

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