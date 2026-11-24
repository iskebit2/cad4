# ui/panels/report_panel.py
from __future__ import annotations

import pandas as pd
from imgui_bundle import imgui

from app.settings.categories import Category
from core.report.report_dataframe import ReportDataFrame
from core.report.report_tree import ReportSection, ReportTree, ReportTreeNode
from logging_config import CadLogger
from tools.report_builders import ReportBuildResult, build_project_report_tree
from tools.report_export import export_docx
from ui.base.panel_base import PanelBase

logger = CadLogger.get(__name__)


class ReportPanel(PanelBase):
    __abstract__ = False
    panel_name = "report"
    title = "Reports"
    category = Category.MANAGEMENT
    quick = True
    menu_label = "Reports"
    icon = "file-text"
    context = ("scene", "project")

    uses_draft = False
    show_apply_bar = False
    PREVIEW_ROWS = 15

    def __init__(self, app=None):
        super().__init__(app=app)
        self.width = 960
        self.height = 620
        self.pos_first_use = (420, 110)
        self.project = None
        self.scene = None
        self._result: ReportBuildResult | None = None
        self._tree: ReportTree = ReportTree()
        self._sections: dict[str, ReportSection] = {}
        self._selected_section_id: str | None = None
        self._detail_index: int = 0
        self._export_selected: set[str] = set()

    def _refresh_draft(self) -> None:
        self.draft = None
        self._original = None
        self._dirty = False

    def _project(self):
        return self.project or (self.app.current_project if self.app else None)

    def open(self, **kw) -> None:
        super().open(**kw)
        proj = self._project()
        if proj is None or not hasattr(proj, "report"):
            return
        if not self._sections and not proj.report.reports:
            self._rebuild(proj)
        self._detail_index = 0

    def _rebuild(self, proj) -> None:
        proj.report.clear()
        self._result = build_project_report_tree(proj)
        self._tree = self._result.tree
        self._sections = {s.section_id: s for s in self._result.sections}
        for rep in self._result.produced:
            proj.report.add_report(rep)
        self._selected_section_id = self._tree.nodes[0].section_id if self._tree.nodes else None
        self._detail_index = 0
        self._export_selected = {n.section_id for n in self._tree.nodes if n.enabled}
        for stage, reason in self._result.skipped:
            logger.info("[ReportPanel] %s atlandı: %s", stage, reason)
        for stage, reason in self._result.failed:
            logger.warning("[ReportPanel] %s başarısız: %s", stage, reason)

    def draw_content(self) -> None:
        proj = self._project()
        if proj is None or not hasattr(proj, "report"):
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.5, 0.4, 1.0),
                "Proje veya Rapor Yöneticisi bağlı değil.",
            )
            return

        self._draw_toolbar(proj)
        imgui.separator()

        if not self._tree.nodes:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.7, 0.7, 1.0),
                "Henüz oluşturulmuş bir rapor bulunmuyor.",
            )
            self._draw_issues()
            return

        valid_ids = {n.section_id for n in self._tree.nodes}
        self._export_selected = {sid for sid in self._export_selected if sid in valid_ids}
        if self._selected_section_id not in valid_ids:
            self._selected_section_id = self._tree.nodes[0].section_id

        self._draw_tree(self._tree.nodes)
        imgui.same_line()
        active_sec = self._sections.get(self._selected_section_id or "")
        self._draw_section_preview(active_sec)
        self._draw_issues()

    def _draw_toolbar(self, proj) -> None:
        if imgui.button("Yeniden Oluştur"):
            self._rebuild(proj)
        imgui.same_line()
        if imgui.button("Temizle"):
            proj.report.clear()
            self._result = None
            self._tree = ReportTree()
            self._sections = {}
            self._selected_section_id = None
            self._detail_index = 0
            self._export_selected = set()
        imgui.same_line()
        if imgui.button("Tümünü Seç"):
            self._export_selected = {n.section_id for n in self._tree.nodes}
        imgui.same_line()
        if imgui.button("Seçimi Kaldır"):
            self._export_selected = set()

        imgui.same_line()
        imgui.text_disabled(f"Seçili: {len(self._export_selected)}")
        imgui.same_line()

        has_selection = bool(self._export_selected)
        imgui.begin_disabled(not has_selection)
        if imgui.button("DOCX'e Aktar"):
            self._export_docx(proj)
        imgui.same_line()
        if imgui.button("PDF'e Aktar"):
            self._export_pdf(proj)
        imgui.end_disabled()

    def _draw_tree(self, nodes: list[ReportTreeNode]) -> None:
        imgui.begin_child("##report_tree", imgui.ImVec2(320, 0), True)
        imgui.text_colored(imgui.ImVec4(0.8, 0.9, 1.0, 1.0), "Rapor Ağacı")
        imgui.separator()
        for node in nodes:
            checked = node.section_id in self._export_selected
            changed, new_val = imgui.checkbox(f"##exp_{node.node_id}", checked)
            if changed:
                if new_val:
                    self._export_selected.add(node.section_id)
                else:
                    self._export_selected.discard(node.section_id)
            imgui.same_line()
            selected = self._selected_section_id == node.section_id
            label = f"{node.title} [{node.status.value}]##sel_{node.node_id}"
            if imgui.selectable(label, selected)[0]:
                self._selected_section_id = node.section_id
                self._detail_index = 0
        imgui.end_child()

    def _draw_section_preview(self, section: ReportSection | None) -> None:
        imgui.begin_child("##report_detail", imgui.ImVec2(0, 0), True)
        if section is None:
            imgui.text_disabled("Bölüm seçilmedi.")
            imgui.end_child()
            return

        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), f"{section.title} ({section.status.value})")
        imgui.separator()

        for note in section.notes:
            imgui.text_wrapped(f"Not: {note}")

        if not section.frames:
            imgui.text_colored(
                imgui.ImVec4(0.8, 0.6, 0.4, 1.0),
                "Bu bölümde gösterilecek tablo verisi bulunmuyor.",
            )
            imgui.end_child()
            return

        if len(section.frames) > 1:
            imgui.text_disabled("Tablolar:")
            for idx, frame in enumerate(section.frames):
                ftitle = getattr(frame, "custom_title", None) or f"Tablo {idx + 1}"
                if imgui.radio_button(f"{ftitle}##tab_{idx}", self._detail_index == idx):
                    self._detail_index = idx
            imgui.spacing()

        if self._detail_index >= len(section.frames):
            self._detail_index = 0
        rep = section.frames[self._detail_index]
        self._draw_dataframe_preview(rep)
        imgui.end_child()

    def _draw_dataframe_preview(self, rep: ReportDataFrame) -> None:
        title = getattr(rep, "custom_title", None) or "Rapor"
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0), title)
        desc = getattr(rep, "custom_desc", None)
        if desc:
            imgui.text_wrapped(str(desc).strip())
            imgui.spacing()

        self._draw_meta(rep)
        self._draw_table(rep)
        self._draw_graphics_info(rep)

    def _draw_meta(self, rep: ReportDataFrame) -> None:
        units = getattr(rep, "column_units", {}) or {}
        descriptions = getattr(rep, "column_descriptions", {}) or {}
        if not units and not descriptions:
            return
        imgui.text_disabled("Kolon bilgisi")
        for col in rep.columns:
            line = str(col)
            unit = units.get(col, "")
            desc = descriptions.get(col, "")
            if unit:
                line += f"  [{unit}]"
            if desc:
                line += f"  — {desc}"
            imgui.text_wrapped(line)
        imgui.spacing()

    def _draw_table(self, rep: ReportDataFrame) -> None:
        if not isinstance(rep, pd.DataFrame) or rep.empty:
            imgui.text_colored(
                imgui.ImVec4(0.8, 0.6, 0.4, 1.0),
                "Bu raporda gösterilecek tablo verisi bulunmuyor.",
            )
            return

        total = len(rep)
        shown = min(total, self.PREVIEW_ROWS)
        imgui.text_disabled(f"Önizleme: {shown} / {total} satır")

        cols = [str(c) for c in rep.columns]
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.scroll_y
        )
        if not imgui.begin_table(f"##preview_table_{self._detail_index}", len(cols), flags):
            return
        for col in cols:
            imgui.table_setup_column(col)
        imgui.table_headers_row()

        for _, row in rep.head(shown).iterrows():
            imgui.table_next_row()
            formatted = rep._format_row(row)
            for col_idx, text in enumerate(formatted):
                imgui.table_set_column_index(col_idx)
                imgui.text(text)
        imgui.end_table()

    def _draw_graphics_info(self, rep: ReportDataFrame) -> None:
        graphics = getattr(rep, "graphics", []) or []
        if not graphics:
            return
        imgui.spacing()
        imgui.text_disabled(f"Grafikler: {len(graphics)} adet")

    def _draw_issues(self) -> None:
        result = self._result
        if result is None or not result.has_issues:
            return
        imgui.spacing()
        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.95, 0.75, 0.35, 1.0), "Uyarılar")
        for stage, reason in result.skipped:
            imgui.text_wrapped(f"Atlandı — {stage}: {reason}")
        for stage, reason in result.failed:
            imgui.text_wrapped(f"Başarısız — {stage}: {reason}")

    def _export_docx(self, proj) -> None:
        selected_ids = [n.section_id for n in self._tree.nodes if n.section_id in self._export_selected]
        if not selected_ids:
            return
        ui = getattr(self.app, "ui", None)
        if ui is None:
            return

        selected_sections = [self._sections[sid] for sid in selected_ids if sid in self._sections]
        selected_tree = ReportTree(
            nodes=[n for n in self._tree.nodes if n.section_id in self._export_selected]
        )
        selected_frames = self._selected_reports(proj)

        def _on_save(path: str) -> None:
            ok = export_docx(
                selected_frames,
                path,
                tree=selected_tree,
                sections=selected_sections,
            )
            if ok:
                logger.info("[ReportPanel] DOCX kaydedildi: %s", path)
            else:
                logger.warning("[ReportPanel] DOCX kaydedilemedi: %s", path)

        ui.open_export_dialog(
            on_select=_on_save,
            default_name="proje_raporu.docx",
            ext=".docx",
            title="Raporu DOCX olarak kaydet",
        )

    def _export_pdf(self, proj) -> None:
        selected = self._selected_reports(proj)
        if not selected:
            return
        ui = getattr(self.app, "ui", None)
        if ui is None:
            return

        def _on_save(path: str) -> None:
            from tools.report_export import export_pdf
            ok = export_pdf(selected, path)
            if ok:
                logger.info("[ReportPanel] PDF kaydedildi: %s", path)
            else:
                logger.warning("[ReportPanel] PDF kaydedilemedi: %s", path)

        ui.open_export_dialog(
            on_select=_on_save,
            default_name="proje_raporu.pdf",
            ext=".pdf",
            title="Raporu PDF olarak kaydet",
        )

    def _selected_reports(self, proj) -> list[ReportDataFrame]:
        out: list[ReportDataFrame] = []
        for node in self._tree.nodes:
            if node.section_id not in self._export_selected:
                continue
            sec = self._sections.get(node.section_id)
            if sec is not None:
                out.extend(sec.frames)
        if out:
            return out
        return list(proj.report.reports)