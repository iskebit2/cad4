# core/selection_manager.py
from dataclasses import field

from core.commands import CommandManager, DeleteElementsCommand
from core.selection_policy import SelectionMode


class SelectionManager:

    def __init__(self, scene_renderer):
        self.r = scene_renderer
        self.selected: set[int] = set()
        self.cmd_mgr = CommandManager(max_history=100)
        self.on_selection_changed = None
        self.named_selections = {}
        
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
        if additive:
            if eid in self.selected:
                self.selected.remove(eid)     # toggle-off
            else:
                self.selected.add(eid)         # toggle-on
                
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

    def select_all(self):
        if not (self.r and self.r.math_model):
            return
        mm = self.r.math_model
        all_els = list(mm.all_elements.values())
        self.select_multiple(all_els, mode=SelectionMode.REPLACE)

    def invert_selection(self):
        if not (self.r and self.r.math_model):
            return
        mm = self.r.math_model
        all_els = list(mm.all_elements.values())
        current = self.selected
        new_els = [e for e in all_els if e.unique_id not in current]
        self.select_multiple(new_els, mode=SelectionMode.REPLACE)

    def expand_to_nodes(self):
        """Filtrelenen/seçilen frame, line, link, area ve polygon'ların köşe node'lerini seçime ekler."""
        if not (self.r and self.r.math_model):
            return
        selected_els = self.get_selected()
        nodes_by_id: dict[int, object] = {}

        for e in selected_els:
            for attr in ("node_i", "node_j", "v1", "v2"):
                node = getattr(e, attr, None)
                if node is not None and hasattr(node, "unique_id"):
                    nodes_by_id[node.unique_id] = node
            nodes_list = getattr(e, "nodes", None)
            if nodes_list:
                for node in nodes_list:
                    if node is not None and hasattr(node, "unique_id"):
                        nodes_by_id[node.unique_id] = node

        if nodes_by_id:
            self.select_multiple(list(nodes_by_id.values()), mode=SelectionMode.ADD)

    def save_selection(self, name: str):
        """Seçimi isimle kaydet"""
        if not name.strip():
            return
        # __init__ içine self.named_selections = {} tanımladığından emin ol
        if not hasattr(self, "named_selections"):
            self.named_selections = {}
        self.named_selections[name.strip()] = list(self.selected)

    def load_selection(self, name: str):
        """İsmi verilen kayıtlı seçimi geri yükle"""
        if not hasattr(self, "named_selections") or name not in self.named_selections:
            return
        ids = self.named_selections[name]
        if not (self.r and self.r.math_model):
            return
        mm = self.r.math_model
        all_dict = {}
        for coll in (getattr(mm, 'nodes', {}), getattr(mm, 'frames', {}), 
                     getattr(mm, 'areas', {}), getattr(mm, 'links', {}),
                     getattr(mm, 'polygons', {}), getattr(mm, 'lines', {})):
            all_dict.update(coll)
            
        elements = [all_dict[uid] for uid in ids if uid in all_dict]
        self.select_multiple(elements, mode=SelectionMode.REPLACE)

    def clear(self):
        for e in self.get_selected():
            e.is_selected = False
        self.selected.clear()
        if self.on_selection_changed:
            self.on_selection_changed([])
        if self.r:
            self.r.update_sel()

    def get_selected(self):
        if not (self.r and self.r.math_model):
            return []
        return [
            element for element in self.r.math_model.all_elements.values()
            if element.unique_id in self.selected
        ]

    def find_element_by_id(self, unique_id: int):
        if not self.r:
            return None
        if self.r.math_model and unique_id in self.r.math_model.all_elements:
            return self.r.math_model.all_elements[unique_id]
        return None

    def count(self):
        return len(self.selected)

    def is_selected(self, e):
        return getattr(e, "unique_id", id(e)) in self.selected

    def delete_selected(self):
        if not self.r or not self.r.math_model:
            return 0, 0
        selected = list(self.get_selected())
        if not selected:
            return 0, 0
        # Yeni mimari: komutu kuyruğa at
        ui = getattr(getattr(self.r, "engine", None), "_app", None)

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
    