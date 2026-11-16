# ui/panels/material_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from core.commands import project_commands as PC
from domain.definition import Material
from data.enums import MatType
from ui.base.panel_base import PanelBase, Category


class MaterialPanel(PanelBase):
    __abstract__ = False
    panel_name = "material_panel"
    title = "Material Properties"
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
        self._draft_obj: Material | None = None
        self._is_new = False
        self._search = ""
        self._confirm_delete: str | None = None
        self._renames: dict[str, str] = {}

    def _on_draft_refreshed(self) -> None:
        self._draft_obj = None
        self._selected_name = None
        self._is_new = False
        self._renames.clear()

    # ------------------------------------------------------------------
    # 1. HEADER
    # ------------------------------------------------------------------
    def draw_header(self) -> None:
        proj = self.draft
        if proj is None:
            imgui.text_colored(imgui.ImVec4(0.95, 0.55, 0.4, 1.0), "Proje yok.")
            return

        imgui.text_disabled(f"Toplam: {len(proj.materials)} material")

        if imgui.button("+ Yeni", imgui.ImVec2(100, 0)):
            self._create_new()
        imgui.same_line()
        can_dup = self._selected_name in proj.materials
        if self.action_button("Kopyala", 90, can_dup):
            self._duplicate(proj.materials)
        imgui.same_line()
        if self.action_button("Sil", 70, can_dup):
            self._confirm_delete = self._selected_name
        imgui.same_line()
        imgui.push_item_width(200)
        _, self._search = imgui.input_text("##search", self._search)
        imgui.pop_item_width()

    # ------------------------------------------------------------------
    # 2. SETTINGS — liste + editör
    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        proj = self.draft
        if proj is None:
            return

        imgui.begin_child("##mat_list", imgui.ImVec2(220, 320), imgui.ChildFlags_.borders)
        q = self._search.lower()
        for name in sorted(proj.materials.keys()):
            if q and q not in name.lower():
                continue
            is_sel = (name == self._selected_name)
            if imgui.selectable(name, is_sel)[0]:
                self._select_existing(proj.materials[name])
        imgui.end_child()

        imgui.same_line()

        imgui.begin_child("##mat_editor", imgui.ImVec2(0, 320), imgui.ChildFlags_.borders)
        if self._draft_obj is None:
            imgui.text_disabled("Soldan bir material seç veya + Yeni'ye bas.")
        else:
            self._draw_editor(proj.materials)
        imgui.end_child()

    def _draw_editor(self, container: dict) -> None:
        mat = self._draft_obj
        if mat is None:
            return

        imgui.push_item_width(200)

        c, v = imgui.input_text("Ad", mat.name)
        if c:
            mat.name = v
        if self._is_new and mat.name in container:
            imgui.text_colored(imgui.ImVec4(1, 0.5, 0.3, 1.0), "⚠ Bu isimde kayıt var!")

        mat_types = list(MatType)
        cur_idx = mat_types.index(mat.mat_type) if mat.mat_type in mat_types else 0
        labels = [getattr(mt, "sap_label", mt.name) if hasattr(mt, "sap_label") else mt.name for mt in mat_types]
        if imgui.begin_combo("Tip", labels[cur_idx]):
            for i, lbl in enumerate(labels):
                if imgui.selectable(lbl, i == cur_idx)[1] and i != cur_idx:
                    mat.mat_type = mat_types[i]
            imgui.end_combo()

        c, v = imgui.input_float("E1 (MPa)", float(mat.E1), 100.0, 1000.0)
        if c: mat.E1 = float(v)
        c, v = imgui.input_float("E2", float(mat.E2), 100.0, 1000.0)
        if c: mat.E2 = float(v)
        c, v = imgui.input_float("E3", float(mat.E3), 100.0, 1000.0)
        if c: mat.E3 = float(v)
        c, v = imgui.input_float("G12 (MPa)", float(mat.G12), 100.0, 1000.0)
        if c: mat.G12 = float(v)
        c, v = imgui.input_float("G13", float(mat.G13), 100.0, 1000.0)
        if c: mat.G13 = float(v)
        c, v = imgui.input_float("G23", float(mat.G23), 100.0, 1000.0)
        if c: mat.G23 = float(v)
        c, v = imgui.input_float("ν12", float(mat.nu12), 0.01, 0.05)
        if c: mat.nu12 = float(v)
        c, v = imgui.input_float("ν13", float(mat.nu13), 0.01, 0.05)
        if c: mat.nu13 = float(v)
        c, v = imgui.input_float("ν23", float(mat.nu23), 0.01, 0.05)
        if c: mat.nu23 = float(v)
        c, v = imgui.input_float("Yoğunluk", float(mat.density), 1e-6, 1e-3, "%.8g")
        if c: mat.density = float(v)

        if mat.is_steel():
            c, v = imgui.input_float("fy (MPa)", float(mat.fy), 5.0, 10.0)
            if c: mat.fy = float(v)
            c, v = imgui.input_float("fu (MPa)", float(mat.fu), 5.0, 10.0)
            if c: mat.fu = float(v)

        if mat.is_concrete():
            c, v = imgui.input_float("fc (MPa)", float(mat.fc), 1.0, 5.0)
            if c: mat.fc = float(v)

        imgui.pop_item_width()

        imgui.spacing()
        can_save = bool(mat.name.strip()) and (not self._is_new or mat.name not in container)
        if self.action_button("Kaydet", 120, can_save):
            self._commit_edit(container)
        imgui.same_line()
        if self.action_button("İptal", 100, True):
            self._draft_obj = None
            self._selected_name = None
            self._is_new = False

    # ------------------------------------------------------------------
    # 3. ACTIONS
    # ------------------------------------------------------------------
    def draw_actions(self) -> None:
        self._draw_delete_confirm()

    def _draw_delete_confirm(self) -> None:
        if not self._confirm_delete:
            return
        imgui.open_popup("Silme Onayı")
        if imgui.begin_popup_modal("Silme Onayı", True)[0]:
            imgui.text(f"'{self._confirm_delete}' silinsin mi?")
            imgui.separator()
            if imgui.button("Evet", imgui.ImVec2(120, 0)):
                proj = self.draft
                if proj is not None:
                    proj.materials.pop(self._confirm_delete, None)
                self._confirm_delete = None
                self._draft_obj = None
                self._selected_name = None
                self._is_new = False
                self.mark_dirty()
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Vazgeç", imgui.ImVec2(120, 0)):
                self._confirm_delete = None
                imgui.close_current_popup()
            imgui.end_popup()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def _create_new(self) -> None:
        proj = self.draft
        if proj is None:
            return
        base = "MALZEME"
        name = base
        n = 1
        while name in proj.materials:
            name = f"{base}_{n}"
            n += 1
        self._draft_obj = Material(name=name)
        self._is_new = True
        self._selected_name = None

    def _duplicate(self, container: dict) -> None:
        src = container.get(self._selected_name)
        if src is None:
            return
        import dataclasses
        dup = dataclasses.replace(src, color=tuple(src.color))
        base = f"{src.name}_copy"
        name = base
        n = 1
        while name in container:
            name = f"{base}_{n}"
            n += 1
        dup.name = name
        self._draft_obj = dup
        self._is_new = True
        self._selected_name = None

    def _select_existing(self, mat: Material) -> None:
        import dataclasses
        self._draft_obj = dataclasses.replace(mat, color=tuple(mat.color))
        self._selected_name = mat.name
        self._is_new = False

    def _commit_edit(self, container: dict) -> None:
        obj = self._draft_obj
        if obj is None:
            return
        new_name = obj.name
        old_name = self._selected_name
        if old_name and old_name != new_name and old_name in container:
            container.pop(old_name)
            container[new_name] = obj
            self._renames[old_name] = new_name
        else:
            container[new_name] = obj
        self._selected_name = new_name
        self._draft_obj = None
        self._is_new = False
        self.mark_dirty()

    # ------------------------------------------------------------------
    # 4. EMIT COMMANDS
    # ------------------------------------------------------------------
    def _emit_commands(self) -> None:
        orig = self._original
        draft = self.draft
        if orig is None or draft is None:
            return
        queue = self.queue()

        orig_c = orig.materials or {}
        draft_c = draft.materials or {}

        renamed_olds: set[str] = set()
        renamed_news: set[str] = set()
        for old_name, new_name in list(self._renames.items()):
            if old_name not in orig_c or new_name not in draft_c:
                continue
            old_obj = orig_c[old_name]
            new_obj = draft_c[new_name]
            changes = {}
            for f in ("mat_type", "color", "E1", "E2", "E3", "G12", "G13", "G23",
                      "nu12", "nu13", "nu23", "density", "fy", "fu", "fc"):
                av = getattr(old_obj, f, None)
                bv = getattr(new_obj, f, None)
                if av != bv:
                    changes[f] = bv
            queue.put(PC.UpdateDefinition("materials", old_name, changes, new_name=new_name))
            renamed_olds.add(old_name)
            renamed_news.add(new_name)

        orig_names = set(orig_c.keys()) - renamed_olds
        draft_names = set(draft_c.keys()) - renamed_news

        for name in draft_names - orig_names:
            queue.put(PC.AddDefinition("materials", name, draft_c[name]))

        for name in orig_names - draft_names:
            queue.put(PC.RemoveDefinition("materials", name))

        for name in orig_names & draft_names:
            a, b = orig_c[name], draft_c[name]
            changes = {}
            for f in ("mat_type", "color", "E1", "E2", "E3", "G12", "G13", "G23",
                      "nu12", "nu13", "nu23", "density", "fy", "fu", "fc"):
                av = getattr(a, f, None)
                bv = getattr(b, f, None)
                if av != bv:
                    changes[f] = bv
            if changes:
                queue.put(PC.UpdateDefinition("materials", name, changes))