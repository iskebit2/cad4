# ui/panels/load_manager_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from core.commands import project_commands as PC
from domain.definition import LoadPattern
from logging_config import CadLogger
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)


_PATTERN_TYPES = ("Dead", "Live", "Snow", "Wind", "Quake", "Other")


class _PatternSubPanel:
    """Load Manager → Pattern'lar sekmesi. Gömülü — kendi draft'ı yok."""

    def __init__(self):
        self.project = None
        self._queue = None
        self._new_name: str = ""
        self._new_type_idx: int = 0
        self._status: str = ""

    def set_queue(self, queue) -> None:
        self._queue = queue

    def set_context(self, project) -> None:
        self.project = project

    def draw_content(self) -> None:
        if self.project is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0), "Proje bağlı değil."
            )
            return

        self.section_label("Load Pattern'lar")
        imgui.text_disabled("Dead, Live, Snow, Wind, Quake pattern'ları burada yönetilir.")
        imgui.separator()

        self._draw_pattern_table()
        imgui.separator()
        self._draw_add_form()

        if self._status:
            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.55, 0.85, 0.6, 1.0), self._status)

    # ------------------------------------------------------------------
    def _draw_pattern_table(self) -> None:
        patterns = self.project.load_patterns
        if not patterns:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), "Henüz pattern yok.")
            return

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("##lm_patterns", 5, flags):
            return

        imgui.table_setup_column("Ad", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Tip", imgui.TableColumnFlags_.width_fixed, 100)
        imgui.table_setup_column("self_wt", imgui.TableColumnFlags_.width_fixed, 80)
        imgui.table_setup_column("Kullanım", imgui.TableColumnFlags_.width_fixed, 80)
        imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 50)
        imgui.table_headers_row()

        for name, pat in sorted(patterns.items()):
            imgui.table_next_row()

            # Ad
            imgui.table_set_column_index(0)
            imgui.text(name)

            # Tip combo — kuyruk
            imgui.table_set_column_index(1)
            try:
                cur_idx = _PATTERN_TYPES.index(str(getattr(pat, "design_type", "Dead")))
            except ValueError:
                cur_idx = 0
            imgui.push_item_width(-1)
            changed, new_idx = imgui.combo(f"##type_{name}", cur_idx, list(_PATTERN_TYPES))
            imgui.pop_item_width()
            if changed and self._queue is not None:
                self._queue.put(PC.UpdateDefinition(
                    "load_patterns", name, {"design_type": _PATTERN_TYPES[new_idx]},
                ))

            # self_wt_mult
            imgui.table_set_column_index(2)
            imgui.push_item_width(-1)
            ch, new_mult = imgui.input_float(
                f"##mult_{name}",
                float(getattr(pat, "self_wt_mult", 0.0)),
                step=0.1, format="%.2f",
            )
            imgui.pop_item_width()
            if ch and abs(new_mult - float(getattr(pat, "self_wt_mult", 0.0))) > 1e-9:
                if self._queue is not None:
                    self._queue.put(PC.UpdateDefinition(
                        "load_patterns", name, {"self_wt_mult": float(new_mult)},
                    ))

            # Kullanım
            imgui.table_set_column_index(3)
            count = self._count_pattern_usage(name)
            color = (0.5, 0.9, 0.5, 1.0) if count > 0 else (0.6, 0.6, 0.6, 1.0)
            imgui.text_colored(imgui.ImVec4(*color), f"{count} eleman")

            # Sil
            imgui.table_set_column_index(4)
            if count == 0:
                if imgui.button(f"x##del_{name}", imgui.ImVec2(30, 0)):
                    if self._queue is not None:
                        self._queue.put(PC.RemoveDefinition("load_patterns", name))
                    self._status = f"'{name}' silindi."
            else:
                imgui.text_disabled("—")

        imgui.end_table()

    # ------------------------------------------------------------------
    def _draw_add_form(self) -> None:
        self.section_label("Yeni Pattern")
        imgui.spacing()

        imgui.text("Ad")
        imgui.same_line(120)
        imgui.push_item_width(-1)
        _, self._new_name = imgui.input_text("##new_name", self._new_name, 128)
        imgui.pop_item_width()

        imgui.text("Tip")
        imgui.same_line(120)
        imgui.push_item_width(-1)
        _, self._new_type_idx = imgui.combo("##new_type", self._new_type_idx, list(_PATTERN_TYPES))
        imgui.pop_item_width()

        imgui.spacing()
        can_add = bool(self._new_name.strip())
        name_clean = self._new_name.strip()
        exists = name_clean in self.project.load_patterns

        if not can_add or exists:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0))
        if imgui.button("+ Pattern Ekle", imgui.ImVec2(-1, 28)) and can_add and not exists:
            self._add_pattern(name_clean, self._new_type_idx)
        if not can_add or exists:
            imgui.pop_style_color(1)

        if exists:
            imgui.text_colored(imgui.ImVec4(0.9, 0.6, 0.5, 1.0), f"⚠ '{name_clean}' zaten var.")
        elif not can_add:
            imgui.text_disabled("Ad gerekli.")

    def _add_pattern(self, name: str, type_idx: int) -> None:
        if self._queue is None:
            return
        self._queue.put(PC.AddDefinition(
            "load_patterns", name,
            LoadPattern(name=name, design_type=_PATTERN_TYPES[type_idx], self_wt_mult=0.0),
        ))
        self._status = f"'{name}' eklendi ({_PATTERN_TYPES[type_idx]})."
        self._new_name = ""

    def _count_pattern_usage(self, pattern: str) -> int:
        if self.project is None:
            return 0
        mm = getattr(self.project, "math_model", None)
        if mm is None:
            return 0
        count = 0
        for frame in mm.frames.values():
            if pattern in (getattr(frame, "dist_load_sets", None) or {}):
                count += 1
        for node in mm.nodes.values():
            for pl in getattr(node, "loads", None) or []:
                if getattr(pl, "pattern_name", None) == pattern:
                    count += 1
                    break
        for poly in mm.polygons.values():
            data = self.project.polygon_analysis_data(poly, create=False)
            for load in getattr(data, "assigned_loads", None) or []:
                if getattr(load, "pattern_name", None) == pattern:
                    count += 1
                    break
        return count

    # Alt panelde de section_label/status_line lazım — küçük helper
    @staticmethod
    def section_label(text: str) -> None:
        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0), text)


class LoadManagerPanel(PanelBase):
    __abstract__ = False
    panel_name = "load_manager"
    title = "Load Manager"
    category = Category.LOADS
    quick = True
    context = ("project", "scene", "selection_polygons", "selection_frames",
               "selection_nodes", "patterns")
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = False

    width = 640
    height = 680
    pos_first_use = (400.0, 80.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.project = None
        self.scene = None

        from ui.panels.load_assign_panel import LoadAssignPanel
        from ui.panels.area_to_frame_panel import AreaToFramePanel
        from ui.panels.frame_load_panel import FrameLoadPanel
        from ui.panels.joint_load_panel import JointLoadPanel
        

        self._pattern_panel = _PatternSubPanel()
        self._assign_panel = LoadAssignPanel()
        self._transfer_panel = AreaToFramePanel()
        self._frame_load_panel = FrameLoadPanel()
        self._joint_load_panel = JointLoadPanel()
        

    # ------------------------------------------------------------------
    def _on_context_ready(self) -> None:
        self.project = getattr(self, "project", None)
        self.scene = getattr(self, "scene", None)

        # Alt panelere context geçir
        base_ctx = {
            "project": self.project,
            "scene": self.scene,
            "selection_polygons": getattr(self, "selection_polygons", []),
            "selection_frames": getattr(self, "selection_frames", []),
            "selection_nodes": getattr(self, "selection_nodes", []),
            "patterns": getattr(self, "patterns", []),
            "math_model": getattr(self.app, "current_project", None).math_model
                if self.app and self.app.current_project else None,
            "renderer": self.app.engine.renderer if self.app and self.app.engine else None,
        }
        for sub in (
            self._assign_panel, self._transfer_panel,
            self._frame_load_panel, self._joint_load_panel
        ):
            try:
                sub.app = self.app
                sub.set_context(base_ctx)
            except Exception:
                logger.exception(
                    "[LoadManager] %s.set_context hatası", type(sub).__name__
                )

        self._pattern_panel.set_queue(self.queue())
        self._pattern_panel.set_context(self.project)

    # ------------------------------------------------------------------
    def draw_content(self) -> None:
        if self.project is None or self.scene is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje/sahne bağlı değil.",
            )
            return

        if imgui.collapsing_header("Load Pattern'lar##lm_patterns_hdr"):
            self._pattern_panel.draw_content()

        if imgui.collapsing_header("Alan Yükleri##lm_assign_hdr"):
            self._draw_sub_panel(self._assign_panel)

        if imgui.collapsing_header("Frame'e Aktar##lm_transfer_hdr"):
            self._draw_sub_panel(self._transfer_panel)

        if imgui.collapsing_header("Frame Yayılı Yükler##lm_frame_load_hdr"):
            self._draw_sub_panel(self._frame_load_panel)

        if imgui.collapsing_header("Noktasal Yükler##lm_joint_load_hdr"):
            self._draw_sub_panel(self._joint_load_panel)

    def _draw_sub_panel(self, sub_panel) -> None:
        try:
            sub_panel.draw_content()
        except Exception:
            logger.exception(
                "[LoadManager] %s draw hatası", type(sub_panel).__name__
            )