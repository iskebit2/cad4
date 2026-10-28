# tools/s2k/handlers/section_cuts.py
"""SECTION CUTS 1/3."""
import logging

import pandas as pd

from data.enums import SectionCutDefinedBy, SectionCutResultType
from domain.definition import QuadDefinition, SectionCut
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


def handle_section_cuts_gen(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("CutName", "")).strip()
        if not name:
            continue
        try:
            defined_by = SectionCutDefinedBy(str(row.get("DefinedBy", "Quad")).strip())
        except ValueError:
            defined_by = SectionCutDefinedBy.QUAD
        try:
            result_type = SectionCutResultType(str(row.get("ResultType", "Analysis")).strip())
        except ValueError:
            result_type = SectionCutResultType.ANALYSIS

        ctx.section_cuts[name] = SectionCut(
            name=name,
            defined_by=defined_by,
            group=str(row.get("Group", "All")).strip(),
            result_type=result_type,
            default_loc=str(row.get("DefaultLoc", "Yes")).strip().upper() == "YES",
            global_x=_safe_float(row, "GlobalX"),
            global_y=_safe_float(row, "GlobalY"),
            global_z=_safe_float(row, "GlobalZ"),
            angle_a=_safe_float(row, "AngleA"),
            angle_b=_safe_float(row, "AngleB"),
            angle_c=_safe_float(row, "AngleC"),
            elem_side=str(row.get("ElemSide", "Positive")).strip(),
            quad=QuadDefinition(points=[]),
        )


def handle_section_cuts_quad(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("SectionCut", "")).strip()
        if not name:
            continue
        sc = ctx.section_cuts.setdefault(name, SectionCut(name=name, quad=QuadDefinition(points=[])))
        if sc.quad is None:
            sc.quad = QuadDefinition(points=[])
        sc.quad.points.append((
            _safe_float(row, "X"),
            _safe_float(row, "Y"),
            _safe_float(row, "Z"),
        ))