# data/section_catalog.py
"""
data/*.json dosyalarındaki kesit kataloglarını yükler.
- steel_sections_W.json  → I/Wide Flange
- steel_sections_C.json  → Channel
- steel_sections_L.json  → Angle
- steel_sections_P.json  → Pipe
"""
import json
from pathlib import Path

from data.enums import SectionType
from domain.definition import Section
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# Dosya adı → (SectionType, aile etiketi)
CATALOG_FILES = {
    "steel_sections_W.json": (SectionType.I,       "W"),
    "steel_sections_C.json": (SectionType.CHANNEL, "C"),
    "steel_sections_L.json": (SectionType.L,       "L"),
    "steel_sections_P.json": (SectionType.PIPE,    "P"),
}


def _f(val, default=0.0) -> float:
    """JSON'dan gelen değeri güvenli float yap. None → default."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _make_section(entry: dict, section_type: SectionType, family: str) -> Section | None:
    """JSON entry'sini Section'a çevir."""
    name = entry.get("EDI_STD") or entry.get("DESIGNATION") or ""
    if not name:
        return None

    params: dict[str, float] = {}
    catalog: dict[str, float] = {}

    if section_type == SectionType.PIPE:
        # Pipe: OD, TDES
        od = _f(entry.get("OD"))
        t  = _f(entry.get("TDES"))
        if od > 0:
            params["d"] = od
        if t > 0:
            params["t"] = t
    else:
        # I / Channel / L: D, BF, TF, TW
        h  = _f(entry.get("D"))    # yükseklik (D)
        b  = _f(entry.get("BF"))   # başlık genişliği
        tf = _f(entry.get("TF"))
        tw = _f(entry.get("TW"))
        if h > 0:  params["h"]  = h
        if b > 0:  params["b"]  = b
        if tf > 0: params["tf"] = tf
        if tw > 0: params["tw"] = tw

    # Hesaplanmış özellikler (JSON'dan)
    for key in ("A", "I33", "I22", "J", "Z33", "Z22",
                "S33POS", "S33NEG", "S22POS", "S22NEG",
                "R33", "R22", "AS2", "AS3"):
        val = entry.get(key)
        if val is not None:
            try:
                catalog[key] = float(val)
            except (ValueError, TypeError):
                pass

    # Pipe için eksikleri tamamla
    if section_type == SectionType.PIPE:
        I33 = catalog.get("I33", 0.0)
        if "I22" not in catalog:
            catalog["I22"] = I33   # simetrik
        if "J" not in catalog and I33 > 0:
            catalog["J"] = 2 * I33
        if "Z22" not in catalog and "Z33" in catalog:
            catalog["Z22"] = catalog["Z33"]

    return Section(
        name=name,
        profile_type=section_type,
        profile_params=params,
        material=None,
        catalog_props=catalog,
        catalog_source=f"CSI Euro - {family}",
    )


def load_catalog_from_dir(data_dir: Path) -> dict[str, Section]:
    """
    Verilen klasördeki tüm steel_sections_*.json dosyalarını yükler.
    Döndürür: {name: Section} sözlüğü.
    """
    result: dict[str, Section] = {}
    for fname, (stype, family) in CATALOG_FILES.items():
        path = data_dir / fname
        if not path.exists():
            logger.debug(f"[Catalog] Dosya yok: {path}")
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception(f"[Catalog] JSON parse hatası: {path}")
            continue

        count = 0
        for entry in raw:
            sec = _make_section(entry, stype, family)
            if sec is None:
                continue
            result[sec.name] = sec
            count += 1

    return result