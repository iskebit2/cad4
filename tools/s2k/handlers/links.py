# tools/s2k/handlers/links.py
"""LINK PROPERTIES 01/02, CONNECTIVITY - LINK, LINK PROPERTY ASSIGNMENTS.

Birim sözleşmesi: S2K değerleri float (S2K CurrUnits).
`convert_project_units` LinkPropLinear.__unit_schema__ üzerinden dönüştürür.
"""
from __future__ import annotations

import logging

import pandas as pd

from data.enums import LinkPropType
from domain.definition import LinkPropLinear
from tools.s2k.context import LoadContext

logger = logging.getLogger(__name__)

_DOF_ORDER = ("U1", "U2", "U3", "R1", "R2", "R3")


# ============================================================================
# YARDIMCILAR
# ============================================================================
def _safe_float(row, key, default: float = 0.0) -> float:
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan", "NaN"):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _pick_name(row) -> str:
    """LINK satırından prop adını çıkar (v10/v25 uyumlu)."""
    for key in ("LinkProp", "Link", "Name", "Prop"):
        val = row.get(key)
        if val is not None:
            s = str(val).strip()
            if s and s.lower() != "nan":
                return s
    return ""


def _pick_stiffness(row, i: int) -> float:
    """S2K'ta olası kolon adları: Ke1..Ke6 → K1..K6 → Stiff1..Stiff6."""
    return _safe_float(
        row, f"Ke{i}",
        _safe_float(row, f"K{i}",
                    _safe_float(row, f"Stiff{i}", 0.0)),
    )


def _pick_damping(row, i: int) -> float:
    """S2K'ta olası kolon adları: Ce1..Ce6 → C1..C6 → Damp1..Damp6."""
    return _safe_float(
        row, f"Ce{i}",
        _safe_float(row, f"C{i}",
                    _safe_float(row, f"Damp{i}", 0.0)),
    )


def _pick_bool(row, key: str, default: bool = True) -> bool:
    val = row.get(key)
    if val is None:
        return default
    s = str(val).strip().upper()
    if s in ("YES", "TRUE", "1"):
        return True
    if s in ("NO", "FALSE", "0"):
        return False
    return default


# ============================================================================
# 01 - GENERAL
# ============================================================================
def handle_link_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    """LINK PROPERTIES 01 - GENERAL.

    Kolonlar: Link / LinkProp, LinkType, DOF1..DOF6, Fixed1..Fixed6
    """
    if df is None or df.empty:
        return

    for _, row in df.iterrows():
        name = _pick_name(row)
        if not name:
            continue

        prop = ctx.link_props.get(name)
        if prop is None:
            prop_type = LinkPropType.from_sap(
                str(row.get("LinkType", "LINEAR")).strip()
            )
            prop = LinkPropLinear(name=name, prop_type=prop_type)
            ctx.link_props[name] = prop

        if not isinstance(prop, LinkPropLinear):
            continue

        # DOF aktif/pasif (varsayılan: hepsi aktif)
        for i, dof in enumerate(_DOF_ORDER, start=1):
            prop.DOF[dof] = _pick_bool(row, f"DOF{i}", True)
            fixed_val = row.get(f"Fixed{i}")
            if fixed_val is not None:
                prop.Fixed[dof] = _pick_bool(row, f"Fixed{i}", False)


# ============================================================================
# 02 - LINEAR
# ============================================================================
def handle_link_props_linear(ctx: LoadContext, df: pd.DataFrame) -> None:
    """LINK PROPERTIES 02 - LINEAR.

    Kolonlar: LinkProp, Ke1..Ke6, Ce1..Ce6  (K1/Stiff1, C1/Damp1 alias)
    """
    if df is None or df.empty:
        return

    for _, row in df.iterrows():
        name = _pick_name(row)
        if not name:
            continue

        prop = ctx.link_props.setdefault(name, LinkPropLinear(name=name))
        if not isinstance(prop, LinkPropLinear):
            logger.warning(
                "[LinkProp] '%s' LinkPropLinear değil, atlanıyor", name,
            )
            continue

        for i, dof in enumerate(_DOF_ORDER, start=1):
            prop.Ke[dof] = _pick_stiffness(row, i)
            prop.Ce[dof] = _pick_damping(row, i)


# ============================================================================
# CONNECTIVITY / ASSIGNMENTS
# ============================================================================
def handle_link_conn(ctx: LoadContext, df: pd.DataFrame) -> None:
    """CONNECTIVITY - LINK."""
    ctx.df_link_conn = df


def handle_link_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    """LINK PROPERTY ASSIGNMENTS.

    Kolonlar: Link, Prop / LinkProp / PropName
    """
    ctx.df_link_assign = df