# gui/definition_browser.py
"""
Sol panel: tüm kategorileri ağaç olarak gösterir.
Bir öğeye tıklanınca on_select(obj) tetiklenir.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.treeview import TreeView, TreeViewLabel


class DefinitionBrowser(BoxLayout):
    def __init__(self, manager, on_select, on_save, **kw):
        super().__init__(orientation="vertical", **kw)
        self.manager = manager
        self.on_select = on_select
        self.on_save = on_save

        self.tree = TreeView(hide_root=True)
        self.add_widget(self.tree)

        self.refresh()

    def set_manager(self, manager):
        self.manager = manager
        self.refresh()

    def refresh(self):
        self.tree.clear_widgets()
        tree_dict = self.manager.__inspector_tree__()
        for category, container in tree_dict.items():
            cat = self.tree.add_node(TreeViewLabel(
                text=f"[b]{category}[/b]",
                markup=True,
                is_open=True,
            ))
            if isinstance(container, dict):
                for key, obj in container.items():
                    label = self._label_for(obj, key)
                    node = self.tree.add_node(
                        TreeViewLabel(text=label), parent=cat)
                    node.bind(on_touch_down=(
                        lambda w, t, o=obj: self._on_touch(w, t, o)))
            else:
                self.tree.add_node(
                    TreeViewLabel(text=str(container)), parent=cat)

    @staticmethod
    def _label_for(obj, key):
        name = getattr(obj, "name", None)
        if name and name != key:
            return f"{key}  •  {name}"
        return str(key)

    def _on_touch(self, node, touch, obj):
        if not node.collide_point(*touch.pos):
            return False
        if touch.button != "left":
            return False
        self.on_select(obj)
        return True