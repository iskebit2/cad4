# tools/report_export.py
from __future__ import annotations

from pathlib import Path

from core.report.docx_renderer import DocxRenderer
from core.report.report_dataframe import ReportDataFrame
from core.report.report_tree import PageLayoutConfig, ReportSection, ReportTree, SectionStatus


def _sections_from_dataframes(reports: list[ReportDataFrame]) -> tuple[ReportTree, dict[str, ReportSection]]:
    from core.report.report_tree import ReportTreeNode

    nodes: list[ReportTreeNode] = []
    sec_map: dict[str, ReportSection] = {}
    for idx, rep in enumerate(reports):
        sec_id = f"item_{idx + 1}"
        title = getattr(rep, "custom_title", None) or f"Rapor {idx + 1}"
        sec = ReportSection(
            section_id=sec_id,
            title=str(title),
            status=SectionStatus.READY,
            frames=[rep],
        )
        sec_map[sec_id] = sec
        nodes.append(
            ReportTreeNode(
                node_id=sec_id,
                title=str(title),
                section_id=sec_id,
                status=SectionStatus.READY,
                enabled=True,
            )
        )
    return ReportTree(nodes=nodes), sec_map


def export_docx(
    reports: list[ReportDataFrame],
    path: str | Path,
    title: str = "Proje Raporu",
    *,
    tree: ReportTree | None = None,
    sections: list[ReportSection] | None = None,
    layout: PageLayoutConfig | None = None,
) -> bool:
    renderer = DocxRenderer(layout=layout)
    if tree is not None and sections is not None:
        sec_map = {s.section_id: s for s in sections}
        return renderer.render(tree, sec_map, path, doc_title=title)
    built_tree, sec_map = _sections_from_dataframes(reports)
    return renderer.render(built_tree, sec_map, path, doc_title=title)


def export_pdf(
    reports: list[ReportDataFrame],
    path: str | Path,
    title: str = "Proje Raporu",
) -> bool:
    raise NotImplementedError("PDF export kütüphanesi seçilmedi")