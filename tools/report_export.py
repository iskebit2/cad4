# tools/report_export.py
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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


def _find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def export_pdf(
    reports: list[ReportDataFrame],
    path: str | Path,
    title: str = "Proje Raporu",
    *,
    tree: ReportTree | None = None,
    sections: list[ReportSection] | None = None,
    layout: PageLayoutConfig | None = None,
) -> bool:
    soffice = _find_soffice()
    if soffice is None:
        return False

    target_pdf = Path(path).resolve()
    if target_pdf.suffix.lower() != ".pdf":
        target_pdf = target_pdf.with_suffix(".pdf")
    target_pdf.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tmp_docx = tmp_path / f"{target_pdf.stem}.docx"
        ok = export_docx(
            reports,
            tmp_docx,
            title=title,
            tree=tree,
            sections=sections,
            layout=layout,
        )
        if not ok or not tmp_docx.is_file():
            return False

        proc = subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_path),
                str(tmp_docx),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        generated_pdf = tmp_path / f"{target_pdf.stem}.pdf"
        if proc.returncode != 0 or not generated_pdf.is_file():
            return False

        shutil.move(str(generated_pdf), str(target_pdf))

    return target_pdf.is_file()