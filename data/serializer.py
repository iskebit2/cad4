# data/serializer.py
"""
Proje geneli serileştirme merkezi.
Tüm veri dönüşümleri, JSON encode/decode işlemleri burada yapılır.
"""
import json
import dataclasses
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Type

from data.enums import ENUM_REGISTRY, UnitSystem
from domain.element import Node, Frame, Area, Link, Polygon
from domain.definition import (
    AnalysisManager, AreaGravityLoad, AreaRefTemperatureLoad, AreaStrainLoad,
    AreaSurfacePressureLoad, AreaTemperatureLoad, AreaUniformLoad, AreaUniformToFrameLoad,
    AreaWindPressureLoad, AutoSeismicTSC2018, ComboItem, FrameDistributedLoad,
    FrameGravityLoad, FramePointLoad, FrameTemperatureLoad, GeneralProjectInfo,
    GridConfig, LinkProp, LinkPropLinear, LoadCase, LoadCombination, LoadManager,
    LoadPattern, Material, ModalCase, PointLoad, ProjectConfig, ProjectInfo,
    ReportManager, ResponseSpectrumCase, ResponseSpectrumLoadAssignment, Restraint,
    Section, SeismicConfig, SiteInformation, SnowConfig, SpectrumFunction,
    StaticLoadAssignment, WindConfig
)
from domain.scene import Scene

from logging_config import CadLogger
logger = CadLogger.get(__name__)

DATACLASS_REGISTRY: Dict[str, Type] = {
    "ProjectInfo": ProjectInfo,
    "GeneralProjectInfo": GeneralProjectInfo,
    "SiteInformation": SiteInformation,
    "ProjectConfig": ProjectConfig,
    "WindConfig": WindConfig,
    "SnowConfig": SnowConfig,
    "SeismicConfig": SeismicConfig,
    "LoadPattern": LoadPattern,
    "StaticLoadAssignment": StaticLoadAssignment,
    "LoadCase": LoadCase,
    "ModalCase": ModalCase,
    "ComboItem": ComboItem,
    "LoadCombination": LoadCombination,
    "SpectrumFunction": SpectrumFunction,
    "ResponseSpectrumLoadAssignment": ResponseSpectrumLoadAssignment,
    "ResponseSpectrumCase": ResponseSpectrumCase,
    "AutoSeismicTSC2018": AutoSeismicTSC2018,
    "PointLoad": PointLoad,
    "FramePointLoad": FramePointLoad,
    "FrameDistributedLoad": FrameDistributedLoad,
    "FrameGravityLoad": FrameGravityLoad,
    "FrameTemperatureLoad": FrameTemperatureLoad,
    "AreaGravityLoad": AreaGravityLoad,
    "AreaRefTemperatureLoad": AreaRefTemperatureLoad,
    "AreaStrainLoad": AreaStrainLoad,
    "AreaSurfacePressureLoad": AreaSurfacePressureLoad,
    "AreaTemperatureLoad": AreaTemperatureLoad,
    "AreaUniformLoad": AreaUniformLoad,
    "AreaUniformToFrameLoad": AreaUniformToFrameLoad,
    "AreaWindPressureLoad": AreaWindPressureLoad,
    "Material": Material,
    "Section": Section,
    "LinkProp": LinkProp,
    "LinkPropLinear": LinkPropLinear,
    "Restraint": Restraint,
    "GridConfig": GridConfig,
    "AnalysisManager": AnalysisManager,
    "LoadManager": LoadManager,
    "ReportManager": ReportManager,
}

CLASS_REGISTRY: Dict[str, Type] = {
    "Node": Node,
    "Frame": Frame,
    "Area": Area,
    "Link": Link,
    "Polygon": Polygon,
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
        return {"__dict__": {str(k): _encode(v) for k, v in obj.items()}}
    if isinstance(obj, list):
        return {"__list__": [_encode(v) for v in obj]}
    if hasattr(obj, "__dict__"):
        data = {"__object__": type(obj).__name__}
        for k, v in obj.__dict__.items():
            if k == "project":
                continue
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
        cls = DATACLASS_REGISTRY.get(obj["__dataclass__"])
        if not cls:
            return obj
        fields = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: _decode(v) for k, v in obj.items() if k in fields}
        return cls(**kwargs)
    if "__object__" in obj:
        class_name = obj["__object__"]
        cls = CLASS_REGISTRY.get(class_name)
        if not cls:
            return obj
        instance = cls.__new__(cls)
        decoded_dict = {}
        for k, v in obj.items():
            if k == "__object__":
                continue
            decoded_dict[k] = _decode(v)
        instance.__dict__.update(decoded_dict)
        return instance
    return obj


class DomainJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, (set, frozenset, tuple)):
            return list(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return super().default(obj)


def save_project_file(project: Any, path: Path) -> None:
    logger.info(f"[Save Debug] Proje diske yazılıyor: {path.name}")
    
    scene = project.scene
    scene_payload = {
        "show_local_axes": scene.show_local_axes,
        "show_local_axes_for_selected": scene.show_local_axes_for_selected,
        "show_local_axes_scale": scene.show_local_axes_scale,
        "units": scene.units,
        "nodes": [_encode(n) for n in scene.nodes.values()],
        "frames": [_encode(f) for f in scene.frames.values() if not getattr(f, "is_temporary", False)],
        "areas": [_encode(a) for a in scene.areas.values()],
        "links": [_encode(l) for l in scene.links.values()],
        "polygons": [_encode(p) for p in scene.polygons.values() if not getattr(p, "is_temporary", False)],
    }
    logger.info(f"[Save Debug] -> Scene kaydediliyor: {len(scene.nodes)} düğüm, {len(scene.frames)} çubuk, {len(scene.areas)} alan, {len(scene.links)} link, {len(scene.polygons)} poligon")

    u_sys = project.unit_system
    u_sys_val = u_sys.value if isinstance(u_sys, Enum) else u_sys

    payload = {
        "version": 3,
        "info": _encode(project.info),
        "general_info": _encode(project.general_info),
        "site_info": _encode(project.site_info),
        "config": _encode(project.config),
        "scene": scene_payload,
        "loads": _encode(project.loads),
        "analysis": _encode(project.analysis),
        "report": _encode(project.report),
        "unit_system": u_sys_val,
        "grid": _encode(project.grid),
        "materials": {k: _encode(v) for k, v in project.materials.items()},
        "sections": {k: _encode(v) for k, v in project.sections.items()},
        "link_props": {k: _encode(v) for k, v in project.link_props.items()},
        "load_patterns": {k: _encode(v) for k, v in project.load_patterns.items()},
        "load_cases": {k: _encode(v) for k, v in project.load_cases.items()},
        "modal_cases": {k: _encode(v) for k, v in project.modal_cases.items()},
        "combinations": {k: _encode(v) for k, v in project.combinations.items()},
        "spectrum_functions": {k: _encode(v) for k, v in project.spectrum_functions.items()},
        "response_spectrum_cases": {k: _encode(v) for k, v in project.response_spectrum_cases.items()},
        "auto_seismics": {k: _encode(v) for k, v in project.auto_seismics.items()},
        "mass_source_map": project.mass_source_map,
    }
    logger.info(f"[Save Debug] -> Tanımlar kaydediliyor: {len(project.materials)} malzeme, {len(project.sections)} kesit, {len(project.load_patterns)} load pattern")

    content = json.dumps(payload, cls=DomainJSONEncoder, indent=2, ensure_ascii=False)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", content)
    logger.info(f"[Save Debug] ✅ Proje başarıyla zip içine paketlendi: {path}")


def load_project_file(path: Path) -> Any:
    logger.info(f"[Load Debug] Proje dosyadan okunuyor: {path.name}")
    from domain.project import Project

    with zipfile.ZipFile(path, "r") as zf:
        if "project.json" not in zf.namelist():
            logger.error(f"[Load Debug] ❌ Hata: Arşiv içinde 'project.json' bulunamadı! İçindekiler: {zf.namelist()}")
        content = zf.read("project.json").decode("utf-8")
    payload = json.loads(content)

    proj = Project()
    proj.info = _decode(payload.get("info", {}))
    proj.general_info = _decode(payload.get("general_info", {}))
    proj.site_info = _decode(payload.get("site_info", {}))
    proj.config = _decode(payload.get("config", {}))
    proj.loads = _decode(payload.get("loads", {}))
    proj.analysis = _decode(payload.get("analysis", {}))
    proj.report = _decode(payload.get("report", {}))

    # Grid yükleme
    raw_grid = payload.get("grid", {})
    if isinstance(raw_grid, dict):
        decoded_grid = _decode(raw_grid)
        if isinstance(decoded_grid, GridConfig):
            proj.grid = decoded_grid
        else:
            proj.grid = GridConfig(
                x_coords=raw_grid.get("x_coords", [0.0, 6000.0]),
                y_coords=raw_grid.get("y_coords", [0.0, 6000.0]),
                z_coords=raw_grid.get("z_coords", [0.0, 3000.0]),
            )
    elif isinstance(raw_grid, GridConfig):
        proj.grid = raw_grid    
    
    raw_unit = payload.get("unit_system", UnitSystem.N_MM)
    if isinstance(raw_unit, int):
        proj.unit_system = UnitSystem(raw_unit)
    else:
        proj.unit_system = raw_unit

    # Tanımları geri yükle
    proj.materials = {k: _decode(v) for k, v in payload.get("materials", {}).items()}
    proj.sections = {k: _decode(v) for k, v in payload.get("sections", {}).items()}
    proj.link_props = {k: _decode(v) for k, v in payload.get("link_props", {}).items()}
    proj.load_patterns = {k: _decode(v) for k, v in payload.get("load_patterns", {}).items()}
    proj.load_cases = {k: _decode(v) for k, v in payload.get("load_cases", {}).items()}
    proj.modal_cases = {k: _decode(v) for k, v in payload.get("modal_cases", {}).items()}
    proj.combinations = {k: _decode(v) for k, v in payload.get("combinations", {}).items()}
    proj.spectrum_functions = {k: _decode(v) for k, v in payload.get("spectrum_functions", {}).items()}
    proj.response_spectrum_cases = {k: _decode(v) for k, v in payload.get("response_spectrum_cases", {}).items()}
    proj.auto_seismics = {k: _decode(v) for k, v in payload.get("auto_seismics", {}).items()}
    proj.mass_source_map = payload.get("mass_source_map", {})
    
    logger.info(f"[Load Debug] -> Tanımlar yüklendi: {len(proj.materials)} malzeme, {len(proj.sections)} kesit, {len(proj.load_patterns)} load pattern")

    # Scene ve Elemanları İki Aşamalı Güvenli İnşa Et
    scene_data = payload.get("scene", {})
    scene_obj = Scene(proj)
    if isinstance(scene_data, dict):
        scene_obj.show_local_axes = bool(scene_data.get("show_local_axes", False))
        scene_obj.show_local_axes_for_selected = bool(scene_data.get("show_local_axes_for_selected", True))
        scene_obj.show_local_axes_scale = float(scene_data.get("show_local_axes_scale", 1.0))
        scene_obj.units = scene_data.get("units", "N, mm, C")

        raw_nodes_data = scene_data.get("nodes", [])
        raw_frames_data = scene_data.get("frames", [])
        raw_areas_data = scene_data.get("areas", [])
        raw_links_data = scene_data.get("links", [])
        raw_polygons_data = scene_data.get("polygons", [])

        # 1. Aşama: Node'ları unique_id bazında tekilleştirerek yükle
        node_map = {}
        for n_data in raw_nodes_data:
            node = _decode(n_data)
            if isinstance(node, Node):
                # Mükerrer eklemeyi önle (unique_id veya koordinat bazlı kontrol)
                if node.unique_id not in node_map:
                    scene_obj.add_node(node)
                    node_map[node.unique_id] = node
                    if hasattr(node, "element_id"):
                        node_map[str(node.element_id)] = node
        logger.info(f"[Load Debug] -> Geri yüklenen tekil düğüm (node) sayısı: {len(node_map)}")

        def resolve_node(ref) -> Optional[Node]:
            if isinstance(ref, Node):
                return node_map.get(ref.unique_id) or node_map.get(str(ref.element_id))
            if isinstance(ref, dict):
                uid = ref.get("unique_id")
                if uid and int(uid) in node_map:
                    return node_map[int(uid)]
                eid = ref.get("element_id")
                if eid and str(eid) in node_map:
                    return node_map[str(eid)]
            if isinstance(ref, (int, str)):
                if int(ref) in node_map:
                    return node_map[int(ref)]
                if str(ref) in node_map:
                    return node_map[str(ref)]
            return None

        # 2. Aşama: Frame'ler (Mükerrer frame'leri engellemek için unique_id kontrolü)
        loaded_frames_count = 0
        added_frame_ids = set()
        for f_data in raw_frames_data:
            frame = _decode(f_data)
            if isinstance(frame, Frame):
                if frame.unique_id in added_frame_ids:
                    continue
                
                if not isinstance(frame.node_i, Node):
                    frame.node_i = resolve_node(frame.node_i)
                if not isinstance(frame.node_j, Node):
                    frame.node_j = resolve_node(frame.node_j)
                
                if isinstance(frame.section, str):
                    frame.section = proj.get_section_by_name(frame.section)
                elif isinstance(frame.section, dict) and "name" in frame.section:
                    frame.section = proj.get_section_by_name(frame.section["name"])
                
                if frame.node_i and frame.node_j:
                    scene_obj.add_frame(frame)
                    added_frame_ids.add(frame.unique_id)
                    loaded_frames_count += 1
        logger.info(f"[Load Debug] -> Geri yüklenen çubuk (frame) sayısı: {loaded_frames_count}")

        # 3. Aşama: Area'lar
        loaded_areas_count = 0
        added_area_ids = set()
        for a_data in raw_areas_data:
            area = _decode(a_data)
            if isinstance(area, Area):
                if area.unique_id in added_area_ids:
                    continue
                resolved_nodes = [resolve_node(n) for n in area.nodes]
                area.nodes = [fn for fn in resolved_nodes if fn is not None]
                if area.nodes:
                    scene_obj.add_area(area)
                    added_area_ids.add(area.unique_id)
                    loaded_areas_count += 1
        logger.info(f"[Load Debug] -> Geri yüklenen alan (area) sayısı: {loaded_areas_count}")

        # 4. Aşama: Link'ler
        loaded_links_count = 0
        added_link_ids = set()
        for l_data in raw_links_data:
            link = _decode(l_data)
            if isinstance(link, Link):
                if link.unique_id in added_link_ids:
                    continue
                if not isinstance(link.node_i, Node):
                    link.node_i = resolve_node(link.node_i)
                if not isinstance(link.node_j, Node):
                    link.node_j = resolve_node(link.node_j)
                if link.node_i and link.node_j:
                    scene_obj.add_link(link)
                    added_link_ids.add(link.unique_id)
                    loaded_links_count += 1
        logger.info(f"[Load Debug] -> Geri yüklenen link sayısı: {loaded_links_count}")

        # 5. Aşama: Polygon'lar
        loaded_polygons_count = 0
        added_poly_ids = set()
        for p_data in raw_polygons_data:
            poly = _decode(p_data)
            if isinstance(poly, Polygon):
                if poly.unique_id in added_poly_ids:
                    continue
                resolved_nodes = [resolve_node(n) for n in poly.nodes]
                poly.nodes = [fn for fn in resolved_nodes if fn is not None]
                if poly.nodes:
                    scene_obj.add_polygon(poly)
                    added_poly_ids.add(poly.unique_id)
                    loaded_polygons_count += 1
        logger.info(f"[Load Debug] -> Geri yüklenen poligon sayısı: {loaded_polygons_count}")

    proj.scene = scene_obj
    proj.scene.project = proj
    logger.info(f"[Load Debug] ✅ Proje başarıyla diskten okundu ve belleğe inşa edildi: {path.name}")
    return proj