# inspector/controller.py
from __future__ import annotations
from typing import Any

from inspector.adapters import (
    MIXED, element_to_values, elements_to_common_values, values_to_element,
)
from inspector.schemas import schema_for_object, multi_schema_for, set_path


class InspectorController:

    def __init__(self, scene=None, catalog=None, on_applied=None):
        self.scene = scene
        self.catalog = catalog
        self.objects: list = []
        self.filter_type: str | None = None
        self._original: dict[int, dict] = {}   # uid -> orijinal values
        self._draft:    dict[int, dict] = {}   # uid -> düzenlenen values
        self.on_applied = on_applied

    @property
    def type_counts(self) -> dict[str, int]:
        counts = {}
        for o in self.objects:
            t = type(o).__name__
            counts[t] = counts.get(t, 0) + 1
        return counts

    @property
    def active_objects(self) -> list:
        if self.filter_type is None:
            return []
        return [o for o in self.objects if type(o).__name__ == self.filter_type]

    @property
    def common_type(self):
        act = self.active_objects
        if not act:
            return None
        t = type(act[0]).__name__
        return t if all(type(o).__name__ == t for o in act) else None

    def set_selection(self, elements):
        self.objects = list(elements or [])
        counts = self.type_counts
        if len(counts) == 1:
            self.filter_type = next(iter(counts))
        elif self.filter_type not in counts:
            self.filter_type = None
        self.load_values()

    def set_filter_type(self, t: str | None):
        self.filter_type = t

    def clear(self):
        self.objects = []
        self.filter_type = None

    def refresh_from_scene(self):
        pass

    # --- Şema ---
    def schema(self):
        act = self.active_objects
        if not act:
            return []
        if len(act) == 1:
            return schema_for_object(act[0])
        return multi_schema_for(act)

    # --- Draft / Commit ---
    def load_values(self):
        self._original.clear()
        self._draft.clear()
        for o in self.objects:
            uid = getattr(o, "unique_id", id(o))
            vals = element_to_values(o, analysis_data=getattr(o, "analysis_data", None))
            self._original[uid] = vals
            self._draft[uid] = _deep_copy(vals)

    def draft_values(self) -> dict:
        """Aktif objeler için ortak değerler (MIXED olabilir)."""
        act = self.active_objects
        if not act:
            return {}
        if len(act) == 1:
            uid = getattr(act[0], "unique_id", id(act[0]))
            return self._draft.get(uid, {})
        drafts = [
            self._draft.get(getattr(o, "unique_id", id(o)), {})
            for o in act
        ]
        return _common_of(drafts)

    def set_draft_value(self, key: str, value: Any) -> None:
        for obj in self.active_objects:
            uid = getattr(obj, "unique_id", id(obj))
            draft = self._draft.get(uid)

            if draft is None:
                continue

            set_path(draft, key, value)

            if key == "section_name" and self._catalog is not None:
                sec = self._catalog.get_area_section(str(value or ""))

                if sec is not None:
                    mat = getattr(sec, "material", None)
                    draft["area_section"] = (
                        f"{sec.name} ({sec.area_type}, t={sec.thickness:g})"
                    )
                    draft["material_info"] = (
                        getattr(mat, "name", "—") if mat is not None else "—"
                    )

                    if draft.get("thick_over") is None:
                        draft["thickness"] = float(sec.thickness)
                else:
                    draft["area_section"] = (
                        f"{value} (tanımsız)" if value else "—"
                    )
                    draft["material_info"] = "—"

        self._dirty = True

    def is_dirty(self) -> bool:
        for o in self.active_objects:
            uid = getattr(o, "unique_id", id(o))
            if self._draft.get(uid) != self._original.get(uid):
                return True
        return False

    def apply(self) -> bool:
        changed = False
        touched_node_uids: list[int] = []

        for o in self.active_objects:
            uid = getattr(o, "unique_id", id(o))
            if self._original.get(uid) == self._draft.get(uid):
                continue
            values_to_element(o, self._draft[uid],
                              analysis_data=getattr(o, "analysis_data", None))
            self._original[uid] = _deep_copy(self._draft[uid])
            changed = True
            if type(o).__name__ == "Node":
                touched_node_uids.append(uid)

        if not changed:
            return False

        if touched_node_uids and self.scene is not None:
            for uid in touched_node_uids:
                node = self.scene.get_element_by_unique_id(uid)
                for _obj_type, conn_uid in getattr(node, "connected", []):
                    conn_el = self.scene.get_element_by_unique_id(conn_uid)
                    if conn_el is not None:
                        conn_el.mark_dirty()

        if self.scene is not None:
            if hasattr(self.scene, "mark_dirty"):
                self.scene.mark_dirty()
            if hasattr(self.scene, "refresh_bounds"):
                self.scene.refresh_bounds()

        if callable(self.on_applied):
            self.on_applied({"node_uids": touched_node_uids})

        return True

    def cancel(self):
        # draft'ı orijinalden geri yükle
        for uid, vals in self._original.items():
            self._draft[uid] = _deep_copy(vals)

    def mark_dirty(self):
        for o in self.active_objects:
            mark = getattr(o, "mark_dirty", None)
            if callable(mark):
                mark()

def _deep_copy(v):
    import copy
    try:
        return copy.deepcopy(v)
    except Exception:
        return dict(v) if isinstance(v, dict) else v


def _diff(a, b, prefix=""):
    """Nested dict için fark anahtarları (adapter'ı tüm values ile beslemek yeterli)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = {}
        for k in set(a) | set(b):
            d = _diff(a.get(k), b.get(k), f"{prefix}.{k}" if prefix else k)
            if d is not None:
                out[k] = d
        return out if out else None
    return None if a == b else b


def _common_of(dicts):
    from inspector.adapters import MIXED
    from inspector.schemas import get_path, set_path
    if not dicts:
        return {}
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
        vals = [get_path(d, key) for d in dicts]
        first = vals[0]
        set_path(result, key,
                 first if all(v == first for v in vals) else MIXED)
    return result