# tools/s2k/handlers/sections.py
"""
FRAME/AREA SECTION PROPERTIES, AUTO SELECT, SD geometry.

Birim sözleşmesi: S2K değerleri `float` (S2K CurrUnits).
`ProjectBuilder` S2K biriminde yaratır, `finalize_and_convert(N_MM)` dönüştürür.
Doğrulama `tools.section_checks.check_section` ile.
"""
from __future__ import annotations

import logging

import pandas as pd

from data.enums import MatType, SectionType
from domain.definition import (
    Material,
    SDPolygonPoint,
    SDSection,
    SDShape,
    Section,
)
from tools.s2k.context import LoadContext
from tools.section_checks import check_section
from tools.s2k.handlers._colors import color_from_string, DEFAULT_COLOR

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





def _dim_modifier(row, key: str, default: float = 1.0) -> float:
    """Boyutsuz modifier — 0 ise default."""
    v = _safe_float(row, key, default)
    return v if v != 0 else default


# ============================================================================
# SAP Shape → SectionType + params (S2K birimi — float)
# ============================================================================
def _map_sap_to_local(row) -> tuple[SectionType, dict[str, float]]:
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
        return SectionType.CUSTOM, {
            "h": _safe_float(row, "t3", 0.2),
            "b": _safe_float(row, "t2", 0.1),
            **analysis,
        }

    logger.info("[SectionMap] Bilinmeyen Shape=%r, RECT fallback", shape)
    return SectionType.RECT, {
        "h": _safe_float(row, "t3", 200),
        "b": _safe_float(row, "t2", 100),
        **analysis,
    }


def _resolve_material(ctx: LoadContext, mat_name: str) -> Material | None:
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
        parsed = color_from_string(raw_color)
        logger.info("[ColorImport] sec=%s raw=%r parsed=%s", sect_name, raw_color, parsed)

        section = Section(
            name=sect_name,
            profile_type=s_type,
            profile_params=s_params,
            material=mat,
            color=parsed,
            cg_offset3=_safe_float(row, "CGOffset3", 0.0),
            cg_offset2=_safe_float(row, "CGOffset2", 0.0),
            ecc_v2=_safe_float(row, "EccV2", 0.0),
            ecc_v3=_safe_float(row, "EccV3", 0.0),
            from_file=str(row.get("FromFile", "No")).strip().upper() == "YES",
            notes=str(row.get("Notes", "")).strip(),
        )
        ctx.sections[sect_name] = section

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
    """AREA SECTION PROPERTIES — AreaSection nesnesi üret."""
    from data.enums import PropAreaType
    from domain.definition import AreaSection

    for _, row in df.iterrows():
        name = str(row.get("Section", "")).strip()
        if not name:
            continue

        # material
        mat_name = str(row.get("Material", "")).strip()
        mat = ctx.materials.get(mat_name) if mat_name else None
        if mat is None and mat_name:
            mat = Material(name=mat_name)
            ctx.materials[mat_name] = mat

        # area_type / type
        area_type_raw = str(row.get("AreaType", "Shell")).strip()
        try:
            prop_type = PropAreaType(area_type_raw)
        except ValueError:
            prop_type = PropAreaType.Shell

        thickness = _safe_float(row, "Thickness", 0.1)   # S2K birimi
        bend_thick_raw = row.get("BendThick")
        bend_thick = None
        if bend_thick_raw not in (None, "", "nan", "NaN"):
            try:
                bend_thick = float(bend_thick_raw)
            except (TypeError, ValueError):
                bend_thick = None

        sec = AreaSection(
            name=name,
            prop_type=prop_type,
            area_type=str(row.get("Type", "Shell-Thin")).strip(),
            material=mat,
            mat_angle=_safe_float(row, "MatAngle", 0.0),
            thickness=thickness,
            bend_thick=bend_thick,
            drill_dof=str(row.get("DrillDOF", "No")).strip().upper() == "YES",
            color= color_from_string(str(row.get("Color", "Gray8Dark"))),
            membrane_f11=_safe_float(row, "F11Mod", 1.0),
            membrane_f22=_safe_float(row, "F22Mod", 1.0),
            membrane_f12=_safe_float(row, "F12Mod", 1.0),
            bending_m11=_safe_float(row, "M11Mod", 1.0),
            bending_m22=_safe_float(row, "M22Mod", 1.0),
            bending_m12=_safe_float(row, "M12Mod", 1.0),
            shear_v13=_safe_float(row, "V13Mod", 1.0),
            shear_v23=_safe_float(row, "V23Mod", 1.0),
            mass=_safe_float(row, "MMod", 1.0),
            weight=_safe_float(row, "WMod", 1.0),
        )

        # geri uyum için ham dict de doldur
        ctx.area_sections[name] = {
            "material": mat,
            "thickness": thickness,
            "area_type": area_type_raw,
            "type": sec.area_type,
            "color": sec.color,
        }
        ctx.area_section_objects[name] = sec
        ctx.area_thicknesses[name] = thickness


# ============================================================================
# SD SECTION
# ============================================================================
def handle_sd_general(ctx: LoadContext, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get("SectionName", "")).strip()
        if not name:
            continue
        sd = ctx.sd_sections.setdefault(name, SDSection(name=name))

        # NaN-safe alan okuma
        def _str(key, default=""):
            v = r.get(key)
            if v is None or (isinstance(v, float) and v != v):
                return default
            s = str(v).strip()
            return s if s and s.lower() != "nan" else default

        def _int(key, default=0):
            v = _safe_float(r, key, float(default))
            return int(v) if v == v else default

        design = _str("DesignType", "")
        if design:
            sd.design_type = design

        dsgn = _str("DsgnOrChck", "")
        if dsgn:
            sd.dsgn_or_chck = dsgn

        base = _str("BaseMat", "")
        if base:
            sd.base_material = base

        if "nPolygon" in r:
            sd.n_polygon = _int("nPolygon", sd.n_polygon)

        if "AxisAngle" in r:
            sd.axis_angle = _safe_float(r, "AxisAngle", sd.axis_angle)
        if "MeshSzAbs" in r:
            sd.mesh_sz_abs = _safe_float(r, "MeshSzAbs", sd.mesh_sz_abs)
        if "MeshSzRel" in r:
            sd.mesh_sz_rel = _safe_float(r, "MeshSzRel", sd.mesh_sz_rel)
        if "IncludeVStr" in r:
            sd.include_v_str = _str("IncludeVStr", "No").upper() == "YES"


def handle_sd_polygon(ctx: LoadContext, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return

    grouped: dict[tuple[str, str], list] = {}
    for _, row in df.iterrows():
        sec = str(row.get("SectionName", "")).strip()
        shp = str(row.get("ShapeName", row.get("ShapeNum", ""))).strip()
        if sec and shp:
            grouped.setdefault((sec, shp), []).append(row)

    for (sec, shp), rows in grouped.items():
        first = rows[0]
        mat = str(first.get("ShapeMat", "")).strip()
        z_order = int(_safe_float(first, "ZOrder", 1))
        color = color_from_string(str(first.get("FillColor", "Gray8Dark")))

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
                        reinforcing=str(first.get("Reinforcing", "No")).strip().upper() == "YES",
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

def handle_frame_section_rebar_col(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        section = ctx.sections.get(sec)
        if section is None:
            section = Section(name=sec)
            ctx.sections[sec] = section
        section.rebar_column.update({
            "rebar_mat_l": str(r.get("RebarMatL", "")).strip(),
            "rebar_mat_c": str(r.get("RebarMatC", "")).strip(),
            "reinf_config": str(r.get("ReinfConfig", "")).strip(),
            "lat_reinf": str(r.get("LatReinf", "")).strip(),
            "cover": _safe_float(r, "Cover"),
            "num_bars3_dir": int(_safe_float(r, "NumBars3Dir", 0)),
            "num_bars2_dir": int(_safe_float(r, "NumBars2Dir", 0)),
            "bar_size_l": str(r.get("BarSizeL", "")).strip(),
            "bar_size_c": str(r.get("BarSizeC", "")).strip(),
            "spacing_c": _safe_float(r, "SpacingC"),
            "num_cbars2": int(_safe_float(r, "NumCBars2", 0)),
            "num_cbars3": int(_safe_float(r, "NumCBars3", 0)),
            "reinf_type": str(r.get("ReinfType", "")).strip(),
        })

def handle_frame_section_rebar_beam(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 03 - CONCRETE BEAM."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        section = ctx.sections.get(sec)
        if section is None:
            section = Section(name=sec)
            ctx.sections[sec] = section
        section.rebar_beam.update({
            "rebar_mat_l": str(r.get("RebarMatL", "")).strip(),
            "rebar_mat_c": str(r.get("RebarMatC", "")).strip(),
            "top_cover": _safe_float(r, "TopCover"),
            "bot_cover": _safe_float(r, "BotCover"),
            "top_left_area": _safe_float(r, "TopLeftArea"),
            "top_rght_area": _safe_float(r, "TopRghtArea"),
            "bot_left_area": _safe_float(r, "BotLeftArea"),
            "bot_rght_area": _safe_float(r, "BotRghtArea"),
        })


def handle_frame_section_time_dependent(ctx: LoadContext, df: pd.DataFrame) -> None:
    """FRAME SECTION PROPERTIES 13 - TIME DEPENDENT."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sec = str(r.get("SectionName", "")).strip()
        if not sec:
            continue
        section = ctx.sections.get(sec)
        if section is None:
            section = Section(name=sec)
            ctx.sections[sec] = section
        section.time_dependent = {
            "type_size": str(r.get("TypeSize", "Auto")).strip(),
            "auto_sf_size": _safe_float(r, "AutoSFSize", 1.0),
        }

def handle_sd_fiber_general(ctx: LoadContext, df: pd.DataFrame) -> None:
    """SECTION DESIGNER PROPERTIES 30 - FIBER GENERAL."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        name = str(r.get("SectionName", "")).strip()
        if not name:
            continue
        sd = ctx.sd_sections.setdefault(name, SDSection(name=name))
        sd.fiber = {
            "num_fibers_d2": int(_safe_float(r, "NumFibersD2", 3)),
            "num_fibers_d3": int(_safe_float(r, "NumFibersD3", 3)),
            "coord_sys": str(r.get("CoordSys", "Cartesian")).strip(),
            "grid_angle": _safe_float(r, "GridAngle", 0.0),
            "lump_rebar": str(r.get("LumpRebar", "No")).strip().upper() == "YES",
            "fiber_pmm": str(r.get("FiberPMM", "No")).strip().upper() == "YES",
            "fiber_mc": str(r.get("FiberMC", "No")).strip().upper() == "YES",
        }