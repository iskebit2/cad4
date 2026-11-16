# ui/panels/material_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from ui.base.panel_base import PanelBase, Category


class TestPanel(PanelBase):
    __abstract__ = False
    panel_name = "test_panel"
    title = "Test Properties"
    category = Category.MANAGEMENT
    quick = False
    context = ("project",)
    uses_draft = True
    show_apply_bar = True
    use_standard_layout = True

    width = 720
    height = 760
    pos_first_use = (80.0, 60.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self._selected_name: str | None = None
        self._search = ""

    def draw_header(self) -> None:
            proj = self.draft
            if proj is None:
                imgui.text_colored(imgui.ImVec4(0.95, 0.55, 0.4, 1.0), "Proje yok.")
                return
    
            imgui.text_disabled(f"Toplam: {len(proj.materials)} material")
    
            if imgui.button("+ Yeni", imgui.ImVec2(100, 0)):
                pass
            imgui.same_line()
            can_dup = self._selected_name in proj.materials
            if self.action_button("Kopyala", 90, can_dup):
                pass
            imgui.same_line()
            if self.action_button("Sil", 70, can_dup):
                pass
            imgui.same_line()
            imgui.push_item_width(200)
            _, self._search = imgui.input_text("##search", self._search)
            imgui.pop_item_width()

    def draw_settings(self) -> None:
        proj = self.draft
        if proj is None:
            return

        

        self._draw_editor(None)

        

        
        
    def _draw_editor(self, container: dict) -> None:
        
            
        if imgui.tree_node("Geometry"):
            if imgui.tree_node("Drawing"):
                imgui.text("Point")
                imgui.text("Line")
                imgui.tree_pop()

            if imgui.tree_node("Editing"):
                imgui.text("Move")
                imgui.text("Delete")
                imgui.tree_pop()

            imgui.tree_pop()