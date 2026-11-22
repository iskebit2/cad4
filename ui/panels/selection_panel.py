# ui/panels/selection_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from core.selection_policy import SelectionMode
from logging_config import CadLogger
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)


_MODE_LABEL = {
    SelectionMode.REPLACE: "REPLACE (normal)",
    SelectionMode.ADD:     "ADD (Shift)",
    SelectionMode.TOGGLE:  "TOGGLE (Ctrl)",
}


class SelectionPanel(PanelBase):
    panel_name = "selection"
    title = "Selection Manager"
    category = Category.VIEW
    quick = False
    context = ("selection_manager", "selection_policy", "math_model")

    uses_draft = False        # ★ seçim draft'lanmaz

    width = 420
    height = 560

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.selection_manager = None
        self.selection_policy = None
        self.math_model = None
        self._save_name_buffer = "Grup_1"
        self._selected_saved_index = 0
        self._rename_buffer: dict[str, str] = {}

    def draw_content(self) -> None:
        sm = self.selection_manager
        if sm is None:
            imgui.text_colored(imgui.ImVec4(1, 0.6, 0.3, 1), "SelectionManager yok.")
            return

        self._draw_status(sm)
        imgui.separator()
        self._draw_basic_actions(sm)
        imgui.separator()
        self._draw_visibility_actions()      # ★ YENİ
        imgui.separator()
        self._draw_mode_info()
        imgui.separator()
        self._draw_saved_sets(sm)
        imgui.separator()
        self._draw_undo_redo(sm)

    # ------------------------------------------------------------------
    def _draw_status(self, sm) -> None:
        count = sm.count()
        if count > 0:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(0.4, 0.9, 0.6, 1))
            imgui.text(f"● {count} eleman seçili")
            imgui.pop_style_color()
        else:
            imgui.text_disabled("○ Seçim yok")

        imgui.same_line()
        avail = imgui.get_content_region_avail().x
        if avail > 100:
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + avail - 90)
        if imgui.button("Temizle", imgui.ImVec2(80, 0)):
            sm.clear()

    def _draw_basic_actions(self, sm) -> None:
        if imgui.button("Tümünü Seç", imgui.ImVec2(140, 0)):
            sm.select_all()
        imgui.same_line()
        if imgui.button("Invert", imgui.ImVec2(100, 0)):
            sm.invert_selection()
        imgui.same_line()
        if imgui.button("Köşe Node'lar", imgui.ImVec2(140, 0)):
            sm.expand_to_nodes()

    def _draw_mode_info(self) -> None:
        pol = self.selection_policy
        if pol is None:
            return
        active = pol.get_mode()
        imgui.text_disabled("Aktif Seçim Modu:")
        imgui.same_line()
        imgui.text_colored(imgui.ImVec4(0.7, 0.85, 1.0, 1), _MODE_LABEL.get(active, str(active)))
        imgui.text_disabled("Ctrl=Toggle  Shift=Add  Boş=Replace")

    def _draw_saved_sets(self, sm) -> None:
        imgui.text_disabled("Kayıtlı Seçim Setleri")
        imgui.set_next_item_width(200)
        changed, new_name = imgui.input_text("##save_name", self._save_name_buffer)
        if changed:
            self._save_name_buffer = new_name
        imgui.same_line()
        if imgui.button("Kaydet", imgui.ImVec2(80, 0)):
            name = self._save_name_buffer.strip()
            if name:
                sm.save_selection(name)
                self._save_name_buffer = "Grup_1"

        sets = getattr(sm, "named_selections", {}) or {}
        if not sets:
            imgui.text_disabled("(kayıtlı set yok)")
            return

        imgui.begin_child("sel_sets", imgui.ImVec2(0, 160), imgui.ChildFlags_.borders)
        names = sorted(sets.keys())
        to_delete: str | None = None
        for name in names:
            uids = sets[name]
            imgui.push_id(f"set_{name}")
            imgui.text(f"• {name}  ({len(uids)} eleman)")
            imgui.same_line()

            avail = imgui.get_content_region_avail().x
            btn_w = 68.0
            if avail > btn_w * 2 + 8:
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + avail - btn_w * 2 - 8)

            if imgui.button("Yükle", imgui.ImVec2(btn_w, 0)):
                sm.load_selection(name)
            imgui.same_line()
            if imgui.button("Sil", imgui.ImVec2(btn_w, 0)):
                to_delete = name
            imgui.pop_id()

        if to_delete is not None:
            sets.pop(to_delete, None)
        imgui.end_child()

    def _draw_undo_redo(self, sm) -> None:
        can_undo = sm.cmd_mgr.can_undo() if sm.cmd_mgr else False
        can_redo = sm.cmd_mgr.can_redo() if sm.cmd_mgr else False

        if not can_undo:
            imgui.begin_disabled()
        if imgui.button("Undo", imgui.ImVec2(100, 0)):
            sm.undo()
        if not can_undo:
            imgui.end_disabled()

        imgui.same_line()

        if not can_redo:
            imgui.begin_disabled()
        if imgui.button("Redo", imgui.ImVec2(100, 0)):
            sm.redo()
        if not can_redo:
            imgui.end_disabled()

    def _draw_visibility_actions(self) -> None:
        app = self.app
        if app is None:
            return
        ui = getattr(app, "ui", None)
        if ui is None:
            return

        from app.commands import project_commands as PC

        show_only = getattr(app, "_show_only_ids", None) is not None
        hidden = getattr(app, "_hidden_ids", None) or set()

        if show_only:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.5, 0.8, 1))
        if imgui.button("Sadece Seçili", imgui.ImVec2(140, 0)):
            selected = self.selection_manager.get_selected() if self.selection_manager else []
            if selected:
                uids = [e.unique_id for e in selected]
                app.command_queue.put(PC.ShowOnly(uids))
            else:
                ui.command_queue.put(PC.ShowOnly(None))
        if show_only:
            imgui.pop_style_color()

        imgui.same_line()
        if imgui.button("Seçiliyi Gizle", imgui.ImVec2(140, 0)):
            selected = self.selection_manager.get_selected() if self.selection_manager else []
            if selected:
                uids = [e.unique_id for e in selected]
                ui.command_queue.put(PC.HideElements(uids))

        imgui.same_line()
        if imgui.button("Tümünü Göster", imgui.ImVec2(140, 0)):
            ui.command_queue.put(PC.ShowEntireModel())

        if hidden:
            imgui.text_disabled(f"({len(hidden)} eleman gizli)")