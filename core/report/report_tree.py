# core/report/report_tree.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from core.report.report_dataframe import ReportDataFrame
from data.enums import MatType


class SectionStatus(str, Enum):
    READY = "ready"
    MISSING_DATA = "missing_data"
    NOT_RUN = "not_run"


@dataclass
class ReportSection:
    section_id: str
    title: str
    status: SectionStatus
    frames: list[ReportDataFrame] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    children: list[ReportSection] = field(default_factory=list)


@dataclass
class ReportTreeNode:
    node_id: str
    title: str
    section_id: str
    status: SectionStatus
    enabled: bool = True
    children: list[ReportTreeNode] = field(default_factory=list)


@dataclass
class ReportTree:
    nodes: list[ReportTreeNode] = field(default_factory=list)


@dataclass
class PageLayoutConfig:
    page_break_before_main_sections: bool = False
    page_break_before_material_modules: bool = True
    default_image_width_cm: float = 15.0


class SectionBuilder(Protocol):
    section_id: str
    title: str

    def is_applicable(self, project: Any, context: Any) -> bool: ...
    def build(self, project: Any, context: Any) -> ReportSection: ...


MATERIAL_MODULE_ORDER: tuple[tuple[str, str, MatType], ...] = (
    ("steel_module", "Çelik Yapı Modülü", MatType.STEEL),
    ("concrete_module", "Betonarme Yapı Modülü", MatType.CONCRETE),
    ("timber_module", "Ahşap Yapı Modülü", MatType.TIMBER),
    ("masonry_module", "Yığma Yapı Modülü", MatType.MASONRY),
)


def _resolve_mat_type(raw_mat: Any) -> MatType | None:
    if raw_mat is None:
        return None
    if isinstance(raw_mat, MatType):
        return raw_mat
    raw_type = getattr(raw_mat, "mat_type", None)
    if isinstance(raw_type, MatType):
        return raw_type
    if raw_type is not None:
        return MatType.from_sap(raw_type)
    return None


def _frame_material(frame: Any, project: Any) -> Any:
    sec = getattr(frame, "section", None)
    if sec is not None and getattr(sec, "material", None) is not None:
        return sec.material
    if isinstance(sec, str) and hasattr(project, "sections"):
        resolved_sec = project.sections.get(sec)
        if resolved_sec is not None and getattr(resolved_sec, "material", None) is not None:
            return resolved_sec.material
    return None


def _area_material(area: Any, project: Any) -> Any:
    if getattr(area, "material", None) is not None:
        return area.material
    area_sec = getattr(area, "area_section", None)
    if area_sec is not None and getattr(area_sec, "material", None) is not None:
        return area_sec.material
    sec_name = getattr(area, "section_name", "")
    if sec_name and hasattr(project, "area_sections"):
        resolved_sec = project.area_sections.get(sec_name)
        if resolved_sec is not None and getattr(resolved_sec, "material", None) is not None:
            return resolved_sec.material
    return None


def collect_active_material_types(project: Any) -> set[MatType]:
    active: set[MatType] = set()
    math_model = getattr(project, "math_model", None)
    if math_model is None:
        return active

    for frame in getattr(math_model, "frames", {}).values():
        mat = _frame_material(frame, project)
        mtype = _resolve_mat_type(mat)
        if mtype is not None:
            active.add(mtype)

    for area in getattr(math_model, "areas", {}).values():
        mat = _area_material(area, project)
        mtype = _resolve_mat_type(mat)
        if mtype is not None:
            active.add(mtype)

    return active


class ReportTreeBuilder:
    def __init__(self, builders: list[SectionBuilder] | None = None) -> None:
        self._builders: list[SectionBuilder] = list(builders) if builders is not None else []

    def build_tree(self, sections: list[ReportSection]) -> ReportTree:
        nodes: list[ReportTreeNode] = []
        for sec in sections:
            children = [
                ReportTreeNode(
                    node_id=f"{sec.section_id}.{child.section_id}",
                    title=child.title,
                    section_id=child.section_id,
                    status=child.status,
                    enabled=True,
                )
                for child in sec.children
            ]
            nodes.append(
                ReportTreeNode(
                    node_id=sec.section_id,
                    title=sec.title,
                    section_id=sec.section_id,
                    status=sec.status,
                    enabled=True,
                    children=children,
                )
            )
        return ReportTree(nodes=nodes)

    def build_sections(self, project: Any, context: Any = None) -> tuple[list[ReportSection], ReportTree]:
        produced: list[ReportSection] = []
        for builder in self._builders:
            if builder.is_applicable(project, context):
                produced.append(builder.build(project, context))
        tree = self.build_tree(produced)
        return produced, tree