# ui/adapters.py
"""Element ↔ dict dönüşümleri.

Ana uygulama bu modülü çağırır; ImGui tarafında sadece dict dolaşır.
"""
from __future__ import annotations

from typing import Any

from data.enums import PolygonType
from domain.definition import FrameDistributedLoad
from ui.schema import get_path, set_path

MIXED = "__MIXED__"   # çakışmayacak bir string (nadir)


# ============================================================================
# NODE
# ============================================================================
def node_to_values(node) -> dict[str, Any]:
    return {
        "label": node.label,
        "is_visible": node.is_visible,
        "color": list(node.color[:3]) if node.color else None,
        "x": float(node.x),
        "y": float(node.y),
        "z": float(node.z),
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


def values_to_node(node, v: dict[str, Any]) -> None:
    node.label = v.get("label", node.label)
    node.color = list(v.get("color", node.color)) if node.color else None
    node.is_visible = bool(v.get("is_visible", node.is_visible))
    node.x = float(v.get("x", node.x))
    node.y = float(v.get("y", node.y))
    node.z = float(v.get("z", node.z))

    node.coord_sys = str(v.get("coord_sys", node.coord_sys))
    node.coord_type = str(v.get("coord_type", node.coord_type))
    node.special_jt = bool(v.get("special_jt", node.special_jt))

    cname = v.get("constraint_name")
    if cname is not None:
        node.constraint_name = str(cname) or None

    node.mass_coord_sys = str(v.get("mass_coord_sys", node.mass_coord_sys))

    r = v.get("restraint", {})
    if r:
        from domain.definition import Restraint
        if node.restraint is None:
            node.restraint = Restraint()
        for k in ("ux", "uy", "uz", "rx", "ry", "rz"):
            if k in r:
                setattr(node.restraint, k, bool(r[k]))

    for key in ("spring_u1", "spring_u2", "spring_u3",
            "spring_r1", "spring_r2", "spring_r3"):
        if key in v:
            setattr(node, key, float(v[key]))

    for key in (
        "mass_1", "mass_2", "mass_3",
        "mmi_1", "mmi_2", "mmi_3",
        "added_mass_1", "added_mass_2", "added_mass_3",
        "added_mmi_1", "added_mmi_2", "added_mmi_3",
    ):
        if key in v:
            setattr(node, key, float(v[key]))

    node.mark_dirty()


# ============================================================================
# FRAME
# ============================================================================
def _segments_to_text(segments) -> str:
    """Segment listesi → 'x1,x2,q1,q2 | x1,x2,q1,q2'."""
    parts = []
    for s in segments:
        if isinstance(s, dict):
            x1 = float(s.get("x1", 0.0))
            x2 = float(s.get("x2", 1.0))
            q1 = float(s.get("q1", 0.0))
            q2 = float(s.get("q2", 0.0))
        else:
            x1 = float(getattr(s, "x1", 0.0))
            x2 = float(getattr(s, "x2", 1.0))
            q1 = float(getattr(s, "q1", 0.0))
            q2 = float(getattr(s, "q2", 0.0))
        parts.append(f"{x1:.4f},{x2:.4f},{q1:.4f},{q2:.4f}")
    return " | ".join(parts)


def _text_to_segments(text: str) -> list:
    from domain.definition import LoadSegment
    segs = []
    if not text:
        return segs
    for chunk in text.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
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


def frame_to_values(frame) -> dict[str, Any]:
    sec = getattr(frame, "section", None)
    sets = getattr(frame, "dist_load_sets", {}) or {}

    sets_list = []
    for pat_name, s in sets.items():
        sets_list.append({
            "pattern_name": s.pattern_name or pat_name,
            "coord_sys": s.coord_sys,
            "load_dir": str(s.load_dir),
            "mode": s.mode,
            "is_relative": bool(getattr(s, "is_relative", True)),
            "segments_text": _segments_to_text(s.segments),
        })

    return {
        "label": frame.label,
        "is_visible": frame.is_visible,
        "color": list(frame.color[:3]) if frame.color else None,
        "rotation_deg": float(getattr(frame, "rotation_deg", 0.0)),
        "section": sec,

        # --- Insertion Point ---
        "cardinal_pt": getattr(frame, "cardinal_pt", "10 (centroid)"),
        "mirror2": bool(getattr(frame, "mirror2", False)),
        "mirror3": bool(getattr(frame, "mirror3", False)),
        "transform": bool(getattr(frame, "transform", True)),
        "insertion_coord_sys": getattr(frame, "insertion_coord_sys", "Local"),
        "jt_offset_i": tuple(getattr(frame, "jt_offset_i", (0.0, 0.0, 0.0))),
        "jt_offset_j": tuple(getattr(frame, "jt_offset_j", (0.0, 0.0, 0.0))),

        # --- End Offset ---
        "offset_type": getattr(frame, "offset_type", "User"),
        "offset_length_i": float(getattr(frame, "offset_length_i", 0.0)),
        "offset_length_j": float(getattr(frame, "offset_length_j", 0.0)),
        "rigid_factor": float(getattr(frame, "rigid_factor", 0.0)),

        # --- Output Stations ---
        "station_type": getattr(frame, "station_type", "MinNumSta"),
        "min_num_sta": int(getattr(frame, "min_num_sta", 3)),
        "add_at_elm_int": bool(getattr(frame, "add_at_elm_int", True)),
        "add_at_pt_load": bool(getattr(frame, "add_at_pt_load", True)),
        "max_sta_spcg": getattr(frame, "max_sta_spcg", None),

        # --- Auto Mesh ---
        "auto_mesh": bool(getattr(frame, "auto_mesh", False)),
        "mesh_at_joints": bool(getattr(frame, "mesh_at_joints", False)),
        "mesh_at_frames": bool(getattr(frame, "mesh_at_frames", False)),
        "mesh_num_segments": int(getattr(frame, "mesh_num_segments", 0)),
        "mesh_max_length": float(getattr(frame, "mesh_max_length", 0.0)),
        "mesh_max_degrees": float(getattr(frame, "mesh_max_degrees", 0.0)),

        # --- Local Axes ---
        "mirror_abt2": bool(getattr(frame, "mirror_abt2", False)),
        "mirror_abt3": bool(getattr(frame, "mirror_abt3", False)),

        # --- Design ---
        "design_proc": getattr(frame, "design_proc", "From Material"),
        "load_transfer": bool(getattr(frame, "load_transfer", True)),

        # --- Yük setleri ---
        "dist_load_sets_list": sets_list,
    }


def values_to_frame(frame, v: dict[str, Any]) -> None:
    frame.label = v.get("label", frame.label)
    frame.color = list(v.get("color", frame.color)) if frame.color else None
    frame.is_visible = bool(v.get("is_visible", frame.is_visible))
    frame.rotation_deg = float(v.get("rotation_deg", frame.rotation_deg))

    sec = v.get("section")
    if sec is not None and hasattr(sec, "name") and hasattr(sec, "profile_type"):
        frame.section = sec

    # Insertion
    frame.cardinal_pt = str(v.get("cardinal_pt", frame.cardinal_pt))
    frame.mirror2 = bool(v.get("mirror2", frame.mirror2))
    frame.mirror3 = bool(v.get("mirror3", frame.mirror3))
    frame.transform = bool(v.get("transform", frame.transform))
    frame.insertion_coord_sys = str(v.get("insertion_coord_sys", frame.insertion_coord_sys))
    ji = v.get("jt_offset_i")
    if isinstance(ji, (tuple, list)) and len(ji) == 3:
        frame.jt_offset_i = tuple(float(x) for x in ji)
    jj = v.get("jt_offset_j")
    if isinstance(jj, (tuple, list)) and len(jj) == 3:
        frame.jt_offset_j = tuple(float(x) for x in jj)

    # End Offset
    frame.offset_type = str(v.get("offset_type", frame.offset_type))
    frame.offset_length_i = float(v.get("offset_length_i", frame.offset_length_i))
    frame.offset_length_j = float(v.get("offset_length_j", frame.offset_length_j))
    frame.rigid_factor = float(v.get("rigid_factor", frame.rigid_factor))

    # Output Stations
    frame.station_type = str(v.get("station_type", frame.station_type))
    frame.min_num_sta = int(v.get("min_num_sta", frame.min_num_sta))
    frame.add_at_elm_int = bool(v.get("add_at_elm_int", frame.add_at_elm_int))
    frame.add_at_pt_load = bool(v.get("add_at_pt_load", frame.add_at_pt_load))
    if "max_sta_spcg" in v:
        val = v["max_sta_spcg"]
        frame.max_sta_spcg = float(val) if val is not None else None

    # Auto Mesh
    frame.auto_mesh = bool(v.get("auto_mesh", frame.auto_mesh))
    frame.mesh_at_joints = bool(v.get("mesh_at_joints", frame.mesh_at_joints))
    frame.mesh_at_frames = bool(v.get("mesh_at_frames", frame.mesh_at_frames))
    frame.mesh_num_segments = int(v.get("mesh_num_segments", frame.mesh_num_segments))
    frame.mesh_max_length = float(v.get("mesh_max_length", frame.mesh_max_length))
    frame.mesh_max_degrees = float(v.get("mesh_max_degrees", frame.mesh_max_degrees))

    # Local Axes
    frame.mirror_abt2 = bool(v.get("mirror_abt2", frame.mirror_abt2))
    frame.mirror_abt3 = bool(v.get("mirror_abt3", frame.mirror_abt3))

    # Design
    frame.design_proc = str(v.get("design_proc", frame.design_proc))
    frame.load_transfer = bool(v.get("load_transfer", frame.load_transfer))

    # Yük setleri
    sets_v = v.get("dist_load_sets_list")
    if isinstance(sets_v, list):
        new_sets: dict[str, FrameDistributedLoad] = {}
        for item in sets_v:
            if not isinstance(item, dict):
                continue
            pat = str(item.get("pattern_name", "")).strip()
            if not pat:
                continue
            segs = _text_to_segments(item.get("segments_text", ""))
            new_sets[pat] = FrameDistributedLoad(
                pattern_name=pat,
                coord_sys=str(item.get("coord_sys", "Local")),
                load_dir=str(item.get("load_dir", "7")),
                mode=str(item.get("mode", "REPLACE")),
                is_relative=bool(item.get("is_relative", True)),
                segments=segs,
            )
        frame.dist_load_sets = new_sets

    frame.mark_dirty()


# ============================================================================
# AREA
# ============================================================================
def area_to_values(area) -> dict[str, Any]:
    return {
        "label": area.label,
        "is_visible": area.is_visible,
        "color": list(area.color[:3]) if area.color else None,
        "thickness": float(area.thickness),
        "material": getattr(area, "material", None),
        "section_name": getattr(area, "section_name", ""),
    }


def values_to_area(area, v: dict[str, Any]) -> None:
    area.label = v.get("label", area.label)
    area.color = list(v.get("color", area.color)) if area.color else None
    area.is_visible = bool(v.get("is_visible", area.is_visible))
    area.thickness = float(v.get("thickness", area.thickness))

    mat = v.get("material")
    if mat is not None and hasattr(mat, "name"):
        area.material = mat

    sec_name = v.get("section_name")
    if isinstance(sec_name, str):
        area.section_name = sec_name

    area.mark_dirty()


# ============================================================================
# LINK
# ============================================================================
def link_to_values(link) -> dict[str, Any]:
    return {
        "label": link.label,
        "is_visible": link.is_visible,
        "color": list(link.color[:3]) if link.color else None,
        "propname": getattr(link, "propname", ""),
    }


def values_to_link(link, v: dict[str, Any]) -> None:
    link.label = v.get("label", link.label)
    link.color = list(v.get("color", link.color)) if link.color else None
    link.is_visible = bool(v.get("is_visible", link.is_visible))
    link.propname = v.get("propname", link.propname)
    link.mark_dirty()


# ============================================================================
# POLYGON
# ============================================================================
def polygon_to_values(poly) -> dict[str, Any]:
    pt = getattr(poly, "poly_type", None)
    loads = getattr(poly, "uniform_to_frame_loads", [])
    return {
        "label": poly.label,
        "is_visible": poly.is_visible,
        "is_temporary": getattr(poly, "is_temporary", False),
        "color": list(poly.color[:3]) if poly.color else None,
        "poly_type": pt.name if hasattr(pt, "name") else str(pt),
        "windplane": dict(getattr(poly, "windplane", {}) or {}),
        "associated_frame_ids": list(getattr(poly, "associated_frame_ids", [])),
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


def values_to_polygon(poly, v: dict[str, Any]) -> None:
    from domain.definition import AreaUniformToFrameLoad, DistType, LoadDirection

    poly.label = v.get("label", poly.label)
    poly.color = list(v.get("color", poly.color)) if poly.color else None
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

    wp = v.get("windplane")
    if isinstance(wp, dict):
        poly.windplane = wp

    loads_v = v.get("uniform_to_frame_loads")
    if isinstance(loads_v, list):
        new_loads = []
        for l_dict in loads_v:
            if not isinstance(l_dict, dict):
                continue
            dir_val = l_dict.get("direction", "GZ")
            direction = LoadDirection.GLOBAL_Z
            for d in LoadDirection:
                if d.value == str(dir_val) or d.name == str(dir_val):
                    direction = d
                    break
            dist_type = DistType.from_input(l_dict.get("dist_type", "One way"))
            new_loads.append(AreaUniformToFrameLoad(
                pattern_name=str(l_dict.get("pattern_name", "")),
                direction=direction,
                value=float(l_dict.get("value", 0.0)),
                dist_type=dist_type,
                coordinate_system=str(l_dict.get("coordinate_system", "GLOBAL")),
            ))
        poly.uniform_to_frame_loads = new_loads

    poly.mark_dirty()


# ============================================================================
# DISPATCH
# ============================================================================
_ADAPTERS = {
    "Node":    (node_to_values,    values_to_node),
    "Frame":   (frame_to_values,   values_to_frame),
    "Area":    (area_to_values,    values_to_area),
    "Link":    (link_to_values,    values_to_link),
    "Polygon": (polygon_to_values, values_to_polygon),
}


def element_to_values(element) -> dict[str, Any]:
    et = getattr(element, "element_type", None)
    pair = _ADAPTERS.get(et)
    if pair is None:
        return {
            "label": getattr(element, "label", ""),
            "is_visible": getattr(element, "is_visible", True),
            "color": list(getattr(element, "color", [0.7, 0.7, 0.7])[:3]),
        }
    return pair[0](element)


def values_to_element(element, v: dict[str, Any]) -> None:
    et = getattr(element, "element_type", None)
    pair = _ADAPTERS.get(et)
    if pair is None:
        return
    pair[1](element, v)


def elements_to_common_values(elements):
    if not elements:
        return {}
    if len(elements) == 1:
        return element_to_values(elements[0])

    dicts = [element_to_values(e) for e in elements]

    def collect_keys(d, prefix=""):
        keys = set()
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys |= collect_keys(v, full)
            else:
                keys.add(full)
        return keys

    all_keys = collect_keys(dicts[0])
    result = {}
    for key in all_keys:
        values = [get_path(d, key) for d in dicts]
        first = values[0]
        if all(v == first for v in values):
            set_path(result, key, first)
        else:
            set_path(result, key, MIXED)
    return result