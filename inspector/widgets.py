# inspector/widgets.py
from __future__ import annotations

from enum import Enum
from typing import Any

from imgui_bundle import imgui

from domain.definition import AreaSection, LinkProp, Material, Restraint, Section
from domain.vertex import Vertex

_SKIP = frozenset({
    "element_type", "unique_id", "pick_id", "needs_update",
    "show_axes_override", "connected", "dof_indices", "loads",
    "is_selected", "source_node_id",
    "node_i", "node_j", "nodes", "dist_loads",
})

MIXED = "__MIXED__"

def inspector_fields(obj) -> list[tuple[str, Any]]:
    if obj is None:
        return []
    out = []
    for name in dir(obj):
        if name.startswith("_") or name in _SKIP:
            continue
        try:
            value = getattr(obj, name)
        except AttributeError:
            continue
        if callable(value):
            continue
        out.append((name, value))
    return out


class _Mixed:
    def __repr__(self):
        return "<MIXED>"


_MIXED = _Mixed()


def common_value(objects: list, key: str):
    if not objects:
        return _MIXED
    try:
        first = getattr(objects[0], key, _MIXED)
    except AttributeError:
        return _MIXED
    for o in objects[1:]:
        try:
            if getattr(o, key, _MIXED) != first:
                return _MIXED
        except AttributeError:
            return _MIXED
    return first


def set_value_all(objects: list, key: str, value):
    for o in objects:
        try:
            setattr(o, key, value)
        except AttributeError:
            pass


def is_mixed(v) -> bool:
    return v is _MIXED

def draw_field_row(objects: list, key: str, catalog) -> bool:
    value = common_value(objects, key)
    mixed = is_mixed(value)

    imgui.table_next_row()
    imgui.table_set_column_index(0)
    imgui.align_text_to_frame_padding()
    imgui.text(key)
    imgui.table_set_column_index(1)
    imgui.set_next_item_width(-1)
    imgui.push_id(key)
    try:
        if mixed:
            changed = _draw_mixed(objects, key, catalog)
        else:
            changed = _dispatch(objects, key, value, catalog)
    finally:
        imgui.pop_id()

    if changed:
        for o in objects:
            if hasattr(o, "mark_dirty"):
                o.mark_dirty()
    return changed


def _draw_mixed(objects, key, catalog) -> bool:
    sample = next((getattr(o, key, None) for o in objects if getattr(o, key, None) is not None), None)
    imgui.push_style_color(imgui.Col_.frame_bg, imgui.ImVec4(0.30, 0.25, 0.10, 1.0))
    imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(0.95, 0.85, 0.45, 1.0))
    changed = _dispatch(objects, key, sample, catalog, mixed=True)
    imgui.pop_style_color(2)
    return changed


def _dispatch(objects, key, value, catalog, mixed=False) -> bool:
    if key == "color":
        return _draw_color(objects, key, value)
    if value is None:
        if mixed:
            imgui.text_disabled("(karışık)")
            return False
        return _draw_string(objects, key, "")
    if isinstance(value, bool):
        return _draw_bool(objects, key, value, mixed)
    if isinstance(value, Enum):
        return _draw_enum(objects, key, value, mixed)
    if isinstance(value, Restraint):
        return _draw_restraint(objects, key, value)
    if isinstance(value, Vertex):
        return _draw_vertex(objects, key, value)
    if isinstance(value, Section):
        return _draw_section(objects, key, value, catalog, mixed)
    if isinstance(value, Material):
        return _draw_material(objects, key, value, catalog, mixed)
    if isinstance(value, AreaSection):
        return _draw_area_section(objects, key, value, catalog, mixed)
    if isinstance(value, LinkProp):
        return _draw_link_prop(objects, key, value, catalog, mixed)
    if isinstance(value, int):
        return _draw_int(objects, key, value, mixed)
    if isinstance(value, float):
        return _draw_float(objects, key, value, mixed)
    if isinstance(value, str):
        return _draw_string(objects, key, value, mixed)
    if isinstance(value, (list, tuple)):
        return _draw_list(objects, key, value)
    if isinstance(value, dict):
        imgui.text_disabled(f"({len(value)} key)")
        return False
    imgui.text_disabled(repr(value)[:80])
    return False


def _draw_bool(objects, key, value, mixed) -> bool:
    changed, new_v = imgui.checkbox("##v", bool(value))
    if changed:
        set_value_all(objects, key, bool(new_v))
        return True
    return False


def _draw_int(objects, key, value, mixed) -> bool:
    v = 0 if mixed else int(value)
    changed, new_v = imgui.input_int("##v", v)
    if changed:
        set_value_all(objects, key, int(new_v))
        return True
    return False


def _draw_float(objects, key, value, mixed) -> bool:
    v = 0.0 if mixed else float(value)
    changed, new_v = imgui.input_float("##v", v, format="%.4f")
    if changed:
        set_value_all(objects, key, float(new_v))
        return True
    return False


def _draw_string(objects, key, value, mixed=False) -> bool:
    v = "" if mixed else str(value or "")
    changed, new_v = imgui.input_text("##v", v)
    if changed:
        set_value_all(objects, key, str(new_v))
        return True
    return False


def _draw_enum(objects, key, value, mixed) -> bool:
    choices = list(type(value))
    names = [c.name for c in choices]
    idx = 0
    if not mixed:
        try:
            idx = names.index(value.name)
        except ValueError:
            idx = 0
    changed, new_idx = imgui.combo("##v", idx, names)
    if changed and 0 <= new_idx < len(choices):
        set_value_all(objects, key, choices[new_idx])
        return True
    return False


def _draw_restraint(objects, key, value: Restraint) -> bool:
    changed = False
    for dof in ("ux", "uy", "uz", "rx", "ry", "rz"):
        imgui.push_id(dof)
        cur = bool(getattr(value, dof, False)) if value else False
        c, v = imgui.checkbox(dof.upper(), cur)
        if c:
            for o in objects:
                r = getattr(o, key, None)
                if r is not None:
                    setattr(r, dof, bool(v))
            changed = True
        imgui.pop_id()
        if dof != "rz":
            imgui.same_line()
    return changed


def _draw_vertex(objects, key, value: Vertex) -> bool:
    changed = False
    width = (imgui.get_content_region_avail().x - 8) / 3.0
    imgui.push_item_width(width)
    for axis in ("x", "y", "z"):
        imgui.push_id(axis)
        cur = float(getattr(value, axis, 0.0)) if value else 0.0
        c, v = imgui.input_float(f"##{axis}", cur, format="%.3f")
        if c:
            for o in objects:
                vx = getattr(o, key, None)
                if vx is not None:
                    setattr(vx, axis, float(v))
            changed = True
        imgui.pop_id()
        if axis != "z":
            imgui.same_line()
    imgui.pop_item_width()
    return changed


def _draw_color(objects, key, value) -> bool:
    rgb = list(value[:3]) if value and len(value) >= 3 else [0.5, 0.5, 0.5]
    changed, new_rgb = imgui.color_edit3("##v", [float(c) for c in rgb])
    if not changed:
        return False
    for o in objects:
        cur = getattr(o, key, None)
        if isinstance(cur, tuple) and len(cur) == 3:
            setattr(o, key, tuple(new_rgb))
        else:
            alpha = cur[3] if cur and len(cur) > 3 else 1.0
            setattr(o, key, [*new_rgb, alpha])
    return True


def _draw_section(objects, key, value, catalog) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_sections()
    if not names:
        imgui.text_disabled("(section yok)")
        return False
    cur = getattr(value, "name", "") if value else ""
    try:
        idx = names.index(cur)
    except ValueError:
        idx = 0
    changed, new_idx = imgui.combo("##v", idx, names)
    if changed and 0 <= new_idx < len(names):
        sec = catalog.get_section(names[new_idx])
        set_value_all(objects, key, sec)
        return True
    return False


def _draw_material(objects, key, value, catalog) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_materials()
    if not names:
        imgui.text_disabled("(material yok)")
        return False
    cur = getattr(value, "name", "") if value else ""
    try:
        idx = names.index(cur)
    except ValueError:
        idx = 0
    changed, new_idx = imgui.combo("##v", idx, names)
    if changed and 0 <= new_idx < len(names):
        set_value_all(objects, key, catalog.get_material(names[new_idx]))
        return True
    return False


def _draw_link_prop(objects, key, value, catalog) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_link_props()
    if not names:
        imgui.text_disabled("(link prop yok)")
        return False
    cur = getattr(value, "name", "") if value else ""
    try:
        idx = names.index(cur)
    except ValueError:
        idx = 0
    changed, new_idx = imgui.combo("##v", idx, names)
    if changed and 0 <= new_idx < len(names):
        set_value_all(objects, key, catalog.get_link_prop(names[new_idx]))
        return True
    return False


def _draw_list(objects, key, value) -> bool:
    imgui.text_disabled(f"({len(value)})")
    for item in list(value)[:30]:
        imgui.bullet_text(str(item))
    if len(value) > 30:
        imgui.text_disabled(f"...ve {len(value) - 30} tane daha")
    return False

def _combo_catalog_items(names: list[str], cur: str, mixed: bool) -> tuple[bool, str | None]:
    items = list(names)
    if mixed:
        items.insert(0, "<Karışık>")
        idx = 0
    else:
        if cur and cur not in items:
            items.insert(0, cur)
        idx = items.index(cur) if cur in items else -1
    if not items:
        return False, None
    changed, new_idx = imgui.combo("##v", idx, items)
    if not changed or not (0 <= new_idx < len(items)):
        return False, None
    picked = items[new_idx]
    if mixed and picked == "<Karışık>":
        return False, None
    return True, picked


def _draw_section(objects, key, value, catalog, mixed=False) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_sections()
    cur = "" if mixed else (getattr(value, "name", "") if value else "")
    changed, picked = _combo_catalog_items(names, cur, mixed)
    if changed and picked is not None:
        sec = catalog.get_section(picked)
        if sec is not None:
            set_value_all(objects, key, sec)
            return True
    return False


def _draw_material(objects, key, value, catalog, mixed=False) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_materials()
    cur = "" if mixed else (getattr(value, "name", "") if value else "")
    changed, picked = _combo_catalog_items(names, cur, mixed)
    if changed and picked is not None:
        mat = catalog.get_material(picked)
        if mat is not None:
            set_value_all(objects, key, mat)
            return True
    return False


def _draw_area_section(objects, key, value, catalog, mixed=False) -> bool:
    if catalog is None or not hasattr(catalog, "list_area_sections"):
        imgui.text_disabled("<Karışık>" if mixed else (getattr(value, "name", "?") or "—"))
        return False
    names = catalog.list_area_sections()
    cur = "" if mixed else (getattr(value, "name", "") if value else "")
    changed, picked = _combo_catalog_items(names, cur, mixed)
    if changed and picked is not None:
        sec = catalog.get_area_section(picked)
        if sec is not None:
            set_value_all(objects, key, sec)
            set_value_all(objects, "section_name", picked)
            return True
    return False


def _draw_link_prop(objects, key, value, catalog, mixed=False) -> bool:
    if catalog is None:
        imgui.text_disabled("(catalog yok)")
        return False
    names = catalog.list_link_props()
    cur = "" if mixed else (getattr(value, "name", "") if value else "")
    changed, picked = _combo_catalog_items(names, cur, mixed)
    if changed and picked is not None:
        lp = catalog.get_link_prop(picked)
        if lp is not None:
            set_value_all(objects, key, lp)
            return True
    return False

def _scene_groups(scene, math_model=None):
    out = [("Node", _collect(math_model, "Node"))]
    out.append(("Frame", _collect(math_model, "Frame")))
    out.append(("Area", _collect(math_model, "Area")))
    out.append(("Link", _collect(math_model, "Link")))
    out.append((
        "Polygon",
        _collect(math_model, "Polygon"),
    ))
    out.append((
        "Line",
        _collect(math_model, "Line"),
    ))
    return out

def _collect(scene, type_name):
    attr_map = {
        "Node": "nodes", "Frame": "frames",
        "Area": "areas", "Polygon": "polygons", "Line": "lines",
    }
    attr = attr_map.get(type_name)
    if attr and hasattr(scene, attr):
        seq = getattr(scene, attr) or []
        if isinstance(seq, dict):
            return list(seq.values())
        if isinstance(seq, (list, tuple, set)):
            return list(seq)
        try:
            return list(seq)
        except TypeError:
            pass

    if hasattr(scene, "iter_elements"):
        try:
            return list(scene.iter_elements(type=type_name))
        except (TypeError, AttributeError):
            pass

    if hasattr(scene, "all_elements"):
        elems = scene.all_elements
        if isinstance(elems, dict):
            elems = elems.values()
        return [e for e in elems
                if getattr(e, "element_type", type(e).__name__) == type_name]

    return []


def _element_label(el) -> str:
    if el is None:
        return "?"
    v = getattr(el, "label", None)
    if v not in (None, ""):
        return str(v)
    v = getattr(el, "name", None)
    if v not in (None, ""):
        return str(v)
    uid = _unique_id(el)
    t = getattr(el, "element_type", type(el).__name__)
    if uid is not None:
        return f"{t}_{uid}"
    return f"{t}@{hex(id(el) & 0xFFFF)}"


def _parse_filter(flt: str):
    type_hint = None
    id_hint = None
    text = flt

    if ":" in text:
        head, tail = text.split(":", 1)
        if head in ("node", "frame", "area", "polygon"):
            type_hint = head
            text = tail.strip()

    if text.startswith("#"):
        try:
            id_hint = int(text[1:])
            text = ""
        except ValueError:
            pass

    return type_hint, id_hint, text.strip()


def _matches(el, type_name: str, text_hint: str, id_hint) -> bool:
    if id_hint is not None:
        return _unique_id(el) == id_hint
    if not text_hint:
        return True
    label = _element_label(el).lower()
    if text_hint in label:
        return True
    return text_hint in str(_unique_id(el)).lower()


def _unique_id(el):
    if el is None:
        return None
    v = getattr(el, "unique_id", None)
    if v is not None:
        return v
    for attr in ("uid", "eid"):
        v = getattr(el, attr, None)
        if v is not None:
            return v
    return None


def _copy_to_clipboard(text: str):
    try:
        imgui.set_clipboard_text(text)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Yardımcı: ImVec4 / renkli metin
# ----------------------------------------------------------------------
def _col(r, g, b, a=1.0) -> imgui.ImVec4:
    return imgui.ImVec4(float(r), float(g), float(b), float(a))


def _domain_field_items(element) -> list[tuple[str, Any]]:
    """Return all stored domain fields, including fields added by future models."""
    try:
        return list(vars(element).items())
    except TypeError:
        return []

def draw_schema_field(controller, field, catalog) -> bool:
    """Şemadaki tek bir alanı draft üzerinden render eder."""
    from inspector.adapters import MIXED
    from inspector.schemas import get_path

    key = field.key
    value = get_path(controller.draft_values(), key)
    mixed = value is MIXED

    imgui.table_next_row()
    imgui.table_set_column_index(0)
    imgui.align_text_to_frame_padding()
    label = field.label or key
    if field.unit:
        label = f"{label} {field.unit}"
    imgui.text(label)

    imgui.table_set_column_index(1)
    imgui.set_next_item_width(-1)
    imgui.push_id(key)
    try:
        changed, new_value = _dispatch_schema(controller, field, value,
                                              mixed, catalog)
    finally:
        imgui.pop_id()

    if changed:
        controller.set_draft_value(key, new_value)
        return True
    return False


def _dispatch_schema(controller, field, value, mixed, catalog):
    kind = field.kind

    if kind == "bool":
        v = False if mixed else bool(value)
        c, nv = imgui.checkbox("##v", v)
        return c, bool(nv)

    if kind == "int":
        v = 0 if mixed else int(value or 0)
        c, nv = imgui.input_int("##v", v)
        return c, int(nv)

    if kind == "float":
        v = 0.0 if mixed else float(value or 0.0)
        c, nv = imgui.input_float("##v", v, step=field.step,
                                   format=field.format)
        return c, float(nv)

    if kind == "str":
        v = "" if mixed else str(value or "")
        c, nv = imgui.input_text("##v", v)
        return c, str(nv)

    if kind == "color":
        rgb = list(value[:3]) if (value and len(value) >= 3) else [0.5]*3
        c, nv = imgui.color_edit3("##v", [float(x) for x in rgb])
        if not c:
            return False, None
        # orijinal alpha koru
        old = controller.draft_values().get("color")
        alpha = old[3] if old and len(old) > 3 else 1.0
        return True, [*nv, alpha]

    if kind == "enum":
        choices = list(field.choices or [])
        cur = "" if mixed else (str(value) if value is not None else "")
        c, picked = _combo_catalog_items(choices, cur, mixed)
        if c and picked is not None:
            return True, picked
        return False, None

    if kind == "info":
        imgui.text_disabled("<Karışık>" if mixed else (str(value) if value is not None else "—"))
        return False, None

    if kind == "section_ref":
        if catalog is None:
            imgui.text_disabled("(catalog yok)")
            return False, None
        names = catalog.list_sections()
        cur = "" if mixed else (getattr(value, "name", "") if value else "")
        c, picked = _combo_catalog_items(names, cur, mixed)
        if c and picked is not None:
            sec = catalog.get_section(picked)
            if sec is not None:
                return True, sec
        return False, None

    if kind == "material_ref":
        if catalog is None:
            imgui.text_disabled("(catalog yok)")
            return False, None
        names = catalog.list_materials()
        cur = "" if mixed else (getattr(value, "name", "") if value else "")
        c, picked = _combo_catalog_items(names, cur, mixed)
        if c and picked is not None:
            mat = catalog.get_material(picked)
            if mat is not None:
                return True, mat
        return False, None

    if kind == "link_prop_ref":
        if catalog is None:
            imgui.text_disabled("(catalog yok)")
            return False, None
        names = catalog.list_link_props()
        cur = "" if mixed else (getattr(value, "name", "") if value else "")
        c, picked = _combo_catalog_items(names, cur, mixed)
        if c and picked is not None:
            lp = catalog.get_link_prop(picked)
            if lp is not None:
                return True, lp
        return False, None

    if kind == "string_select":
        if catalog is not None and field.key == "section_name" and hasattr(catalog, "list_area_sections"):
            names = catalog.list_area_sections()
            cur = "" if mixed else str(value or "")
            c, picked = _combo_catalog_items(names, cur, mixed)
            if c and picked is not None:
                return True, picked
            return False, None
        v = "" if mixed else str(value or "")
        c, nv = imgui.input_text("##v", v)
        return c, str(nv)

    if kind == "list_object":
        return _draw_list_object(controller, field, value, mixed, catalog)

    if kind == "list":
        items = value if isinstance(value, (list, tuple)) else []
        imgui.text_disabled(f"({len(items)})")
        for it in list(items)[:30]:
            imgui.bullet_text(str(it))
        return False, None

    imgui.text_disabled(repr(value)[:80] if value is not None else "—")
    return False, None


def _draw_list_object(controller, field, value, mixed, catalog):
    """Frame.dist_load_sets_list gibi item_schema'lı listeler."""
    items = list(value) if isinstance(value, list) else []
    changed = False
    new_items = [dict(it) if isinstance(it, dict) else it for it in items]

    if imgui.button(f"+ {field.label or field.key}"):
        new_items.append(_blank_item(field))
        changed = True
    imgui.same_line()
    imgui.text_disabled(f"({len(new_items)})")

    item_schema = field.item_schema or []
    for i, it in enumerate(new_items):
        imgui.push_id(f"{field.key}_{i}")
        try:
            header = f"{i}: {it.get('pattern_name', '?')}##item"
            open_ = imgui.collapsing_header(header)
            if open_:
                imgui.indent(12)
                for sub in item_schema:
                    sub_val = it.get(sub.key)
                    sub_changed, sub_new = _dispatch_schema(
                        controller, sub, sub_val, False, catalog,
                    )
                    if sub_changed:
                        it[sub.key] = sub_new
                        changed = True
                imgui.unindent(12)
            if imgui.button(f"Sil##{i}"):
                new_items.pop(i)
                changed = True
                break
        finally:
            imgui.pop_id()

    return changed, new_items if changed else None


def _blank_item(field):
    item = {}
    for sub in (field.item_schema or []):
        if sub.kind == "bool":
            item[sub.key] = False
        elif sub.kind in ("int",):
            item[sub.key] = 0
        elif sub.kind in ("float",):
            item[sub.key] = 0.0
        elif sub.kind == "enum" and sub.choices:
            item[sub.key] = sub.choices[0]
        else:
            item[sub.key] = ""
    return item