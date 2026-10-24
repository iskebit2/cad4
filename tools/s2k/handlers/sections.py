# tools/s2k/handlers/sections.py
"""
FRAME/AREA SECTION PROPERTIES, AUTO SELECT, SD geometry.
Birim dönüşümü UnitConverter üzerinden; doğrulama section_checks ile.
"""
import logging
from typing import Dict, Tuple

import pandas as pd

from tools.s2k.context import LoadContext
from tools.s2k.units_adapter import validate_section_properties
from data.enums import SectionType, MatType
from domain.definition import Section, Material, SDShape, SDPolygonPoint, SDSection
from tools.section_checks import check_section

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


# ============================================================================
# SAP Shape → SectionType + params
# ============================================================================
def _map_sap_to_local(row, uc) -> Tuple[SectionType, Dict[str, float]]:
    s_type = str(row.get("Shape", "Rectangle")).strip()

    def L(k, d=0.0):  return uc.L(_safe_float(row, k, d))
    def L2(k, d=0.0): return uc.L2(_safe_float(row, k, d))
    def L3(k, d=0.0): return uc.L3(_safe_float(row, k, d))
    def L4(k, d=0.0): return uc.L4(_safe_float(row, k, d))
    def dim(k, d=1.0):
        v = _safe_float(row, k, d)
        return v if v != 0 else d

    # Ortak analiz özellikleri
    analysis = {
        "Area": L2("Area"),
        "J":    L4("TorsConst"),
        "I33":  L4("I33"),
        "I22":  L4("I22"),
        "I23":  L4("I23"),
        "AS2":  L2("AS2"),
        "AS3":  L2("AS3"),
        "S33Top": L3("S33Top"), "S33Bot": L3("S33Bot"),
        "S22Left": L3("S22Left"), "S22Right": L3("S22Right"),
        "Z33": L3("Z33"), "Z22": L3("Z22"),
        "R33": L3("R33"), "R22": L3("R22"),
        "Cw":  L4("Cw"),
        "AMod": dim("AMod"), "A2Mod": dim("A2Mod"), "A3Mod": dim("A3Mod"),
        "JMod": dim("JMod"), "I2Mod": dim("I2Mod"), "I3Mod": dim("I3Mod"),
        "MMod": dim("MMod"), "WMod": dim("WMod"),
    }

    if s_type in ("I/Wide Flange", "I"):
        return SectionType.I, {
            "h": L("t3", 200), "b": L("t2", 100),
            "tw": L("tw", 10), "tf": L("tf", 14),
            **analysis,
        }
    if s_type in ("Tee", "T"):
        return SectionType.T, {
            "h": L("t3", 200), "b": L("t2", 100),
            "tw": L("tw", 10), "tf": L("tf", 14),
            **analysis,
        }
    if s_type in ("Rectangle", "Rectangular"):
        return SectionType.RECT, {"h": L("t3", 200), "b": L("t2", 100), **analysis}
    if s_type in ("Pipe", "Circular", "Circle"):
        d = L("t3", 120); tw = L("tw", 10)
        return SectionType.PIPE, {"ro": d/2, "ri": max(0.1, (d - 2*tw)/2), "n": 24, **analysis}
    if s_type in ("Channel", "C"):
        return SectionType.C, {
            "h": L("t3", 100), "b": L("t2", 80),
            "t": L("tw", 6), "tf": L("tf", 6),
            **analysis,
        }
    if s_type in ("Angle", "L"):
        return SectionType.L, {
            "h": L("t3", 100), "b": L("t2", 80), "t": L("tw", 8),
            **analysis,
        }
    if s_type in ("Tube", "Box", "Box/Tube"):
        return SectionType.TUBE, {
            "h": L("t3", 200), "b": L("t2", 100), "t": L("tw", 10),
            **analysis,
        }
    if s_type in ("SD Section", "General"):
        return SectionType.CUSTOM, {**analysis}

    logger.warning("[SectionMap] Bilinmeyen Shape=%r, RECT fallback", s_type)
    return SectionType.RECT, {"h": L("t3", 200), "b": L("t2", 100), **analysis}


# ============================================================================
# HANDLERS
# ============================================================================
def handle_frame_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    name_col = next((c for c in ("SectionName", "Section", "Name") if c in df.columns), None)
    if name_col is None:
        logger.error("[FrameProps] İsim kolonu yok: %s", list(df.columns))
        return

    for _, row in df.iterrows():
        sect_name = str(row.get(name_col, "")).strip()
        if not sect_name:
            continue
        shape = str(row.get("Shape", "")).strip()
        if "auto select" in shape.lower() or str(row.get("AutoType", "")).upper() in ("YES", "AUTOSELECT"):
            continue

        try:
            s_type, s_params = _map_sap_to_local(row, ctx.units)
        except Exception as e:
            logger.error("[FrameProps] '%s' dönüşüm HATASI: %s", sect_name, e, exc_info=True)
            continue

        mat_name = str(row.get("Material", "")).strip()
        mat = ctx.materials.get(mat_name) if mat_name else None
        if mat is None and mat_name:
            mat = Material(name=mat_name, mat_type=MatType.STEEL)
            ctx.materials[mat_name] = mat

        section = Section(
            name=sect_name,
            profile_type=s_type,
            profile_params=s_params,
            material=mat,
            color=_color_from_string(str(row.get("Color", "Gray8Dark"))),
        )
        ctx.sections[sect_name] = section

        # --- DOĞRULAMA: analitik + birim kontrolü ---
        for msg in validate_section_properties(section):
            logger.warning("[SectionCheck] %s", msg)
            ctx.warnings.append(msg)
        try:
            # Tek doğrulama — analitik + katalog + değişmezler + birim şüphesi
            for msg in check_section(section, strict=False):
                logger.warning("[SectionCheck] %s", msg)
                ctx.warnings.append(msg)
        except Exception as e:
            logger.debug("[SectionCheck-Deep] atlandı: %s", e)


def handle_auto_select_lists(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        list_name = str(row.get("ListName", "")).strip()
        member = str(row.get("SectionName", "")).strip()
        if list_name and member:
            ctx.auto_select_lists.setdefault(list_name, []).append(member)


def handle_area_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    uc = ctx.units
    for _, row in df.iterrows():
        name = str(row.get("Section", "")).strip()
        if not name:
            continue
        thickness = uc.L(_safe_float(row, "Thickness", 0.1))
        mat_name = str(row.get("Material", "")).strip()
        mat = ctx.materials.get(mat_name) if mat_name else None
        if mat is None and mat_name:
            mat = Material(name=mat_name)
            ctx.materials[mat_name] = mat
        ctx.area_sections[name] = {
            "material": mat,
            "thickness": thickness,
            "area_type": str(row.get("AreaType", "Shell")).strip(),
            "type": str(row.get("Type", "Shell-Thin")).strip(),
            "color": _color_from_string(str(row.get("Color", "Gray8Dark"))),
        }
        ctx.area_thicknesses[name] = thickness


# ============================================================================
# SD SECTION
# ============================================================================
def handle_sd_general(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        name = str(r.get("SectionName", "")).strip()
        if not name:
            continue
        sd = ctx.sd_sections.setdefault(name, SDSection(name=name))
        sd.design_type = str(r.get("DesignType", "No Check/Design")).strip()
        sd.axis_angle = _safe_float(r, "AxisAngle", 90.0)


def handle_sd_polygon(ctx: LoadContext, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    grouped: Dict[Tuple[str, str], list] = {}
    for _, row in df.iterrows():
        sec = str(row.get("SectionName", "")).strip()
        shp = str(row.get("ShapeName", "")).strip()
        if sec and shp:
            grouped.setdefault((sec, shp), []).append(row)

    for (sec, shp), rows in grouped.items():
        first = rows[0]
        mat = str(first.get("ShapeMat", "")).strip()
        z_order = int(_safe_float(first, "ZOrder", 1))
        color = _color_from_string(str(first.get("FillColor", "Gray8Dark")))

        pts = [
            SDPolygonPoint(
                x=ctx.units.L(_safe_float(r, "X")),
                y=ctx.units.L(_safe_float(r, "Y")),
                radius=ctx.units.L(_safe_float(r, "Radius")),
            )
            for r in rows
        ]
        shape = SDShape(name=shp, shape_kind="Polygon", material=mat,
                        z_order=z_order, fill_color=color, points=pts)
        sd = ctx.sd_sections.setdefault(sec, SDSection(name=sec))
        sd.shapes.append(shape)


def handle_sd_rebar_rect(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        sd = ctx.sd_sections.setdefault(sec, SDSection(name=sec))
        sd.rect_rebars.append({
            "shape": str(r.get("ShapeName", "")).strip(),
            "material": str(r.get("ShapeMat", "")).strip(),
            "x_center": ctx.units.L(_safe_float(r, "XCenter")),
            "y_center": ctx.units.L(_safe_float(r, "YCenter")),
            "height": ctx.units.L(_safe_float(r, "Height")),
            "width": ctx.units.L(_safe_float(r, "Width")),
            "rotation": _safe_float(r, "Rotation"),
        })