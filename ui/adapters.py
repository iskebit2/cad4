# ui/adapters.py
"""
Element ↔ dict dönüşümleri.

Ana uygulama bu modülü çağırır; ImGui tarafında sadece dict dolaşır.
"""
from typing import Any, Dict

from ui.schema import get_path, set_path

MIXED = "__MIXED__"   # çakışmayacak bir string (nadir)

# ------------------------------------------------------------------
# NODE
# ------------------------------------------------------------------
def node_to_values(node) -> Dict[str, Any]:
    return {
        "label": node.label,
        "is_visible": node.is_visible,
        "color": list(node.color[:3]),
        "x": float(node.x), "y": float(node.y), "z": float(node.z),
        "restraint": (node.restraint.as_dict()
                      if node.restraint else
                      {"ux": False, "uy": False, "uz": False,
                       "rx": False, "ry": False, "rz": False}),
        "mass": list(node.mass) if node.mass else [0.0] * 6,
    }


def values_to_node(node, v: Dict[str, Any]):
    node.label = v.get("label", node.label)
    node.color = list(v.get("color", node.color))[:3]
    node.is_visible = bool(v.get("is_visible", node.is_visible))
    node.x = float(v.get("x", node.x))
    node.y = float(v.get("y", node.y))
    node.z = float(v.get("z", node.z))

    r = v.get("restraint", {})
    if r:
        from domain.definition import Restraint
        if node.restraint is None:
            node.restraint = Restraint()
        for k in ("ux", "uy", "uz", "rx", "ry", "rz"):
            if k in r:
                setattr(node.restraint, k, bool(r[k]))

    m = v.get("mass")
    if isinstance(m, list) and len(m) == 6:
        node.mass = tuple(float(x) for x in m)

    node.mark_dirty()


# ------------------------------------------------------------------
# FRAME
# ------------------------------------------------------------------
def frame_to_values(frame) -> Dict[str, Any]:
    sec = getattr(frame, "section", None)
    loads = getattr(frame, "dist_loads", [])
    return {
        "label": frame.label,
        "is_visible": frame.is_visible,
        "color": list(frame.color[:3]),
        "rotation_deg": float(getattr(frame, "rotation_deg", 0.0)),
        "section": {
            "name": getattr(sec, "name", "") if sec else "",
            "profile_type": (sec.profile_type.name
                             if sec and hasattr(sec, "profile_type")
                             else ""),
            "profile_params": dict(getattr(sec, "profile_params", {})
                                   if sec else {}),
        },
        "dist_loads": [
            {
                "pattern_name": l.pattern_name,
                "force_or_moment": getattr(l, "force_or_moment", "Force"),
                "direction": l.direction.value if hasattr(l.direction, "value") else str(l.direction),
                "p1": float(l.p1),
                "p2": float(l.p2),
                "coordinate_system": getattr(l, "coordinate_system", "GLOBAL"),
            }
            for l in loads
        ],
    }


def values_to_frame(frame, v: Dict[str, Any]):
    frame.label = v.get("label", frame.label)
    frame.color = list(v.get("color", frame.color))[:3]
    frame.is_visible = bool(v.get("is_visible", frame.is_visible))
    frame.rotation_deg = float(v.get("rotation_deg", frame.rotation_deg))

    sec_v = v.get("section", {})
    if frame.section is not None:
        pt = sec_v.get("profile_type")
        if pt:
            from domain.definition import SectionType
            try:
                frame.section.profile_type = SectionType[pt]
            except KeyError:
                pass
        for k, val in sec_v.get("profile_params", {}).items():
            try:
                frame.section.profile_params[k] = float(val)
            except (ValueError, TypeError):
                pass

    # Dağıtılmış yükleri (dist_loads) güncelle
    loads_v = v.get("dist_loads")
    if isinstance(loads_v, list):
        from domain.definition import FrameDistributedLoad, LoadDirection
        new_loads = []
        for l_dict in loads_v:
            if isinstance(l_dict, dict):
                dir_val = l_dict.get("direction", "GZ")
                direction = LoadDirection.GLOBAL_Z
                for d in LoadDirection:
                    if d.value == str(dir_val) or d.name == str(dir_val):
                        direction = d
                        break

                load_obj = FrameDistributedLoad(
                    pattern_name=str(l_dict.get("pattern_name", "")),
                    force_or_moment=str(l_dict.get("force_or_moment", "Force")),
                    direction=direction,
                    p1=float(l_dict.get("p1", 0.0)),
                    p2=float(l_dict.get("p2", 0.0)),
                    d1=0.0,
                    d2=1.0,
                    is_relative=True,
                    coordinate_system=str(l_dict.get("coordinate_system", "GLOBAL"))
                )
                new_loads.append(load_obj)
        frame.dist_loads = new_loads

    frame.mark_dirty()


# ------------------------------------------------------------------
# AREA
# ------------------------------------------------------------------
def area_to_values(area) -> Dict[str, Any]:
    return {
        "label": area.label,
        "is_visible": area.is_visible,
        "color": list(area.color[:3]),
        "thickness": float(area.thickness),
        "section_name": getattr(area, "section_name", ""),
    }


def values_to_area(area, v: Dict[str, Any]):
    area.label = v.get("label", area.label)
    area.color = list(v.get("color", area.color))[:3]
    area.is_visible = bool(v.get("is_visible", area.is_visible))
    area.thickness = float(v.get("thickness", area.thickness))
    area.section_name = v.get("section_name", area.section_name)
    area.mark_dirty()


# ------------------------------------------------------------------
# LINK
# ------------------------------------------------------------------
def link_to_values(link) -> Dict[str, Any]:
    return {
        "label": link.label,
        "is_visible": link.is_visible,
        "color": list(link.color[:3]),
        "propname": getattr(link, "propname", ""),
    }


def values_to_link(link, v: Dict[str, Any]):
    link.label = v.get("label", link.label)
    link.color = list(v.get("color", link.color))[:3]
    link.is_visible = bool(v.get("is_visible", link.is_visible))
    link.propname = v.get("propname", link.propname)
    link.mark_dirty()


# ------------------------------------------------------------------
# POLYGON
# ------------------------------------------------------------------
def polygon_to_values(poly) -> Dict[str, Any]:
    pt = getattr(poly, "poly_type", None)
    loads = getattr(poly, "uniform_to_frame_loads", [])
    return {
        "label": poly.label,
        "is_visible": poly.is_visible,
        "is_temporary": getattr(poly, "is_temporary", False),
        "color": list(poly.color[:3]),
        "poly_type": pt.name if hasattr(pt, "name") else str(pt),
        "windplane": dict(getattr(poly, "windplane", {}) or {}),
        "uniform_to_frame_loads": [
            {
                "pattern_name": l.pattern_name,
                "value": float(l.value),
                # Enum'ın string value'sunu alıyoruz (Örn: "GRAV", "GZ" vb.)
                "direction": l.direction.value if hasattr(l.direction, "value") else str(l.direction),
                "dist_type": l.dist_type.value if hasattr(l.dist_type, "value") else str(l.dist_type),
                "coordinate_system": getattr(l, "coordinate_system", "GLOBAL"),
            }
            for l in loads
        ],
    }


def values_to_polygon(poly, v: Dict[str, Any]):
    poly.label = v.get("label", poly.label)
    poly.color = list(v.get("color", poly.color))[:3]
    poly.is_visible = bool(v.get("is_visible", poly.is_visible))
    poly.is_temporary = bool(v.get("is_temporary", getattr(poly, "is_temporary", False)))

    pt = v.get("poly_type")
    if pt:
        from domain.element import PolygonType
        try:
            poly.poly_type = PolygonType[pt]
        except KeyError:
            pass

    wp = v.get("windplane")
    if isinstance(wp, dict):
        poly.windplane = wp

    # Yükleri güncelle
    loads_v = v.get("uniform_to_frame_loads")
    if isinstance(loads_v, list):
        from domain.definition import AreaUniformToFrameLoad, LoadDirection, DistType
        new_loads = []
        for l_dict in loads_v:
            if isinstance(l_dict, dict):
                dir_val = l_dict.get("direction", "GZ")
                
                # Gelen string değere (örn. "GRAV", "GX") göre doğru LoadDirection'ı bul
                direction = LoadDirection.GLOBAL_Z  # varsayılan
                for d in LoadDirection:
                    if d.value == str(dir_val) or d.name == str(dir_val):
                        direction = d
                        break

                # DistType parse
                dist_raw = l_dict.get("dist_type", "One way")
                dist_type = DistType.from_input(dist_raw)

                load_obj = AreaUniformToFrameLoad(
                    pattern_name=str(l_dict.get("pattern_name", "")),
                    direction=direction,
                    value=float(l_dict.get("value", 0.0)),
                    dist_type=dist_type,
                    coordinate_system=str(l_dict.get("coordinate_system", "GLOBAL"))
                )
                new_loads.append(load_obj)
        poly.uniform_to_frame_loads = new_loads

    poly.mark_dirty()


# ------------------------------------------------------------------
# DISPATCH
# ------------------------------------------------------------------
_ADAPTERS = {
    "Node":    (node_to_values,    values_to_node),
    "Frame":   (frame_to_values,   values_to_frame),
    "Area":    (area_to_values,    values_to_area),
    "Link":    (link_to_values,    values_to_link),
    "Polygon": (polygon_to_values, values_to_polygon),
}


def element_to_values(element) -> Dict[str, Any]:
    et = getattr(element, "element_type", None)
    pair = _ADAPTERS.get(et)
    if pair is None:
        # bilinmeyen tip → minimum ortak alanlar
        return {
            "label": getattr(element, "label", ""),
            "is_visible": getattr(element, "is_visible", True),
            "color": list(getattr(element, "color", [0.7, 0.7, 0.7])[:3]),
        }
    return pair[0](element)


def values_to_element(element, v: Dict[str, Any]):
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
            set_path(result, key, MIXED)   # ← string sentinel
    return result