# core/selection_manager.py
from core.commands import CommandManager, DeleteElementsCommand
from core.selection_policy import SelectionMode


class SelectionManager:

    def __init__(self, scene_renderer):
        self.r = scene_renderer
        self.selected: set[int] = set()
        self.cmd_mgr = CommandManager(max_history=100)
        self.on_selection_changed = None

    def _update(self):
        if self.r:
            self.r.update_sel()
        if self.on_selection_changed:
            self.on_selection_changed(list(self.get_selected()))

    def _update_geometry_renderers(self, scene):
        if self.r:
            self.r.update_geo(scene)

    def _deselect_all(self):
        for e in self.get_selected():
            e.is_selected = False
        self.selected.clear()

    def select(self, element, additive=False):
        if not element:
            return
        eid = getattr(element, "unique_id", id(element))

        if not additive:
            for e in self.get_selected():
                if getattr(e, "unique_id", id(e)) != eid:
                    e.is_selected = False
            self.selected.clear()
            self.selected.add(eid)
            element.is_selected = True
        else:
            if eid in self.selected:
                self.selected.remove(eid)
                element.is_selected = False
            else:
                self.selected.add(eid)
                element.is_selected = True
        self._update()

    def select_multiple(self, elements: list, mode=SelectionMode.REPLACE):
        if mode == SelectionMode.REPLACE:
            self._deselect_all()
            for e in elements:
                self.selected.add(getattr(e, "unique_id", id(e)))
                e.is_selected = True
        elif mode == SelectionMode.ADD:
            for e in elements:
                eid = getattr(e, "unique_id", id(e))
                if eid not in self.selected:
                    self.selected.add(eid)
                    e.is_selected = True
        elif mode == SelectionMode.TOGGLE:
            for e in elements:
                eid = getattr(e, "unique_id", id(e))
                if eid in self.selected:
                    self.selected.discard(eid)
                    e.is_selected = False
                else:
                    self.selected.add(eid)
                    e.is_selected = True
        self._update()

    def select_only(self, element):
        if element is None:
            self.clear()
            return
        self.select(element, additive=False)

    def clear(self):
        for e in self.get_selected():
            e.is_selected = False
        self.selected.clear()
        if self.on_selection_changed:
            self.on_selection_changed([])
        if self.r:
            self.r.update_sel()

    def get_selected(self):
        out = []
        if self.r and self.r.scene:
            out.extend(
                e for e in self.r.scene.all_elements.values()
                if e.unique_id in self.selected
            )
            project = getattr(self.r.scene, "project", None)
            if project:
                out.extend(
                    p for p in getattr(project, "polygons", {}).values()
                    if p.unique_id in self.selected
                )
                out.extend(
                    ln for ln in getattr(project, "lines", {}).values()
                    if ln.unique_id in self.selected
                )
        return out

    def find_element_by_id(self, unique_id: int):
        if not self.r or not self.r.scene:
            return None
        if unique_id in self.r.scene.all_elements:
            return self.r.scene.all_elements[unique_id]
        project = getattr(self.r.scene, "project", None)
        if project:
            polys = getattr(project, "polygons", {})
            if unique_id in polys:
                return polys[unique_id]
            lines = getattr(project, "lines", {})
            if unique_id in lines:
                return lines[unique_id]
        return None

    def count(self):
        return len(self.selected)

    def is_selected(self, e):
        return getattr(e, "unique_id", id(e)) in self.selected

    def delete_selected(self):
        if not self.r or not self.r.scene:
            return 0, 0
        selected = list(self.get_selected())
        if not selected:
            return 0, 0
        cmd = DeleteElementsCommand(self.r.scene, selected)
        if not self.cmd_mgr.execute(cmd):
            return 0, 0
        self.selected.clear()
        self._update_geometry_renderers(self.r.scene)
        return len(cmd.deleted), len(cmd.rejected)

    def undo(self):
        if not self.cmd_mgr.can_undo():
            return False
        if not self.cmd_mgr.undo():
            return False
        self.selected.clear()
        self._update_geometry_renderers(self.r.scene)
        return True

    def redo(self):
        if not self.cmd_mgr.can_redo():
            return False
        if not self.cmd_mgr.redo():
            return False
        self.selected.clear()
        self._update_geometry_renderers(self.r.scene)
        return True