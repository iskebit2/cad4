# tools/s2k/utils.py
"""Ortak yardımcı fonksiyonlar."""
from typing import Dict, Tuple

import pandas as pd

from domain.definition import SectionType


def get_color_from_string(color_str: str) -> Tuple[float, float, float]:
    """SAP2000 renk adı → RGB."""
    color_map = {
        'Red': (1.0, 0.0, 0.0), 'Green': (0.0, 1.0, 0.0), 'Blue': (0.0, 0.0, 1.0),
        'Yellow': (1.0, 1.0, 0.0), 'Cyan': (0.0, 1.0, 1.0), 'Magenta': (1.0, 0.0, 1.0),
        'White': (1.0, 1.0, 1.0), 'Black': (0.0, 0.0, 0.0),
        'Gray8Dark': (0.3, 0.3, 0.3), 'Gray8Light': (0.7, 0.7, 0.7),
    }
    return color_map.get(color_str, (0.8, 0.8, 0.8))


def parse_sap_mat_type(row) -> 'MatType':
    """SAP2000 material tipini tespit et."""
    from domain.definition import MatType
    
    raw_type = str(row.get('Type', '')).upper().strip()
    raw_grade = str(row.get('Grade', '')).upper().strip()
    raw_name = str(row.get('Material', '')).upper().strip()
    
    mapping = {
        "STEEL": MatType.STEEL, "CONCRETE": MatType.CONCRETE,
        "REBAR": MatType.REBAR, "TENDON": MatType.TENDON,
        "ALUMINUM": MatType.ALUMINUM, "COLDFORMED": MatType.COLDFORMED,
    }
    if raw_type in mapping:
        return mapping[raw_type]
    
    if raw_type == "OTHER":
        if any(k in raw_grade for k in ("WOOD", "TIMBER", "OSB")):
            return getattr(MatType, 'TIMBER', MatType.NODESIGN)
        if any(k in raw_name for k in ("TAS", "DUVAR", "MASONRY", "BRICK")):
            return getattr(MatType, 'MASONRY', MatType.NODESIGN)
    
    return MatType.NODESIGN


def map_sap_to_local_params(row) -> Tuple[SectionType, Dict[str, float]]:
    """SAP2000 kesit → yerel parametreler."""
    s_type = str(row.get('Shape', 'Rectangle')).strip()
    
    def sf(key, default=0.0, allow_zero=True):
        val = row.get(key)
        if val is None or str(val).strip() in ("", "None", "nan"):
            return default
        try:
            f = float(val)
            return f if (allow_zero or abs(f) > 1e-12) else default
        except (ValueError, TypeError):
            return default
    
    # Analiz parametreleri (her kesitte ortak)
    analysis = {
        'Area': sf('Area'), 'J': sf('TorsConst'),
        'I33': sf('I33'), 'I22': sf('I22'), 'I23': sf('I23'),
        'AS2': sf('AS2'), 'AS3': sf('AS3'),
        'S33Top': sf('S33Top'), 'S33Bot': sf('S33Bot'),
        'S22Left': sf('S22Left'), 'S22Right': sf('S22Right'),
        'Z33': sf('Z33'), 'Z22': sf('Z22'),
        'R33': sf('R33'), 'R22': sf('R22'),
        'Cw': sf('Cw'),
        'AMod': sf('AMod', 1.0), 'A2Mod': sf('A2Mod', 1.0), 'A3Mod': sf('A3Mod', 1.0),
        'JMod': sf('JMod', 1.0), 'I2Mod': sf('I2Mod', 1.0), 'I3Mod': sf('I3Mod', 1.0),
        'MMod': sf('MMod', 1.0), 'WMod': sf('WMod', 1.0),
    }
    
    if s_type in ("I/Wide Flange", "I"):
        geom = {"h": sf('t3', 200), "b": sf('t2', 100),
                "tw": sf('tw', 10), "tf": sf('tf', 14)}
        return SectionType.I, {**geom, **analysis}
    
    if s_type in ("Rectangle", "Rectangular"):
        return SectionType.RECT, {"h": sf('t3', 200), "b": sf('t2', 100), **analysis}
    
    if s_type in ("Pipe", "Circular", "Circle"):
        t3, tw = sf('t3', 120), sf('tw', 10)
        return SectionType.PIPE, {
            "ro": t3 / 2, "ri": max(0.1, (t3 - 2 * tw) / 2), "n": 24, **analysis,
        }
    
    if s_type in ("Channel", "C"):
        return SectionType.C, {
            "h": sf('t3', 100), "b": sf('t2', 80), "t": sf('tw', 6), **analysis,
        }
    
    if s_type in ("Angle", "L"):
        return SectionType.L, {
            "h": sf('t3', 100), "b": sf('t2', 80), "t": sf('tw', 8), **analysis,
        }
    
    if s_type in ("Tube", "Box"):
        return SectionType.TUBE, {
            "h": sf('t3', 200), "b": sf('t2', 100), "t": sf('tw', 10), **analysis,
        }
    
    return SectionType.RECT, {"h": 200.0, "b": 100.0, **analysis}


def safe_float(row, key, default=0.0, allow_zero=True):
    """Güvenli float dönüşümü."""
    val = row.get(key)
    if val is None or str(val).strip() in ("", "None", "nan"):
        return default
    try:
        f = float(val)
        return f if (allow_zero or abs(f) > 1e-12) else default
    except (ValueError, TypeError):
        return default