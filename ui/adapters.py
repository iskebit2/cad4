# ui/adapters.py
from __future__ import annotations

from typing import Any

from data.enums import PolygonType
from domain.definition import FrameDistributedLoad, AreaUniformToFrameLoad, DistType, LoadDirection
from ui.schema import get_path, set_path

MIXED = "__MIXED__"


# ============================================================================
# NODE
# ============================================================================
def node_to_values(node) -> dict:
    return {
        "label": node.label,
        "is_visible": node.is_visible,
        "color": list(node.color[:3]) if node.color else None,
        "x": float(node.x), "y": float(node.y), "z": float(node.z),
        "coord_sys": getattr(node, "coord_sys", "GLOBAL"),
        "coord_type": getattr(node, "coord_type", "Cartesian"),
        "special_jt": bool(getattr(node, "special_jt", False)),
        "constraint_name": getattr(node, "constraint_name", None) or "",
        "restraint": (
            node.restraint.as_dict() if node.restraint
            else {"ux": False, "uy": False, "uz": False,
                  "rx": False, "ry": False, "rz": False}
        ),
        "mass_1": float(getattr(node, "mass_1", 0.0)),
        "mass_2": float(getattr(node, "mass_2", 0.0)),
        "mass_3": float(getattr(node, "mass_3", 0.0)),
        "mmi_1": float(getattr(node, "mmi_1", 0.0)),
        "mmi_2": float(getattr(node, "mmi_2", 0.0)),
        "mmi_3": float(getattr(node, "mmi_3", 0.0)),
        "added_mass_1": float(getattr(node, "added_mass_1", 0.0)),
        "added_mass_2": float(getattr(node, "added_mass_2", 0.0)),
        "added_mass_3": float(getattr(node, "added_mass_3", 0.0)),
        "added_mmi_1": float(getattr(node, "added_mmi_1", 0.0)),
        "added_mmi_2": float(getattr(node, "added_mmi_2", 0.0)),
        "added_mmi_3": float(getattr(node, "added_mmi_3", 0.0)),
        "mass_coord_sys": getattr(node, "mass_coord_sys", "Joint Local"),
        "spring_u1": float(getattr(node, "spring_u1", 0.0)),
        "spring_u2": float(getattr(node, "spring_u2", 0.0)),
        "spring_u3": float(getattr(node, "spring_u3", 0.0)),
        "spring_r1": float(getattr(node, "spring_r1", 0.0)),
        "spring_r2": float(getattr(node, "spring_r2", 0.0)),
        "spring_r3": float(getattr(node, "spring_r3", 0.0)),
    }


def values_to_node(node, v: dict) -> None:
    node.label = v.get("label", node.label)
    node.color = list(v["color"]) if v.get("color") and node.color else node.color
    node.is_visible = bool(v.get("is_visible", node.is_visible))
    node.x = float(v.get("x", node.x))
    node.y = float(v.get("y", node.y))
    node.z = float(v.get("z", node.z))
    node.coord_sys = str(v.get("coord_sys", node.coord_sys))
    node.coord_type = str(v.get("coord_type", node.coord_type))
    node.special_jt = bool(v.get("special_jt", node.special_jt))
    node.mass_coord_sys = str(v.get("mass_coord_sys", node.mass_coord_sys))

    if "constraint_name" in v:
        node.constraint_name = str(v["constraint_name"]) or None

    r = v.get("restraint", {})
    if r:
        from domain.definition import Restraint
        if node.restraint is None:
            node.restraint = Restraint()
        for k in ("ux", "uy", "uz", "rx", "ry", "rz"):
            if k in r:
                setattr(node.restraint, k, bool(r[k]))

    for key in ("spring_u1", "spring_u2", "spring_u3",
                "spring_r1", "spring_r2", "spring_r3",
                "mass_1", "mass_2", "mass_3",
                "mmi_1", "mmi_2", "mmi_3",
                "added_mass_1", "added_mass_2", "added_mass_3",
                "added_mmi_1", "added_mmi_2", "added_mmi_3"):
        if key in v:
            setattr(node, key, float(v[key]))

    node.mark_dirty()


# ============================================================================
# FRAME
# ============================================================================
def _segments_to_text(segments) -> str:
    parts = []
    for s in segments:
        if isinstance(s, dict):
            vals = (s.get("x1", 0.0), s.get("x2", 1.0),
                    s.get("q1", 0.0), s.get("q2", 0.0))
        else:
            vals = (getattr(s, "x1", 0.0), getattr(s, "x2", 1.0),
                    getattr(s, "q1", 0.0), getattr(s, "q2", 0.0))
        parts.append(",".join(f"{float(x):.4f}" for x in vals))
    return " | ".join(parts)


def _text_to_segments(text: str) -> list:
    from domain.definition import LoadSegment
    segs = []
    for chunk in (text or "").split("|"):
        nums = [p.strip() for p in chunk.replace(";", ",").split(",") if p.strip()]
        if len(nums) != 4:
            continue
        try:
            x1, x2, q1, q2 = (float(n) for n in nums)
        except ValueError:
            continue
        x1 = max(0.0, min(1.0, x1))
        x2 = max(0.0, min(1.0, x2))
        if x2 <= x1:
            x2 = min(1.0, x1 + 0.001)
        segs.append(LoadSegment(x1=x1, x2=x2, q1=q1, q2=q2))
    segs.sort(key=lambda s: s.x1)
    return segs


def frame_to_values(frame) -> dict:
    sets_list = [
        {
            "pattern_name": s.pattern_name or pat,
            "coord_sys": s.coord_sys,
            "load_dir": str(s.load_dir),
            "mode": s.mode,
            "is_relative": bool(getattr(s, "is_relative", True)),
            "segments_text": _segments_to_text(s.segments),
        }
        for pat, s in (getattr(frame, "dist_load_sets", {}) or {}).items()
    ]
    return {
        "label": frame.label,
        "is_visible": frame.is_visible,
        "color": list(frame.color[:3]) if frame.color else None,
        "rotation_deg": float(getattr(frame, "rotation_deg", 0.0)),
        "section": getattr(frame, "section", None),
        "cardinal_pt": getattr(frame, "cardinal_pt", "10 (centroid)"),
        "mirror2": bool(getattr(frame, "mirror2", False)),
        "mirror3": bool(getattr(frame, "mirror3", False)),
        "transform": bool(getattr(frame, "transform", True)),
        "insertion_coord_sys": getattr(frame, "insertion_coord_sys", "Local"),
        "jt_offset_i": tuple(getattr(frame, "jt_offset_i", (0.0, 0.0, 0.0))),
        "jt_offset_j": tuple(getattr(frame, "jt_offset_j", (0.0, 0.0, 0.0))),
        "offset_type": getattr(frame, "offset_type", "User"),
        "offset_length_i": float(getattr(frame, "offset_length_i", 0.0)),
        "offset_length_j": float(getattr(frame, "offset_length_j", 0.0)),
        "rigid_factor": float(getattr(frame, "rigid_factor", 0.0)),
        "station_type": getattr(frame, "station_type", "MinNumSta"),
        "min_num_sta": int(getattr(frame, "min_num_sta", 3)),
        "add_at_elm_int": bool(getattr(frame, "add_at_elm_int", True)),
        "add_at_pt_load": bool(getattr(frame, "add_at_pt_load", True)),
        "max_sta_spcg": getattr(frame, "max_sta_spcg", None),
        "auto_mesh": bool(getattr(frame, "auto_mesh", False)),
        "mesh_at_joints": bool(getattr(frame, "mesh_at_joints", False)),
        "mesh_at_frames": bool(getattr(frame, "mesh_at_frames", False)),
        "mesh_num_segments": int(getattr(frame, "mesh_num_segments", 0)),
        "mesh_max_length": float(getattr(frame, "mesh_max_length", 0.0)),
        "mesh_max_degrees": float(getattr(frame, "mesh_max_degrees", 0.0)),
        "mirror_abt2": bool(getattr(frame, "mirror_abt2", False)),
        "mirror_abt3": bool(getattr(frame, "mirror_abt3", False)),
        "design_proc": getattr(frame, "design_proc", "From Material"),
        "load_transfer": bool(getattr(frame, "load_transfer", True)),
        "dist_load_sets_list": sets_list,
    }


def values_to_frame(frame, v: dict) -> None:
    frame.label = v.get("label", frame.label)
    frame.color = list(v["color"]) if v.get("color") and frame.color else frame.color
    frame.is_visible = bool(v.get("is_visible", frame.is_visible))
    frame.rotation_deg = float(v.get("rotation_deg", frame.rotation_deg))

    sec = v.get("section")
    if sec is not None and hasattr(sec, "name"):
        frame.section = sec

    for k in ("cardinal_pt", "insertion_coord_sys", "offset_type",
              "station_type", "design_proc"):
        if k in v:
            setattr(frame, k, str(v[k]))
    for k in ("mirror2", "mirror3", "transform",
              "add_at_elm_int", "add_at_pt_load", "auto_mesh",
              "mesh_at_joints", "mesh_at_frames",
              "mirror_abt2", "mirror_abt3", "load_transfer"):
        if k in v:
            setattr(frame, k, bool(v[k]))
    for k in ("offset_length_i", "offset_length_j", "rigid_factor",
              "mesh_max_length", "mesh_max_degrees"):
        if k in v:
            setattr(frame, k, float(v[k]))
    if "min_num_sta" in v:
        frame.min_num_sta = int(v["min_num_sta"])
    if "mesh_num_segments" in v:
        frame.mesh_num_segments = int(v["mesh_num_segments"])
    if "max_sta_spcg" in v:
        val = v["max_sta_spcg"]
        frame.max_sta_spcg = float(val) if val is not None else None

    for key in ("jt_offset_i", "jt_offset_j"):
        val = v.get(key)
        if isinstance(val, (tuple, list)) and len(val) == 3:
            setattr(frame, key, tuple(float(x) for x in val))

    sets_v = v.get("dist_load_sets_list")
    if isinstance(sets_v, list):
        new_sets: dict[str, FrameDistributedLoad] = {}
        for item in sets_v:
            if not isinstance(item, dict):
                continue
            pat = str(item.get("pattern_name", "")).strip()
            if not pat:
                continue
            new_sets[pat] = FrameDistributedLoad(
                pattern_name=pat,
                coord_sys=str(item.get("coord_sys", "Local")),
                load_dir=str(item.get("load_dir", "7")),
                mode=str(item.get("mode", "REPLACE")),
                is_relative=bool(item.get("is_relative", True)),
                segments=_text_to_segments(item.get("segments_text", "")),
            )
        frame.dist_load_sets = new_sets

    frame.mark_dirty()


# ============================================================================
# AREA
# ============================================================================
def area_to_values(area) -> dict:
    return {
        "label": area.label,
        "is_visible": area.is_visible,
        "color": list(area.color[:3]) if area.color else None,
        "thickness": float(area.thickness),
        "material": getattr(area, "material", None),
        "section_name": getattr(area, "section_name", ""),
    }


def values_to_area(area, v: dict) -> None:
    area.label = v.get("label", area.label)
    area.color = list(v["color"]) if v.get("color") and area.color else area.color
    area.is_visible = bool(v.get("is_visible", area.is_visible))
    area.thickness = float(v.get("thickness", area.thickness))
    if "material" in v and hasattr(v["material"], "name"):
        area.material = v["material"]
    if "section_name" in v:
        area.section_name = str(v["section_name"])
    area.mark_dirty()


# ============================================================================
# LINK
# ============================================================================
def link_to_values(link) -> dict:
    return {
        "label": link.label,
        "is_visible": link.is_visible,
        "color": list(link.color[:3]) if link.color else None,
        "propname": getattr(link, "propname", ""),
    }


def values_to_link(link, v: dict) -> None:
    link.label = v.get("label", link.label)
    link.color = list(v["color"]) if v.get("color") and link.color else link.color
    link.is_visible = bool(v.get("is_visible", link.is_visible))
    link.propname = v.get("propname", link.propname)
    link.mark_dirty()


# ============================================================================
# POLYGON
# ============================================================================
def polygon_to_values(poly) -> dict:
    pt = getattr(poly, "poly_type", None)
    loads = getattr(poly, "uniform_to_frame_loads", [])
    assigned = getattr(poly, "assigned_loads", [])
    return {
        "label": poly.label,
        "is_visible": poly.is_visible,
        "is_temporary": getattr(poly, "is_temporary", False),
        "color": list(poly.color[:3]) if poly.color else None,
        "poly_type": pt.name if hasattr(pt, "name") else str(pt),
        "windplane": dict(getattr(poly, "windplane", {}) or {}),
        "show_zones_direction": poly.show_zones_direction or "",
        "zone_count": sum(len(v) for v in poly.zone_children_by_direction.values()),
        "vertex_count": len(poly.nodes),
        "assoc_count": len(poly.associated_frame_ids),
        "associated_frame_ids": list(getattr(poly, "associated_frame_ids", [])),
        "transfer_target": str(getattr(poly, "transfer_target", "frames")),
        "transfer_dist_type": str(getattr(poly, "transfer_dist_type", "one_way")),
        "is_load_area": bool(getattr(poly, "is_load_area", False)),
        "assigned_loads_summary": [
            (f"{load.source_name or load.pattern_name} | "
             f"{load.pattern_name} | {float(load.value):g} "
             f"({load.direction.value})")
            for load in assigned
        ],
        "uniform_to_frame_loads": [
            {
                "pattern_name": l.pattern_name,
                "value": float(l.value),
                "direction": l.direction.value if hasattr(l.direction, "value") else str(l.direction),
                "dist_type": l.dist_type.value if hasattr(l.dist_type, "value") else str(l.dist_type),
                "coordinate_system": getattr(l, "coordinate_system", "GLOBAL"),
            }
            for l in loads
        ],
    }


def values_to_polygon(poly, v: dict) -> None:
    

    poly.label = v.get("label", poly.label)
    poly.color = list(v["color"]) if v.get("color") and poly.color else poly.color
    poly.is_visible = bool(v.get("is_visible", poly.is_visible))
    poly.is_temporary = bool(v.get("is_temporary", getattr(poly, "is_temporary", False)))

    ids = v.get("associated_frame_ids")
    if isinstance(ids, list):
        poly.associated_frame_ids = list(ids)

    pt = v.get("poly_type")
    if pt:
        try:
            poly.poly_type = PolygonType[pt]
        except KeyError:
            pass

    if isinstance(v.get("windplane"), dict):
        poly.windplane = v["windplane"]
    if "transfer_target" in v:
        poly.transfer_target = str(v["transfer_target"])
    if "transfer_dist_type" in v:
        poly.transfer_dist_type = str(v["transfer_dist_type"])
    if "is_load_area" in v:
        poly.is_load_area = bool(v["is_load_area"])
    if "show_zones_direction" in v:
        s = str(v["show_zones_direction"]) or None
        poly.show_zones_direction = s

    loads_v = v.get("uniform_to_frame_loads")
    if isinstance(loads_v, list):
        new_loads = []
        for d in loads_v:
            if not isinstance(d, dict):
                continue
            direction = LoadDirection.GLOBAL_Z
            for cand in LoadDirection:
                if cand.value == str(d.get("direction", "GZ")) or cand.name == str(d.get("direction", "GZ")):
                    direction = cand
                    break
            new_loads.append(AreaUniformToFrameLoad(
                pattern_name=str(d.get("pattern_name", "")),
                direction=direction,
                value=float(d.get("value", 0.0)),
                dist_type=DistType.from_input(d.get("dist_type", "One way")),
                coordinate_system=str(d.get("coordinate_system", "GLOBAL")),
            ))
        poly.uniform_to_frame_loads = new_loads

    poly.mark_dirty()


# ============================================================================
# LINE
# ============================================================================
def line_to_values(line) -> dict:
    return {
        "label": line.label or "",
        "color": list(line.color[:3]) if line.color else [1.0, 1.0, 1.0],
        "width": float(line.width),
        "style": line.style,
        "visible": bool(line.visible),
        "is_column": bool(line.is_column),
        "v1x": float(line.v1.x), "v1y": float(line.v1.y), "v1z": float(line.v1.z),
        "v2x": float(line.v2.x), "v2y": float(line.v2.y), "v2z": float(line.v2.z),
        "length": float(line.length),
    }


def values_to_line(line, v: dict) -> None:
    from domain.vertex import Vertex

    if "label" in v:
        line.label = str(v["label"])
    if "color" in v:
        c = v["color"]
        line.color = (float(c[0]), float(c[1]), float(c[2]))
    if "width" in v:
        line.width = float(v["width"])
    if "style" in v:
        line.style = str(v["style"])
    if "visible" in v:
        line.visible = bool(v["visible"])
    if "is_column" in v:
        line.is_column = bool(v["is_column"])

    if any(k in v for k in ("v1x", "v1y", "v1z")):
        line.v1 = Vertex(float(v.get("v1x", line.v1.x)),
                         float(v.get("v1y", line.v1.y)),
                         float(v.get("v1z", line.v1.z)))
    if any(k in v for k in ("v2x", "v2y", "v2z")):
        line.v2 = Vertex(float(v.get("v2x", line.v2.x)),
                         float(v.get("v2y", line.v2.y)),
                         float(v.get("v2z", line.v2.z)))


# ============================================================================
# DISPATCH
# ============================================================================
_ADAPTERS = {
    "Node":    (node_to_values,    values_to_node),
    "Frame":   (frame_to_values,   values_to_frame),
    "Area":    (area_to_values,    values_to_area),
    "Link":    (link_to_values,    values_to_link),
    "Polygon": (polygon_to_values, values_to_polygon),
    "Line":    (line_to_values,    values_to_line),
}

_DEFAULT = (node_to_values, values_to_node)


def element_to_values(obj) -> dict:
    name = type(obj).__name__
    pair = _ADAPTERS.get(name)
    if pair is None:
        return {}
    return pair[0](obj)

def _apply_extras(obj, values, known_fn):
    from ui.adapters import _KNOWN_KEYS_BY_TYPE
    known = _KNOWN_KEYS_BY_TYPE.get(type(obj).__name__, set())
    for k, v in values.items():
        if k in known or k.startswith("_"):
            continue
        try:
            setattr(obj, k, v)
        except Exception:
            pass

def values_to_element(obj, values: dict) -> None:
    name = type(obj).__name__
    pair = _ADAPTERS.get(name)
    if pair is None:
        return
    pair[1](obj, values)
    _apply_extras(obj, values, pair[1])



# ============================================================================
# MULTI-SELECT COMMON VALUES
# ============================================================================
def elements_to_common_values(elements) -> dict:
    if not elements:
        return {}
    if len(elements) == 1:
        return element_to_values(elements[0])

    dicts = [element_to_values(e) for e in elements]

    def _keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out |= _keys(v, full)
            else:
                out.add(full)
        return out

    all_keys = _keys(dicts[0])
    result = {}
    for key in all_keys:
        values = [get_path(d, key) for d in dicts]
        first = values[0]
        set_path(result, key,
                 first if all(v == first for v in values) else MIXED)
    return result