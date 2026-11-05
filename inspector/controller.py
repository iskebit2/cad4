# inspector/controller.py
from __future__ import annotations


class InspectorController:

    def __init__(self, scene=None, catalog=None):
        self.scene = scene
        self.catalog = catalog
        self.objects: list = []
        self.filter_type: str | None = None

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

    def set_filter_type(self, t: str | None):
        self.filter_type = t

    def clear(self):
        self.objects = []
        self.filter_type = None

    def refresh_from_scene(self):
        pass

    def apply(self) -> bool:
        act = self.active_objects
        if not act:
            return False
        for o in act:
            mark = getattr(o, "mark_dirty", None)
            if callable(mark):
                mark()
        if self.scene is not None:
            self.scene.mark_dirty()
        return True

    def cancel(self):
        pass