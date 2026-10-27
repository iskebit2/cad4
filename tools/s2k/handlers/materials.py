# tools/s2k/handlers/materials.py
"""MATERIAL PROPERTIES 01/02 — tüm birim dönüşümü UnitConverter üzerinden."""
import logging

import pandas as pd

from tools.s2k.context import LoadContext
from data.enums import MatType
from domain.definition import Material

logger = logging.getLogger(__name__)


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _color_from_string(s: str) -> tuple:
    color_map = {
        "Red": (1, 0, 0), "Green": (0, 1, 0), "Blue": (0, 0, 1),
        "Yellow": (1, 1, 0), "Cyan": (0, 1, 1), "Magenta": (1, 0, 1),
        "White": (1, 1, 1), "Black": (0, 0, 0),
        "Gray8Dark": (0.3, 0.3, 0.3), "Gray8Light": (0.7, 0.7, 0.7),
    }
    return color_map.get(s, (0.8, 0.8, 0.8))


def _parse_mat_type(row) -> MatType:
    raw_type = str(row.get("Type", "")).upper().strip()
    return {
        "STEEL": MatType.STEEL, "CONCRETE": MatType.CONCRETE,
        "REBAR": MatType.REBAR, "TENDON": MatType.TENDON,
        "ALUMINUM": MatType.ALUMINUM, "COLDFORMED": MatType.COLDFORMED,
    }.get(raw_type, MatType.NODESIGN)


def handle_material_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        ctx.materials[name] = Material(
            name=name,
            mat_type=_parse_mat_type(row),
            color=_color_from_string(str(row.get("Color", "Gray8Dark"))),
        )


def handle_material_mech(ctx: LoadContext, df: pd.DataFrame) -> None:
    
    for _, row in df.iterrows():
        name = str(row.get("Material", "")).strip()
        if not name:
            continue
        mat = ctx.materials.setdefault(name, Material(name=name))

        E = _safe_float(row, "E1", 2.0e5)
        G = _safe_float(row, "G12", 8.1e4)
        mat.E1 = mat.E2 = mat.E3 = E
        mat.G12 = mat.G13 = mat.G23 = G
        mat.nu12 = mat.nu13 = mat.nu23 = _safe_float(row, "U12", 0.3)
        mat.density = _safe_float(row, "UnitMass", 0.0)

        