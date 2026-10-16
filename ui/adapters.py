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
def _segments_to_text(segments) -> str:
    """Segment listesini 'x1,x2,q1,q2 | x1,x2,q1,q2' formatına çevir."""
    parts = []
    for s in segments:
        parts.append(f"{s.x1:.4f},{s.x2:.4f},{s.q1:.4f},{s.q2:.4f}")
    return " | ".join(parts)


def _text_to_segments(text: str):
    """Metni LoadSegment listesine çevir. Hatalı parçaları atlar."""
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
        # Sıralama ve sınır kontrolü
        x1 = max(0.0, min(1.0, x1))
        x2 = max(0.0, min(1.0, x2))
        if x2 <= x1:
            x2 = min(1.0, x1 + 0.001)
        segs.append(LoadSegment(x1=x1, x2=x2, q1=q1, q2=q2))
    segs.sort(key=lambda s: s.x1)
    return segs


def frame_to_values(frame) -> Dict[str, Any]:
    sec = getattr(frame, "section", None)
    sets = getattr(frame, "dist_load_sets", {}) or {}

    # Her set'i liste olarak dışa aktar (inspector list_object sever)
    sets_list = []
    for pat_name, s in sets.items():
        sets_list.append({
            "pattern_name":  s.pattern_name or pat_name,
            "coord_sys":     s.coord_sys,
            "load_dir":      str(s.load_dir),
            "mode":          s.mode,
            "is_relative":   bool(getattr(s, "is_relative", True)),
            "segments_text": _segments_to_text(s.segments),
        })

    # Eğer frame'in dist_loads'u var ama dist_load_sets'i yoksa,
    # dist_loads'tan reconstruct edip göster (read-only hissi)
    if not sets_list and getattr(frame, "dist_loads", None):
        from domain.definition import FrameDistributedLoadSet
        by_pattern: Dict[str, list] = {}
        for dl in frame.dist_loads:
            by_pattern.setdefault(dl.pattern_name, []).append(dl)
        for pat_name, dls in by_pattern.items():
            s = FrameDistributedLoadSet.from_sap_loads(dls)
            sets_list.append({
                "pattern_name":  s.pattern_name,
                "coord_sys":     s.coord_sys,
                "load_dir":      str(s.load_dir),
                "mode":          s.mode,
                "is_relative":   bool(getattr(s, "is_relative", True)),
                "segments_text": _segments_to_text(s.segments),
            })

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
        # Inspector için tek sanal alan
        "dist_load_sets_list": sets_list,
    }


def values_to_frame(frame, v: Dict[str, Any]):
    frame.label = v.get("label", frame.label)
    frame.color = list(v.get("color", frame.color))[:3]
    frame.is_visible = bool(v.get("is_visible", frame.is_visible))
    frame.rotation_deg = float(v.get("rotation_deg", frame.rotation_deg))

    # Kesit
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

    # --- Segment bazlı yük setleri ---
    sets_v = v.get("dist_load_sets_list")
    if isinstance(sets_v, list):
        from domain.definition import FrameDistributedLoadSet

        if not hasattr(frame, "dist_load_sets"):
            frame.dist_load_sets = {}

        # Yeni setleri oluştur
        new_sets: Dict[str, FrameDistributedLoadSet] = {}
        for item in sets_v:
            if not isinstance(item, dict):
                continue
            pat = str(item.get("pattern_name", "")).strip()
            if not pat:
                continue
            segs = _text_to_segments(item.get("segments_text", ""))

            s = FrameDistributedLoadSet(
                pattern_name=pat,
                coord_sys=str(item.get("coord_sys", "Local")),
                load_dir=str(item.get("load_dir", "7")),
                mode=str(item.get("mode", "REPLACE")),
                is_relative=bool(item.get("is_relative", True)),
                segments=segs,
            )
            new_sets[pat] = s

        frame.dist_load_sets = new_sets

        # dist_loads'u (SAP satırları) senkronize et
        if not hasattr(frame, "dist_loads"):
            frame.dist_loads = []
        # Tüm eski satırları temizle, setlerden yeniden üret
        frame.dist_loads = []
        for s in new_sets.values():
            frame.dist_loads.extend(s.to_sap_loads())

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