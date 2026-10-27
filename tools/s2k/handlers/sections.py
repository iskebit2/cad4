# tools/s2k/handlers/sections.py
"""
FRAME/AREA SECTION PROPERTIES, AUTO SELECT, SD geometry.

Birim sözleşmesi: S2K değerleri `float` (S2K CurrUnits).
`ProjectBuilder` S2K biriminde yaratır, `finalize_and_convert(N_MM)` dönüştürür.
Doğrulama `tools.section_checks.check_section` ile.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import pandas as pd

from tools.s2k.context import LoadContext
from data.enums import MatType, SectionType
from domain.definition import (
    Material, Section, SDShape, SDPolygonPoint, SDSection,
)
from tools.section_checks import check_section

logger = logging.getLogger(__name__)


# ============================================================================
# YARDIMCILAR
# ============================================================================
def _safe_float(row, key, default=0.0) -> float:
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _color_from_string(s: str) -> Tuple[float, float, float]:
    """S2K Color alanı → (R, G, B) 0-1 aralığında.

    Desteklenen formatlar:
        - İsimli: "Red", "Cyan", "Gray8Dark", ...
        - Windows BGR sayısal: 16711808, 4227200, ...
        - Hex: "#FF0080"
    """
    if not s:
        return (0.8, 0.8, 0.8)

    s_clean = str(s).strip()

    # 1. Sayısal (Windows BGR)
    try:
        value = int(s_clean)
        r = (value & 0xFF) / 255.0
        g = ((value >> 8) & 0xFF) / 255.0
        b = ((value >> 16) & 0xFF) / 255.0
        return (r, g, b)
    except (ValueError, TypeError):
        pass

    # 2. Hex "#FF0080"
    if s_clean.startswith("#") and len(s_clean) == 7:
        try:
            r = int(s_clean[1:3], 16) / 255.0
            g = int(s_clean[3:5], 16) / 255.0
            b = int(s_clean[5:7], 16) / 255.0
            return (r, g, b)
        except ValueError:
            pass

    # 3. İsimli renkler (case-insensitive)
    color_map = {
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
        "yellow": (1.0, 1.0, 0.0),
        "cyan": (0.0, 1.0, 1.0),
        "magenta": (1.0, 0.0, 1.0),
        "white": (1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0),
        "orange": (1.0, 0.5, 0.0),
        "pink": (1.0, 0.75, 0.8),
        "purple": (0.5, 0.0, 0.5),
        "brown": (0.6, 0.4, 0.2),
        "gray": (0.5, 0.5, 0.5),
        "grey": (0.5, 0.5, 0.5),
        "gray8dark": (0.3, 0.3, 0.3),
        "gray8light": (0.7, 0.7, 0.7),
    }
    c = color_map.get(s_clean.lower())
    if c is not None:
        return c

    logger.warning("[Color] Bilinmeyen format: %r → default", s_clean)
    return (0.8, 0.8, 0.8)


def _dim_modifier(row, key: str, default: float = 1.0) -> float:
    """Boyutsuz modifier — 0 ise default."""
    v = _safe_float(row, key, default)
    return v if v != 0 else default


# ============================================================================
# SAP Shape → SectionType + params (S2K birimi — float)
# ============================================================================
def _map_sap_to_local(row) -> Tuple[SectionType, Dict[str, float]]:
    """SAP satırını SectionType + params'a çevir. Değerler S2K biriminde (float)."""
    shape = str(row.get("Shape", "Rectangle")).strip()

    # Ortak analiz özellikleri — S2K birimi
    analysis = {
        "Area":    _safe_float(row, "Area"),
        "J":       _safe_float(row, "TorsConst"),
        "I33":     _safe_float(row, "I33"),
        "I22":     _safe_float(row, "I22"),
        "I23":     _safe_float(row, "I23"),
        "AS2":     _safe_float(row, "AS2"),
        "AS3":     _safe_float(row, "AS3"),
        "S33Top":  _safe_float(row, "S33Top"),
        "S33Bot":  _safe_float(row, "S33Bot"),
        "S22Left": _safe_float(row, "S22Left"),
        "S22Right": _safe_float(row, "S22Right"),
        "Z33":     _safe_float(row, "Z33"),
        "Z22":     _safe_float(row, "Z22"),
        "R33":     _safe_float(row, "R33"),
        "R22":     _safe_float(row, "R22"),
        "Cw":      _safe_float(row, "Cw"),
        "AMod":    _dim_modifier(row, "AMod", 1.0),
        "A2Mod":   _dim_modifier(row, "A2Mod", 1.0),
        "A3Mod":   _dim_modifier(row, "A3Mod", 1.0),
        "JMod":    _dim_modifier(row, "JMod", 1.0),
        "I2Mod":   _dim_modifier(row, "I2Mod", 1.0),
        "I3Mod":   _dim_modifier(row, "I3Mod", 1.0),
        "MMod":    _dim_modifier(row, "MMod", 1.0),
        "WMod":    _dim_modifier(row, "WMod", 1.0),
    }

    if shape in ("I/Wide Flange", "I"):
        return SectionType.I, {
            "h": _safe_float(row, "t3", 200),
            "b": _safe_float(row, "t2", 100),
            "tw": _safe_float(row, "tw", 10),
            "tf": _safe_float(row, "tf", 14),
            **analysis,
        }
    if shape in ("Tee", "T"):
        return SectionType.T, {
            "h": _safe_float(row, "t3", 200),
            "b": _safe_float(row, "t2", 100),
            "tw": _safe_float(row, "tw", 10),
            "tf": _safe_float(row, "tf", 14),
            **analysis,
        }
    if shape in ("Rectangle", "Rectangular"):
        return SectionType.RECT, {
            "h": _safe_float(row, "t3", 200),
            "b": _safe_float(row, "t2", 100),
            **analysis,
        }
    if shape in ("Pipe", "Circular", "Circle"):
        d = _safe_float(row, "t3", 120)
        tw = _safe_float(row, "tw", 10)
        return SectionType.PIPE, {
            "ro": d / 2.0,
            "ri": max(0.1, (d - 2.0 * tw) / 2.0),
            "n": 24,
            **analysis,
        }
    if shape in ("Channel", "C"):
        return SectionType.C, {
            "h": _safe_float(row, "t3", 100),
            "b": _safe_float(row, "t2", 80),
            "t": _safe_float(row, "tw", 6),
            "tf": _safe_float(row, "tf", 6),
            **analysis,
        }
    if shape in ("Angle", "L"):
        return SectionType.L, {
            "h": _safe_float(row, "t3", 100),
            "b": _safe_float(row, "t2", 80),
            "t": _safe_float(row, "tw", 8),
            **analysis,
        }
    if shape in ("Tube", "Box", "Box/Tube"):
        return SectionType.TUBE, {
            "h": _safe_float(row, "t3", 200),
            "b": _safe_float(row, "t2", 100),
            "t": _safe_float(row, "tw", 10),
            **analysis,
        }
    if shape in ("SD Section", "General"):
        return SectionType.CUSTOM, {**analysis}

    logger.info("[SectionMap] Bilinmeyen Shape=%r, RECT fallback", shape)
    return SectionType.RECT, {
        "h": _safe_float(row, "t3", 200),
        "b": _safe_float(row, "t2", 100),
        **analysis,
    }


def _resolve_material(ctx: LoadContext, mat_name: str) -> Optional[Material]:
    """S2K biriminde material — handler'lar `float` doldurur."""
    mat_name = str(mat_name or "").strip()
    if not mat_name or mat_name.lower() == "nan":
        return None
    mat = ctx.materials.get(mat_name)
    if mat is None:
        mat = Material(name=mat_name, mat_type=MatType.STEEL)
        ctx.materials[mat_name] = mat
    return mat


# ============================================================================
# FRAME SECTION
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
            s_type, s_params = _map_sap_to_local(row)
        except Exception as e:
            logger.error("[FrameProps] '%s' dönüşüm HATASI: %s", sect_name, e, exc_info=True)
            continue

        mat = _resolve_material(ctx, row.get("Material", ""))
        raw_color = str(row.get("Color", ""))
        parsed = _color_from_string(raw_color)
        logger.info("[ColorImport] sec=%s raw=%r parsed=%s", sect_name, raw_color, parsed)

        section = Section(
            name=sect_name,
            profile_type=s_type,
            profile_params=s_params,
            material=mat,
            color=_color_from_string(str(row.get("Color", "Gray8Dark"))),
        )
        ctx.sections[sect_name] = section

        # Doğrulama — analitik + katalog + değişmezler
        try:
            for msg in check_section(section, strict=False):
                logger.info("[SectionCheck] %s", msg)
                ctx.warnings.append(msg)
        except Exception as e:
            logger.error("[SectionCheck] atlandı: %s", e)


# ============================================================================
# AUTO SELECT
# ============================================================================
def handle_auto_select_lists(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        list_name = str(row.get("ListName", "")).strip()
        member = str(row.get("SectionName", "")).strip()
        if list_name and member:
            ctx.auto_select_lists.setdefault(list_name, []).append(member)


# ============================================================================
# AREA SECTION
# ============================================================================
def handle_area_props(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        name = str(row.get("Section", "")).strip()
        if not name:
            continue
        thickness = _safe_float(row, "Thickness", 0.1)   # S2K birimi
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
                x=_safe_float(r, "X"),
                y=_safe_float(r, "Y"),
                radius=_safe_float(r, "Radius"),
            )
            for r in rows
        ]
        shape = SDShape(
            name=shp, shape_kind="Polygon", material=mat,
            z_order=z_order, fill_color=color, points=pts,
        )
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
            "x_center": _safe_float(r, "XCenter"),
            "y_center": _safe_float(r, "YCenter"),
            "height": _safe_float(r, "Height"),
            "width": _safe_float(r, "Width"),
            "rotation": _safe_float(r, "Rotation"),
        })