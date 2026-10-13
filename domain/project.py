# domain/project.py
from dataclasses import dataclass, field
import json
import zipfile
from pathlib import Path

from domain.element import Area, Frame, Link, Node, Polygon
from domain.scene import Scene
from domain.definition_manager import DefinitionManager
from domain.definition import (
    AnalysisManager, GeneralProjectInfo, LoadManager, ProjectConfig, ProjectInfo,
    ReportManager, SerializableData, SiteInformation,
)
from domain.serialization import dumps_pretty


@dataclass
class Project(SerializableData):
    info: ProjectInfo = field(default_factory=ProjectInfo)
    general_info: GeneralProjectInfo = field(default_factory=GeneralProjectInfo)
    site_info: SiteInformation = field(default_factory=SiteInformation)
    config: ProjectConfig = field(default_factory=ProjectConfig)
    definitions: DefinitionManager = field(default_factory=DefinitionManager)
    scene: Scene = field(default_factory=Scene)
    loads: LoadManager = field(default_factory=LoadManager)
    analysis: AnalysisManager = field(default_factory=AnalysisManager)
    report: ReportManager = field(default_factory=ReportManager)

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        def _ser(obj, fallback=None):
            if obj is None:
                return fallback if fallback is not None else {}
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            return fallback if fallback is not None else {}

        scene_dict = _ser(self.scene)
        scene_dict["polygons"] = [
            p for p in scene_dict.get("polygons", [])
            if not p.get("is_temporary", False)
        ]

        return {
            "info":         _ser(self.info),
            "general_info": _ser(self.general_info),
            "site_info":    _ser(self.site_info),
            "config":       _ser(self.config),
            "definitions":  _ser(self.definitions),
            "scene":        scene_dict,
            "loads":        _ser(self.loads),
            "analysis":     _ser(self.analysis),
            "report":       _ser(self.report),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        project = cls()

        project.info         = ProjectInfo.from_dict(data.get("info", {}))
        project.general_info = GeneralProjectInfo.from_dict(data.get("general_info", {}))
        project.site_info    = SiteInformation.from_dict(data.get("site_info", {}))

        defs_data = data.get("definitions", {})
        project.definitions = (
            DefinitionManager.from_dict(defs_data)
            if defs_data else DefinitionManager()
        )

        if data.get("config"):
            project.config = ProjectConfig.from_dict(data["config"])
        if data.get("loads"):
            project.loads = LoadManager.from_dict(data["loads"])
        if data.get("analysis"):
            project.analysis = AnalysisManager.from_dict(data["analysis"])
        if data.get("report"):
            project.report = ReportManager.from_dict(data["report"])

        scene_data = data.get("scene", {})
        project.scene = Scene.from_dict(scene_data, project.definitions)
        project.scene.def_mgr = project.definitions

        return project

    # ------------------------------------------------------------------
    # FILE I/O
    # ------------------------------------------------------------------
    def save(self, filepath: str):
        path = Path(filepath)
        if path.suffix != ".cd4":
            path = path.with_suffix(".cd4")

        data = self.to_dict()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", dumps_pretty(data))

    @classmethod
    def load(cls, filepath: str) -> "Project":
        path = Path(filepath)
        if not path.exists():
            return cls()

        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("project.json").decode("utf-8")
        data = json.loads(content)
        return cls.from_dict(data)


if __name__ == "__main__":
    from logging_config import CadLogger
    logger = CadLogger.get(__name__)

    import os
    from tools.s2kloader import S2KLoader

    loader = S2KLoader(file_path=os.path.join('examples', 'model3d.s2k'))
    project = loader.load()

    logger.info(
        "[Project] "
        f"{len(project.scene.nodes)} node, "
        f"{len(project.scene.frames)} frame, "
        f"{len(project.scene.areas)} area, "
        f"{len(project.scene.links)} link, "
        f"{len(project.definitions.materials)} materials, "
        f"{len(project.definitions.sections)} sections, "
        f"{len(project.definitions.link_props)} link_props, "
        f"{len(project.definitions.load_patterns)} load_patterns, "
        f"{len(project.definitions.section_cuts)} section_cuts, "
        f"{len(project.definitions.auto_seismics)} auto_seismics, "
        f"{len(project.definitions.spectrum_functions)} spectrum_functions, "
        f"{len(project.definitions.response_spectrum_cases)} response_spectrum_cases, "
        f"{len(project.definitions.mass_source_map)} mass_source_map, "
        f"{len(project.definitions.load_cases)} load_cases, "
        f"{len(project.definitions.modal_cases)} modal_cases, "
        f"{len(project.definitions.combinations)} combinations, "
    )

    project.save("test_proje2.cd4")

    # Round-trip testi
    loaded = Project.load("test_proje2.cd4")
    logger.info(
        f"[Round-trip] "
        f"{len(loaded.scene.nodes)} node, "
        f"{len(loaded.scene.frames)} frame, "
        f"{len(loaded.definitions.sections)} section"
    )