# tools/s2k/handlers/nodes.py
"""JOINT COORDINATES, RESTRAINTS, CONSTRAINTS, DIAPHRAGMS."""
import pandas as pd

from data.enums import ConstraintType
from domain.definition import PointLoad, ConstraintDefinition
from tools.s2k.context import LoadContext

def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _bool(v, default=False) -> bool:
    if v is None:
        return default
    return str(v).strip().upper() in ("YES", "TRUE", "1")


def _make_constraint_def(row, ctype: ConstraintType) -> ConstraintDefinition:
    return ConstraintDefinition(
        name=str(row.get("Name", "")).strip(),
        constraint_type=ctype,
        coord_sys=str(row.get("CoordSys", "GLOBAL")).strip(),
        axis=str(row.get("Axis", "Z")).strip(),
        ux=_bool(row.get("UX")),
        uy=_bool(row.get("UY")),
        uz=_bool(row.get("UZ")),
        rx=_bool(row.get("RX")),
        ry=_bool(row.get("RY")),
        rz=_bool(row.get("RZ")),
        u1=_bool(row.get("U1")),
        u2=_bool(row.get("U2")),
        u3=_bool(row.get("U3")),
        r1=_bool(row.get("R1")),
        r2=_bool(row.get("R2")),
        r3=_bool(row.get("R3")),
        multi_level=_bool(row.get("MultiLevel")),
        tolerance=_safe_float(row, "Tolerance"),
    )


def handle_constraint_definitions(ctx, df, ctype: ConstraintType):
    """Ortak: 9 constraint tablosu için tek handler."""
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        cd = _make_constraint_def(row, ctype)
        if not cd.name:
            continue
        ctx.constraint_definitions[cd.name] = cd
        # Diaphragm özel — eski `ctx.diaphragms` uyumu için
        if ctype == ConstraintType.DIAPHRAGM:
            ctx.diaphragms[cd.name] = {
                "coord_sys": cd.coord_sys,
                "axis": cd.axis,
                "multi_level": cd.multi_level,
            }

def handle_joint_springs(ctx: LoadContext, df: pd.DataFrame) -> None:
    """JOINT SPRING ASSIGNMENTS 1 - UNCOUPLED.

    Kolonlar: Joint, CoordSys, U1..U3, R1..R3
    Birim: S2K CurrUnits (F veya MOMENT) — convert_project_units çevirir.
    """
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        jid = str(row.get("Joint", "")).strip()
        if not jid:
            continue
        ctx.joint_springs[jid] = {
            "coord_sys": str(row.get("CoordSys", "Local")).strip(),
            "u1": _safe_float(row, "U1"),
            "u2": _safe_float(row, "U2"),
            "u3": _safe_float(row, "U3"),
            "r1": _safe_float(row, "R1"),
            "r2": _safe_float(row, "R2"),
            "r3": _safe_float(row, "R3"),
        }
        
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

def handle_joint_added_mass(ctx: LoadContext, df: pd.DataFrame) -> None:
    """JOINT ADDED MASS ASSIGNMENTS.

    v25/v10: Joint, CoordSys, Mass1, Mass2, Mass3, MMI1, MMI2, MMI3
    Birim: S2K CurrUnits — finalize_and_convert N_MM'ye çevirir.
    """
    if df is None or df.empty:
        return

    def _f(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    for _, row in df.iterrows():
        jid = str(row.get("Joint", "")).strip()
        if not jid:
            continue
        ctx.joint_added_mass[jid] = {
            "coord_sys": str(row.get("CoordSys", "Joint Local")).strip(),
            "mass1": _f(row.get("Mass1")),
            "mass2": _f(row.get("Mass2")),
            "mass3": _f(row.get("Mass3")),
            "mmi1":  _f(row.get("MMI1")),
            "mmi2":  _f(row.get("MMI2")),
            "mmi3":  _f(row.get("MMI3")),
        }