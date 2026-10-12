# ui/adapters.py
"""
Element ↔ dict dönüşümleri.

Ana uygulama bu modülü çağırır; ImGui tarafında sadece dict dolaşır.
"""
from typing import Any, Dict

from ui.schema import get_path, set_path


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
    return {
        "label": poly.label,
        "is_visible": poly.is_visible,
        "color": list(poly.color[:3]),
        "poly_type": pt.name if hasattr(pt, "name") else str(pt),
        "windplane": dict(getattr(poly, "windplane", {}) or {}),
    }


def values_to_polygon(poly, v: Dict[str, Any]):
    poly.label = v.get("label", poly.label)
    poly.color = list(v.get("color", poly.color))[:3]
    poly.is_visible = bool(v.get("is_visible", poly.is_visible))

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
    """
    Birden fazla element için ortak değerleri çıkar.
    Değerler farklıysa "[KARIŞIK]" döner.
    """
    if not elements:
        return {}
    if len(elements) == 1:
        return element_to_values(elements[0])

    # Her elementi dict'e çevir
    dicts = [element_to_values(e) for e in elements]

    # Ortak alanları topla (ilk elementin tüm anahtarları)
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

    # Her key için tüm değerleri kontrol et
    result = {}
    for key in all_keys:
        values = [get_path(d, key) for d in dicts]
        first = values[0]
        if all(v == first for v in values):
            set_path(result, key, first)
        else:
            # Tip uyumlu mu? Değilse string olarak KARIŞIK
            set_path(result, key, "[KARIŞIK]")
    return result