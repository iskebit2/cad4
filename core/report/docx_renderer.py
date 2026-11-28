# core/report/docx_renderer.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.report.my_document import MyDocument
from core.report.report_dataframe import ReportDataFrame
from core.report.report_tree import PageLayoutConfig, ReportSection, ReportTree


class DocxRenderer:
    def __init__(self, layout: PageLayoutConfig | None = None) -> None:
        self.layout = layout if layout is not None else PageLayoutConfig()

    def render(
        self,
        tree: ReportTree,
        sections: dict[str, ReportSection],
        path: str | Path,
        doc_title: str = "Proje Raporu",
    ) -> bool:
        doc = MyDocument()
        doc.apply_visual_settings()
        doc.add_heading_numbered(doc_title, level=1)

        is_first = True
        for node in tree.nodes:
            if not node.enabled:
                continue
            sec = sections.get(node.section_id)
            if sec is None:
                continue
            self._render_section(doc, sec, level=2, is_first=is_first)
            is_first = False

        return doc.save_report(str(path))

    def _render_section(
        self,
        doc: MyDocument,
        section: ReportSection,
        level: int,
        is_first: bool,
    ) -> None:
        is_material = section.section_id.endswith("_module")
        if not is_first:
            if is_material and self.layout.page_break_before_material_modules:
                doc.add_page_break()
            elif not is_material and self.layout.page_break_before_main_sections:
                doc.add_page_break()

        doc.add_heading_numbered(section.title, level=level)

        for note in section.notes:
            doc.add_paragraph(note)

        for df in section.frames:
            self._render_dataframe(doc, df, level=level + 1)

        for child in section.children:
            self._render_section(doc, child, level=level + 1, is_first=True)

    def _render_dataframe(self, doc: MyDocument, df: ReportDataFrame, level: int) -> None:
        from docx.enum.section import WD_ORIENT
        from docx.shared import Cm

        is_wide = len(df.columns) > 10
        raw_doc = getattr(doc, "doc", doc)

        if is_wide:
            sec_land = raw_doc.add_section()
            sec_land.orientation = WD_ORIENT.LANDSCAPE
            sec_land.page_width, sec_land.page_height = sec_land.page_height, sec_land.page_width
            sec_land.left_margin = Cm(1.0)
            sec_land.right_margin = Cm(1.0)
            sec_land.top_margin = Cm(1.2)
            sec_land.bottom_margin = Cm(1.2)

        title = getattr(df, "custom_title", None)
        desc = getattr(df, "custom_desc", None)

        if title:
            doc.add_heading_numbered(str(title), level=level)
        if desc:
            doc.add_paragraph(str(desc))

        if df.empty:
            doc.add_paragraph("Gösterilecek veri bulunamadı.")
        else:
            headers: list[str] = []
            for col in df.columns:
                unit = getattr(df, "column_units", {}).get(col, "") if isinstance(getattr(df, "column_units", None), dict) else ""
                headers.append(f"{col} [{unit}]" if unit else str(col))

            rows: list[list[Any]] = []
            for _, data_row in df.iterrows():
                rows.append(df._format_row(data_row) if hasattr(df, "_format_row") else list(data_row.values))

            doc.add_table(rows, headers)

        for graphic in getattr(df, "graphics", []) or []:
            g_title = graphic.get("title")
            g_desc = graphic.get("description")
            if g_title:
                p = doc.add_paragraph()
                p.add_run(str(g_title)).bold = True
            if g_desc:
                doc.add_paragraph(str(g_desc))
            img_stream = graphic.get("image") or graphic.get("data")
            if img_stream is not None:
                width_cm = graphic.get("width_cm")
                if width_cm is None:
                    width_cm = graphic.get("width")
                if width_cm is None:
                    width_cm = self.layout.default_image_width_cm
                doc.add_image(img_stream, width_cm=float(width_cm))

        if is_wide:
            sec_port = raw_doc.add_section()
            sec_port.orientation = WD_ORIENT.PORTRAIT
            sec_port.page_width, sec_port.page_height = sec_port.page_height, sec_port.page_width
            sec_port.left_margin = Cm(2.0)
            sec_port.right_margin = Cm(1.0)
            sec_port.top_margin = Cm(2.0)
            sec_port.bottom_margin = Cm(2.0)