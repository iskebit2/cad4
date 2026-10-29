# geometry/scenebuilder.py
"""ProjectBuilder'ın alt katmanı — primitive yaratım.

S2K parse/bağlama işleri `tools/s2k/scene_builder.py`'da.
Bu sınıf sadece Node/Frame/Area/Link/Material/Section/LinkProp yaratır.
"""
from __future__ import annotations

from data.enums import LinkPropType, MatType, SectionType
from domain.definition import (
    LinkProp,
    LinkPropLinear,
    Material,
    Restraint,
    Section,
)
from domain.element import Area, Frame, Link, Node
from domain.project import Project
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class SceneBuilder:
    def __init__(self, project: Project):
        self.project = project
        self.scene = project.scene
        self._node_cache: dict[str, Node] = {}

    # ------------------------------------------------------------------
    # MATERIAL / SECTION / LINKPROP
    # ------------------------------------------------------------------
    def create_material(
        self, name: str, mat_type: MatType,
        E: float = 2.0e8, density: float = 7850,
        color: tuple[float, float, float] = (0.8, 0.8, 0.8),
    ) -> Material:
        material = Material(
            name=name, mat_type=mat_type, E1=E,
            density=density, color=color,
        )
        self.project.add_material(material)
        return material

    def create_section(
        self, name: str, profile_type: SectionType,
        profile_params: dict[str, float],
        material: Material | None = None,
        color: tuple[float, float, float] = (0.8, 0.8, 0.8),
    ) -> Section:
        section = Section(
            name=name, profile_type=profile_type,
            profile_params=profile_params,
            material=material, color=color,
        )
        self.project.add_section(section)
        return section

    def create_link_prop(
        self, name: str, prop_type: LinkPropType = LinkPropType.LINEAR,
        Ke: dict | None = None, Ce: dict | None = None,
    ) -> LinkProp:
        if prop_type == LinkPropType.LINEAR:
            prop = LinkPropLinear(name=name, Ke=Ke, Ce=Ce)
        else:
            prop = LinkProp(name=name, prop_type=prop_type)
        self.project.add_link_prop(prop)
        return prop

    # ------------------------------------------------------------------
    # NODE
    # ------------------------------------------------------------------
    def create_node(
        self, x: float, y: float, z: float,
        label: str = "",
        restraint: dict[str, bool] | Restraint | None = None,
    ) -> Node:
        restraint_obj = Restraint(**restraint) if isinstance(restraint, dict) else restraint
        node = Node(x, y, z, label, restraint_obj)
        self.scene.add_node(node)
        if label:
            self._node_cache[label] = node
        return node

    # ------------------------------------------------------------------
    # FRAME
    # ------------------------------------------------------------------
    def create_frame(
        self, node_i: Node | str, node_j: Node | str, section_name: str,
        rotation_deg: float = 0.0, label: str = "",
    ) -> Frame:
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]

        section = self.project.get_section_by_name(section_name)
        if section is None:
            raise ValueError(f"Section '{section_name}' not found in Project!")

        frame = Frame(
            node_i=node_i, node_j=node_j, section=section,
            rotation_deg=rotation_deg, label=label,
        )
        self.scene.add_frame(frame)
        return frame

    # ------------------------------------------------------------------
    # AREA
    # ------------------------------------------------------------------
    def create_area(
        self, nodes: list, thickness: float, label: str = "",
    ) -> Area:
        area_nodes = [
            self._node_cache[n] if isinstance(n, str) else n
            for n in nodes
        ]
        area = Area(area_nodes, thickness, label)
        self.scene.add_area(area)
        return area

    # ------------------------------------------------------------------
    # LINK
    # ------------------------------------------------------------------
    def create_link(
        self, node_i: Node | str, node_j: Node | str,
        prop_name: str = "LINK1", label: str = "",
    ) -> Link:
        if isinstance(node_i, str):
            node_i = self._node_cache[node_i]
        if isinstance(node_j, str):
            node_j = self._node_cache[node_j]

        link = Link(node_i, node_j, prop_name, label)
        self.scene.add_link(link)
        return link