# data/serializer.py
"""
Tüm definition nesnelerini JSON'a çevirir ve geri yükler.
Enum, tuple ve dataclass'ları tanır. GUID yoktur.
"""
import json
import dataclasses
from enum import Enum
from typing import Any, Dict, Type

from domain import definition as D
from domain.definition_manager import DefinitionManager


ENUM_REGISTRY: Dict[str, Type[Enum]] = {
    "MatType": D.MatType,
    "SectionType": D.SectionType,
    "LinkPropType": D.LinkPropType,
    "ElementType": D.ElementType,
    "ObjType": D.ObjType,
    "LoadType": D.LoadType,
    "LoadDirection": D.LoadDirection,
    "SpectrumSourceType": D.SpectrumSourceType,
    "LoadPatternType": D.LoadPatternType,
    "LoadCaseType": D.LoadCaseType,
    "ComboType": D.ComboType,
}

DATACLASS_REGISTRY: Dict[str, Type] = {
    "GeneralProjectInfo": D.GeneralProjectInfo,
    "SiteInformation": D.SiteInformation,
    "LoadPattern": D.LoadPattern,
    "StaticLoadAssignment": D.StaticLoadAssignment,
    "LoadCase": D.LoadCase,
    "ModalCase": D.ModalCase,
    "ComboItem": D.ComboItem,
    "LoadCombination": D.LoadCombination,
    "SpectrumFunction": D.SpectrumFunction,
    "ResponseSpectrumLoadAssignment": D.ResponseSpectrumLoadAssignment,
    "ResponseSpectrumCase": D.ResponseSpectrumCase,
    "AutoSeismicTSC2018": D.AutoSeismicTSC2018,
    "PointLoad": D.PointLoad,
    "FramePointLoad": D.FramePointLoad,
    "FrameDistributedLoad": D.FrameDistributedLoad,
    "FrameGravityLoad": D.FrameGravityLoad,
    "FrameTemperatureLoad": D.FrameTemperatureLoad,
    "AreaGravityLoad": D.AreaGravityLoad,
    "AreaRefTemperatureLoad": D.AreaRefTemperatureLoad,
    "AreaStrainLoad": D.AreaStrainLoad,
    "AreaSurfacePressureLoad": D.AreaSurfacePressureLoad,
    "AreaTemperatureLoad": D.AreaTemperatureLoad,
    "AreaUniformLoad": D.AreaUniformLoad,
    "AreaUniformToFrameLoad": D.AreaUniformToFrameLoad,
    "AreaWindPressureLoad": D.AreaWindPressureLoad,
    "Material": D.Material,
    "Section": D.Section,
    "LinkProp": D.LinkProp,
    "LinkPropLinear": D.LinkPropLinear,
    "Restraint": D.Restraint,
}


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return {"__enum__": type(obj).__name__, "value": obj.value}
    if isinstance(obj, tuple):
        return {"__tuple__": [_encode(v) for v in obj]}
    if dataclasses.is_dataclass(obj):
        data = {"__dataclass__": type(obj).__name__}
        for f in dataclasses.fields(obj):
            data[f.name] = _encode(getattr(obj, f.name))
        return data
    if isinstance(obj, dict):
        return {"__dict__": {k: _encode(v) for k, v in obj.items()}}
    if isinstance(obj, list):
        return {"__list__": [_encode(v) for v in obj]}
    if hasattr(obj, "__dict__"):
        data = {"__object__": type(obj).__name__}
        for k, v in obj.__dict__.items():
            data[k] = _encode(v)
        return data
    return str(obj)


def _decode(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    if "__enum__" in obj:
        return ENUM_REGISTRY[obj["__enum__"]](obj["value"])
    if "__tuple__" in obj:
        return tuple(_decode(v) for v in obj["__tuple__"])
    if "__list__" in obj:
        return [_decode(v) for v in obj["__list__"]]
    if "__dict__" in obj:
        return {k: _decode(v) for k, v in obj["__dict__"].items()}
    if "__dataclass__" in obj:
        cls = DATACLASS_REGISTRY[obj["__dataclass__"]]
        fields = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: _decode(v) for k, v in obj.items() if k in fields}
        return cls(**kwargs)
    if "__object__" in obj:
        cls = DATACLASS_REGISTRY[obj["__object__"]]
        inst = cls.__new__(cls)
        for k, v in obj.items():
            if k != "__object__":
                setattr(inst, k, _decode(v))
        return inst
    return obj


def save_project(manager: DefinitionManager, path: str) -> None:
    payload = {
        "version": 2,   # GUID kaldırıldı → şema versiyonu yükseltildi
        "materials": _encode(manager.materials),
        "sections": _encode(manager.sections),
        "link_props": _encode(manager.link_props),
        "load_patterns": _encode(manager.load_patterns),
        "load_cases": _encode(manager.load_cases),
        "modal_cases": _encode(manager.modal_cases),
        "combinations": _encode(manager.combinations),
        "spectrum_functions": _encode(manager.spectrum_functions),
        "response_spectrum_cases": _encode(manager.response_spectrum_cases),
        "auto_seismics": _encode(manager.auto_seismics),
        "mass_source_map": _encode(manager.mass_source_map),
        "project_info": _encode(manager.project_info),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_project(manager: DefinitionManager, path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Sözlükler artık doğrudan name key'li — ek index kurmaya gerek yok
    manager.materials = _decode(payload.get("materials", {}))
    manager.sections = _decode(payload.get("sections", {}))
    manager.link_props = _decode(payload.get("link_props", {}))
    manager.load_patterns = _decode(payload.get("load_patterns", {}))
    manager.load_cases = _decode(payload.get("load_cases", {}))
    manager.modal_cases = _decode(payload.get("modal_cases", {}))
    manager.combinations = _decode(payload.get("combinations", {}))
    manager.spectrum_functions = _decode(payload.get("spectrum_functions", {}))
    manager.response_spectrum_cases = _decode(payload.get("response_spectrum_cases", {}))
    manager.auto_seismics = _decode(payload.get("auto_seismics", {}))
    manager.mass_source_map = _decode(payload.get("mass_source_map", {}))
    manager.project_info = _decode(payload.get("project_info", {}))