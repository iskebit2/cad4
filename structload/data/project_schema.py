# data/project_schema.py
"""
Proje JSON Şeması

Tüm config tek bir sözlükte toplanır:

{
  "project":            { name, type, address, coordinates, altitude,
                          structure_type, wood_material, building_height },
  "points":             { "P1": [x,y,z], "P2": [...], ... },
  "polygons":           { "D1": ["P1","P2",...], ... },
  "dead_config":        { ... G yükleri ... },
  "live_config":        { ... Q yükleri ... },
  "wind_config":        { v_b0, terrain, rho, ct, kI },
  "snow_config":        { slope, snow_region, altitude, Ce, Ct },
  "earthquake_config":  { R, D, I, kappa, Hn, gamma_E, n, e, ee,
                          zemin_sinifi, limit_raw, load_cases,
                          drift_combo_names, has_irregularity,
                          dd2, dd3 }
}
"""

import json
import os


# ======================================================================
# VARSAYILANLAR
# ======================================================================

DEFAULT_PROJECT = {
    "name": "Yeni Proje",
    "type": "Konut",
    "address": "",
    "coordinates": "36.0,42.0",
    "altitude": 0,
    "structure_type": "Betonarme",
    "wood_material": "",
    "building_height": 0,
}

DEFAULT_POINTS = {}
DEFAULT_POLYGONS = {}

DEFAULT_DEAD_CONFIG = {
    # GUI'deki manuel tanımlar + hazır yüklerin bir özeti
    "definitions": [],   # [{id, name, load_type, value, unit, source, description}]
    "assignments": {},   # {element_id: {"G": [...], "Q": [...]}}
}

DEFAULT_LIVE_CONFIG = {
    "definitions": [],
    "assignments": {},
}

DEFAULT_WIND_CONFIG = {
    "v_b0": 28.0,
    "terrain": "Kategori III",
    "rho": 1.25,
    "ct": 1.0,
    "kI": 1.0,
}

DEFAULT_SNOW_CONFIG = {
    "slope": 15.0,
    "snow_region": 2,
    "altitude": 50,
    "Ce": 1.0,
    "Ct": 1.0,
}

DEFAULT_EARTHQUAKE_CONFIG = {
    "R": 2.5,
    "D": 2.5,
    "I": 1.2,
    "kappa": 0.5,
    "Hn": 10.1,
    "gamma_E": 0.9,
    "n": 0.30,
    "e": "±0.05",
    "ee": "Dbi= (η_bi/1.2)², Ek dış merkezlik= %5 + Dbi",
    "zemin_sinifi": "ZC",
    "limit_raw": 0.008,
    "load_cases": ["EQX", "EQY", "QUAKEX", "QUAKEY"],
    "drift_combo_names": ["EXP", "EXM", "EYP", "EYM"],
    "has_irregularity": True,
    "dd2": {
        "Ss": 0.329, "S1": 0.128, "PGA": 0.143, "PGV": 10.653,
        "Fs": 1.300, "F1": 1.500, "Sds": 0.428, "Sd1": 0.192,
    },
    "dd3": {
        "Ss": 0.130, "S1": 0.054, "PGA": 0.058, "PGV": 4.540,
        "Fs": 1.300, "F1": 1.500, "Sds": 0.169, "Sd1": 0.081,
    },
}


# ======================================================================
# ŞEMA
# ======================================================================

SCHEMA_KEYS = (
    "project",
    "points",
    "polygons",
    "dead_config",
    "live_config",
    "wind_config",
    "snow_config",
    "earthquake_config",
)


def get_default_project() -> dict:
    """Boş bir proje iskeleti döner."""
    return {
        "project":            dict(DEFAULT_PROJECT),
        "points":             dict(DEFAULT_POINTS),
        "polygons":           dict(DEFAULT_POLYGONS),
        "dead_config":        _deepcopy(DEFAULT_DEAD_CONFIG),
        "live_config":        _deepcopy(DEFAULT_LIVE_CONFIG),
        "wind_config":        dict(DEFAULT_WIND_CONFIG),
        "snow_config":        dict(DEFAULT_SNOW_CONFIG),
        "earthquake_config":  _deepcopy(DEFAULT_EARTHQUAKE_CONFIG),
    }


# ======================================================================
# YÜKLE / KAYDET
# ======================================================================

def load_project(path: str) -> dict:
    """
    Proje JSON'unu okur, eksik alanları varsayılanla doldurur.
    Şema dışı anahtarları yok saymaz, korur (ileri uyumluluk).
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    base = get_default_project()

    # 1) Alt sözlükleri doldur (eksik anahtarlar default'tan gelir)
    for key in SCHEMA_KEYS:
        if key in raw and isinstance(raw[key], dict):
            base[key].update(raw[key])

    # 2) Şema dışı anahtarları koru
    for key, val in raw.items():
        if key not in base:
            base[key] = val

    return base


def save_project(project: dict, path: str):
    """Projeyi JSON'a yazar (insan-okur biçimde)."""
    # Sadece şema anahtarlarını yaz (opsiyonel olarak fazlalıkları da yaz)
    out = {k: project.get(k, {}) for k in SCHEMA_KEYS}
    # Şema dışı ekstralar
    for k, v in project.items():
        if k not in out:
            out[k] = v

    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


# ======================================================================
# LOAD MANAGER <-> CONFIG DÖNÜŞÜMÜ
# ======================================================================

def load_manager_to_config(load_manager) -> dict:
    """
    LoadManager'daki definitions ve assignments'ı JSON'a
    çevrilebilir sözlüklere dönüştürür.
    """
    definitions = []
    for d in load_manager.definitions.values():
        try:
            value = d.calculate(load_manager.material_weights)
        except Exception:
            value = 0.0
        definitions.append({
            "id": d.id,
            "name": d.name,
            "load_type": d.load_type,
            "value": round(value, 4),
            "unit": getattr(d, "unit", "kN/m²"),
            "source": d.source,
            "description": d.description,
        })

    assignments = {
        str(elem_id): {
            "G": list(assignment.get("G", [])),
            "Q": list(assignment.get("Q", [])),
        }
        for elem_id, assignment in load_manager.assignments.items()
    }

    return {
        "definitions": definitions,
        "assignments": assignments,
    }


def config_to_load_manager(config: dict, load_manager):
    """
    JSON'dan okunan dead_config / live_config sözlüklerini
    LoadManager'a geri yükler.

    Definitions: LoadDefinition olarak yeniden inşa edilir.
    Assignments: doğrudan LoadManager.assignments'a yazılır.
    """
    from structload.loads.load_definition import LoadDefinition

    for d in config.get("definitions", []):
        try:
            # Aynı ID zaten varsa atla (çift yükleme koruması)
            if d["id"] in load_manager.definitions:
                continue

            definition = LoadDefinition(
                id=d["id"],
                name=d["name"],
                load_type=d["load_type"],
                value=d["value"],
                unit=d.get("unit", "kN/m²"),
                source=d.get("source", "user"),
                description=d.get("description", ""),
            )
            load_manager.add_definition(definition)
        except Exception as e:
            print(f"[config_to_load_manager] '{d.get('id')}' atlandı: {e}")

    for elem_id, kinds in config.get("assignments", {}).items():
        for load_id in kinds.get("G", []):
            try:
                load_manager.assign(elem_id, load_id)
            except Exception:
                pass
        for load_id in kinds.get("Q", []):
            try:
                load_manager.assign(elem_id, load_id)
            except Exception:
                pass


# ======================================================================
# YARDIMCI
# ======================================================================

def _deepcopy(obj):
    """Küçük sözlük/listeler için güvenli derin kopya."""
    if isinstance(obj, dict):
        return {k: _deepcopy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deepcopy(v) for v in obj]
    return obj