# data/serializer.py
import dataclasses
import json
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from core.units import UnitSystem
from data.enums import ENUM_REGISTRY, PolygonType
from domain.grid import Grid, ObliqueAxis, Axis
from domain.definition import (
    AreaSection, AnalysisManager, AreaGravityLoad, AreaRefTemperatureLoad,
    AreaStrainLoad, AreaSurfacePressureLoad, AreaTemperatureLoad,
    AreaUniformLoad, AreaUniformToFrameLoad, AreaWindPressureLoad,
    AutoSeismicTSC2018, ComboItem, FrameDistributedLoad, FrameGravityLoad,
    FrameTemperatureLoad, GeneralProjectInfo, LinkProp, LinkPropLinear,
    LoadCase, LoadCombination, LoadManager, LoadPattern, LoadSegment,
    Material, ModalCase, PointLoad, ProjectConfig, ProjectInfo,
    QuadDefinition, ReportManager, ResponseSpectrumCase,
    ResponseSpectrumLoadAssignment, Restraint, Section, SectionCut,
    SeismicConfig, SiteInformation, SnowConfig, SpectrumFunction,
    StaticLoadAssignment, WindConfig, WindResult, ConstraintDefinition,
    MassAssembly, MassContribution, SDPolygonPoint, SDShape, SDSection,
)
from domain.element import Area, Frame, Link, Node
from domain.polygon import Polygon
from domain.plane import ASSOC_KINDS, ASSOC_STATUSES, PendingChange, Plane
from domain.scene import Scene
from domain.vertex import Vertex
from domain.line import Line

from logging_config import CadLogger

logger = CadLogger.get(__name__)


DATACLASS_REGISTRY: dict[str, type] = {
    cls.__name__: cls for cls in (
        Grid, ObliqueAxis, Axis,Vertex, Line,
        ProjectInfo, GeneralProjectInfo, SiteInformation, ProjectConfig,
        WindConfig, SnowConfig, SeismicConfig, LoadPattern,
        StaticLoadAssignment, LoadCase, ModalCase, ComboItem,
        LoadCombination, SpectrumFunction, ResponseSpectrumLoadAssignment,
        ResponseSpectrumCase, AutoSeismicTSC2018, PointLoad,
        FrameDistributedLoad, FrameGravityLoad, FrameTemperatureLoad,
        AreaGravityLoad, AreaRefTemperatureLoad, AreaStrainLoad,
        AreaSurfacePressureLoad, AreaTemperatureLoad, AreaUniformLoad,
        AreaUniformToFrameLoad, AreaWindPressureLoad, Material, Section,
        AreaSection, LinkProp, LinkPropLinear, Restraint, AnalysisManager,
        LoadManager, WindResult, ReportManager, SectionCut, QuadDefinition,
        ConstraintDefinition, LoadSegment, MassAssembly, MassContribution,
        SDPolygonPoint, SDShape, SDSection,
    )
}

CLASS_REGISTRY: dict[str, type] = {
    "Node": Node, "Frame": Frame, "Area": Area, "Link": Link, "Polygon": Polygon,
}


def _encode_plane(p: Plane) -> dict:
    return {
        "__plane__": True,
        "plane_id": p.plane_id,
        "name": p.name,
        "origin": [float(x) for x in p.origin],
        "normal": [float(x) for x in p.normal],
        "u": [float(x) for x in p.u],
        "v": [float(x) for x in p.v],
        "u_min": p.u_min, "u_max": p.u_max,
        "v_min": p.v_min, "v_max": p.v_max,
        "depth_minus": p.depth_minus, "depth_plus": p.depth_plus,
        "auto_assoc": p.auto_assoc,
        "auto_assoc_ignore_bounds": p.auto_assoc_ignore_bounds,
        "associated": {k: sorted(int(x) for x in v) for k, v in p.associated.items()},
        "excluded": {k: sorted(int(x) for x in v) for k, v in p.excluded.items()},
        "association_status": {
            k: {str(uid): s for uid, s in statuses.items()}
            for k, statuses in p.association_status.items()
        },
        "pending": [
            {"op": pc.op, "kind": pc.kind, "id": pc.id, "data": _encode(pc.data)}
            for pc in p.pending.values()
        ],
    }


def _decode_plane(d: dict) -> Plane:
    p = Plane(
        origin=np.array(d["origin"], float),
        normal=np.array(d["normal"], float),
        u=np.array(d["u"], float),
        v=np.array(d["v"], float),
        plane_id=d.get("plane_id"),
        name=d.get("name", ""),
        depth_minus=d.get("depth_minus", 0.0),
        depth_plus=d.get("depth_plus", 0.0),
    )
    p.u_min, p.u_max = d.get("u_min"), d.get("u_max")
    p.v_min, p.v_max = d.get("v_min"), d.get("v_max")
    p.auto_assoc = d.get("auto_assoc", True)
    p.auto_assoc_ignore_bounds = d.get("auto_assoc_ignore_bounds", False)
    for k in ASSOC_KINDS:
        p.associated[k] = set(int(x) for x in d.get("associated", {}).get(k, []))
        p.excluded[k] = set(int(x) for x in d.get("excluded", {}).get(k, []))
        statuses = d.get("association_status", {}).get(k, {})
        if any(s not in ASSOC_STATUSES for s in statuses.values()):
            raise ValueError(f"Invalid plane association status in {k}")
        p.association_status[k] = {int(uid): s for uid, s in statuses.items()}
    for pc_data in d.get("pending", []):
        pc = PendingChange(
            op=pc_data["op"], kind=pc_data["kind"],
            id=pc_data["id"], data=_decode(pc_data.get("data")),
        )
        p.pending[(pc.kind, pc.id)] = pc
    return p


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, np.ndarray):
        return {"__ndarray__": obj.tolist()}
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, Plane):
        return _encode_plane(obj)
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
            if k in ("project", "_plane_associations_dirty", "is_selected"):
                continue
            data[k] = _encode(v)
        return data
    return str(obj)


def _decode(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    if "__ndarray__" in obj:
        return np.array(obj["__ndarray__"], dtype=float)
    if obj.get("__plane__"):
        return _decode_plane(obj)
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
        return cls(**{k: _decode(v) for k, v in obj.items() if k in fields})
    if "__object__" in obj:
        cls = CLASS_REGISTRY.get(obj["__object__"])
        if not cls:
            return obj
        instance = cls.__new__(cls)
        instance.is_selected = False
        decoded = {}
        for k, v in obj.items():
            if k in ("__object__", "is_selected"):
                continue
            if k == "poly_type":
                decoded[k] = PolygonType(v) if cls is Polygon else v
            else:
                decoded[k] = _decode(v)
        instance.__dict__.update(decoded)
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


def save_project_file(project, path: Path) -> None:
    scene = project.scene
    scene_payload = {
        "show_local_axes": scene.show_local_axes,
        "show_local_axes_for_selected": scene.show_local_axes_for_selected,
        "show_local_axes_scale": scene.show_local_axes_scale,
        "units": scene.units,
        "nodes": [_encode(n) for n in scene.nodes.values()],
        "frames": [_encode(f) for f in scene.frames.values()],
        "areas": [_encode(a) for a in scene.areas.values()],
        "links": [_encode(l) for l in scene.links.values()],
    }
    u_sys = project.unit_system
    payload = {
        "version": 5,
        "info": _encode(project.info),
        "general_info": _encode(project.general_info),
        "site_info": _encode(project.site_info),
        "config": _encode(project.config),
        "scene": scene_payload,
        "loads": _encode(project.loads),
        "analysis": _encode(project.analysis),
        "report": _encode(project.report),
        "unit_system": u_sys.value if isinstance(u_sys, Enum) else u_sys,
        "grid": _encode(project.grid),
        "materials": {k: _encode(v) for k, v in project.materials.items()},
        "sections": {k: _encode(v) for k, v in project.sections.items()},
        "area_sections": {k: _encode(v) for k, v in project.area_sections.items()},
        "link_props": {k: _encode(v) for k, v in project.link_props.items()},
        "load_patterns": {k: _encode(v) for k, v in project.load_patterns.items()},
        "load_cases": {k: _encode(v) for k, v in project.load_cases.items()},
        "modal_cases": {k: _encode(v) for k, v in project.modal_cases.items()},
        "combinations": {k: _encode(v) for k, v in project.combinations.items()},
        "spectrum_functions": {k: _encode(v) for k, v in project.spectrum_functions.items()},
        "response_spectrum_cases": {k: _encode(v) for k, v in project.response_spectrum_cases.items()},
        "auto_seismics": {k: _encode(v) for k, v in project.auto_seismics.items()},
        "mass_source_map": project.mass_source_map,
        "section_cuts": {k: _encode(v) for k, v in project.section_cuts.items()},
        "diaphragms": project.diaphragms,
        "joint_constraints": project.joint_constraints,
        "frame_modifiers": project.frame_modifiers,
        "frame_design_procs": project.frame_design_procs,
        "frame_auto_mesh": project.frame_auto_mesh,
        "custom_planes": {k: _encode_plane(p) for k, p in project.custom_planes.items()},
    }
    content = json.dumps(payload, cls=DomainJSONEncoder, indent=2, ensure_ascii=False)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", content)


def load_project_file(path: Path):
    from domain.project import Project

    with zipfile.ZipFile(path, "r") as zf:
        if "project.json" not in zf.namelist():
            raise ValueError(f"project.json arşivde yok: {zf.namelist()}")
        payload = json.loads(zf.read("project.json").decode("utf-8"))

    proj = Project()
    proj.info = _decode(payload.get("info", {}))
    proj.general_info = _decode(payload.get("general_info", {}))
    proj.site_info = _decode(payload.get("site_info", {}))
    proj.config = _decode(payload.get("config", {}))
    proj.loads = _decode(payload.get("loads", {}))
    proj.analysis = _decode(payload.get("analysis", {}))
    proj.report = _decode(payload.get("report", {}))

    decoded_grid = _decode(payload.get("grid", {}))
    if decoded_grid:
        proj.grid = decoded_grid

    raw_unit = payload.get("unit_system", UnitSystem.N_MM)
    if isinstance(raw_unit, UnitSystem):
        proj.unit_system = raw_unit
    elif isinstance(raw_unit, str):
        proj.unit_system = UnitSystem.from_sap(raw_unit)
    elif isinstance(raw_unit, int):
        proj.unit_system = UnitSystem(raw_unit)

    for key, attr in (
        ("materials", "materials"), ("sections", "sections"),
        ("area_sections", "area_sections"), ("link_props", "link_props"),
        ("load_patterns", "load_patterns"), ("load_cases", "load_cases"),
        ("modal_cases", "modal_cases"), ("combinations", "combinations"),
        ("spectrum_functions", "spectrum_functions"),
        ("response_spectrum_cases", "response_spectrum_cases"),
        ("auto_seismics", "auto_seismics"), ("section_cuts", "section_cuts"),
    ):
        setattr(proj, attr, {k: _decode(v) for k, v in payload.get(key, {}).items()})

    proj.mass_source_map = payload.get("mass_source_map", {})
    proj.diaphragms = payload.get("diaphragms", {})
    proj.joint_constraints = payload.get("joint_constraints", {})
    proj.frame_modifiers = payload.get("frame_modifiers", {})
    proj.frame_design_procs = payload.get("frame_design_procs", {})
    proj.frame_auto_mesh = payload.get("frame_auto_mesh", {})

    scene = Scene(proj)
    scene_data = payload.get("scene", {})
    if isinstance(scene_data, dict):
        scene.show_local_axes = bool(scene_data.get("show_local_axes", False))
        scene.show_local_axes_for_selected = bool(scene_data.get("show_local_axes_for_selected", True))
        scene.show_local_axes_scale = float(scene_data.get("show_local_axes_scale", 1.0))
        scene.units = scene_data.get("units", "N, mm, C")

        node_map: dict[int, Node] = {}
        for n_data in scene_data.get("nodes", []):
            node = _decode(n_data)
            if isinstance(node, Node) and node.unique_id not in node_map:
                node.connected = []
                scene.add_node(node)
                node_map[node.unique_id] = node

        def _resolve(ref):
            if isinstance(ref, Node):
                return node_map.get(ref.unique_id, ref)
            uid = ref.get("unique_id") if isinstance(ref, dict) else ref
            return node_map.get(int(uid)) if uid is not None else None

        for f_data in scene_data.get("frames", []):
            frame = _decode(f_data)
            if isinstance(frame, Frame):
                frame.node_i = _resolve(frame.node_i) or frame.node_i
                frame.node_j = _resolve(frame.node_j) or frame.node_j
                if isinstance(frame.section, str):
                    frame.section = proj.get_section_by_name(frame.section)
                if frame.node_i and frame.node_j:
                    scene.add_frame(frame)

        for a_data in scene_data.get("areas", []):
            area = _decode(a_data)
            if isinstance(area, Area):
                area.nodes = [n for n in (_resolve(x) for x in area.nodes) if n]
                if area.nodes:
                    scene.add_area(area)

        for l_data in scene_data.get("links", []):
            link = _decode(l_data)
            if isinstance(link, Link):
                link.node_i = _resolve(link.node_i) or link.node_i
                link.node_j = _resolve(link.node_j) or link.node_j
                if link.node_i and link.node_j:
                    scene.add_link(link)

    proj.custom_planes = {
        k: _decode_plane(v) for k, v in payload.get("custom_planes", {}).items()
    }
    proj.scene = scene
    proj.scene.project = proj
    return proj