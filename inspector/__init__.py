"""
Inspector — bağımsız sahne element editörü.

Kullanım (CadApp içinden):
    from inspector import InspectorWindow

    self.inspector = InspectorWindow(scene=project.scene)

    # her frame:
    self.inspector.draw()

    # seçim değişince:
    self.inspector.set_selection(selected_elements)
"""

from inspector.window import InspectorWindow

__all__ = ["InspectorWindow"]