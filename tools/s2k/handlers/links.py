# tools/s2k/handlers/links.py
"""LINK PROPERTIES 01/02, CONNECTIVITY - LINK, LINK PROPERTY ASSIGNMENTS."""
import logging

import pandas as pd

from data.enums import LinkPropType
from domain.definition import LinkPropLinear
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


def handle_link_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Link", row.get("LinkProp", row.get("Name", "")))).strip()
        if not name or name in ctx.link_props:
            continue
        prop_type = LinkPropType.from_sap(str(row.get("LinkType", "LINEAR")).strip())
        ctx.link_props[name] = LinkPropLinear(name=name, prop_type=prop_type)


def handle_link_props_linear(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        name = str(r.get("LinkProp", r.get("Link", ""))).strip()
        if not name:
            continue
        prop = ctx.link_props.setdefault(name, LinkPropLinear(name=name))
        if not isinstance(prop, LinkPropLinear):
            continue

        # S2K birimi — float, dönüşüm yok
        for i, dof in enumerate(("u1", "u2", "u3", "rx", "ry", "rz"), start=1):
            k_val = _safe_float(r, f"K{i}", _safe_float(r, f"Stiff{i}", 0.0))
            c_val = _safe_float(r, f"C{i}", _safe_float(r, f"Damp{i}", 0.0))
            if hasattr(prop, f"stiff_{dof}"):
                setattr(prop, f"stiff_{dof}", k_val)
            if hasattr(prop, f"damp_{dof}"):
                setattr(prop, f"damp_{dof}", c_val)


def handle_link_conn(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_link_conn = df


def handle_link_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_link_assign = df