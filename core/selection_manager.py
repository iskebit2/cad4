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
        if not self.r:
            return
        engine = getattr(self.r, "engine", None)
        if engine:
            engine.update_geo()
        else:
            self.r.update_geo(self.r.math_model, scene)

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
        if self.r and self.r.math_model:
            out.extend(
                e for e in self.r.math_model.all_elements.values()
                if e.unique_id in self.selected
            )
        if self.r and self.r.scene:
            out.extend(
                element for element in self.r.scene.all_elements.values()
                if element.unique_id in self.selected
            )
        return out

    def find_element_by_id(self, unique_id: int):
        if not self.r:
            return None
        if self.r.math_model and unique_id in self.r.math_model.all_elements:
            return self.r.math_model.all_elements[unique_id]
        if self.r.scene and unique_id in self.r.scene.all_elements:
            return self.r.scene.all_elements[unique_id]
        return None

    def count(self):
        return len(self.selected)

    def is_selected(self, e):
        return getattr(e, "unique_id", id(e)) in self.selected

    def delete_selected(self):
        if not self.r or not self.r.math_model or not self.r.scene:
            return 0, 0
        selected = list(self.get_selected())
        if not selected:
            return 0, 0
        math_elements = [
            element for element in selected
            if self.r.math_model.is_element_added(element)
        ]
        visual_elements = [
            element for element in selected if element not in math_elements
        ]
        cmd = DeleteElementsCommand(self.r.math_model, math_elements)
        if math_elements and not self.cmd_mgr.execute(cmd):
            return 0, len(math_elements) + len(visual_elements)
        deleted_visual = 0
        for element in visual_elements:
            if element.unique_id in self.r.scene.polygons:
                project = getattr(self.r, "engine", None)
                project = getattr(project, "project", None)
                if project is not None:
                    deleted_visual += project.remove_polygon(element.unique_id)
                else:
                    deleted_visual += self.r.scene.remove_polygon(
                        element.unique_id,
                    )
                    if self.r.math_model.polygon_analysis.pop(
                        element.unique_id, None,
                    ) is not None:
                        self.r.math_model.mark_dirty()
            elif element.unique_id in self.r.scene.lines:
                deleted_visual += self.r.scene.remove_line(element.unique_id)
        self.selected.clear()
        self._update_geometry_renderers(self.r.scene)
        return len(cmd.deleted) + deleted_visual, len(cmd.rejected)

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