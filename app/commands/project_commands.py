# app/commands/project_commands.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Union

@dataclass
class OpenPanel:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass
class ClosePanel:
    name: str

@dataclass
class TogglePanel:
    name: str
    
# ---- Tanım container'ları ----
@dataclass
class ReplicateSelected:
    dx: float
    dy: float
    dz: float
    count: int = 1

@dataclass
class AddDefinition:
    container_attr: str
    name: str
    obj: Any


@dataclass
class UpdateDefinition:
    container_attr: str
    name: str
    changes: dict[str, Any]
    new_name: str | None = None


@dataclass
class RemoveDefinition:
    container_attr: str
    name: str


@dataclass
class RenameDefinition:
    container_attr: str
    old_name: str
    new_name: str


# ---- Element ----
@dataclass
class UpdateElementFields:
    element_uid: int
    changes: dict[str, Any]


@dataclass
class DeleteElements:
    uids: list[int]


@dataclass
class AddNode:
    x: float
    y: float
    z: float
    label: str = ""
    restraint: Any = None


@dataclass
class AddFrame:
    node_i_uid: int
    node_j_uid: int
    section_name: str
    rotation_deg: float = 0.0
    label: str = ""


# ---- Proje seviyesi ----
@dataclass
class ReplaceProject:
    project: Any
    label: str = ""


@dataclass
class SetUnitSystem:
    unit_system: Any
    reason: str = "ui"


# ---- Engine actions ----
@dataclass
class FitView: pass


@dataclass
class ZoomExtents: pass


@dataclass
class SetCameraPreset:
    preset: str


@dataclass
class Toggle2D: pass


@dataclass
class ToggleLoadsVisible:
    enabled: bool | None = None


@dataclass
class ToggleLocalAxes: pass


@dataclass
class ClearSelection: pass


@dataclass
class SelectElements:
    uids: list[int]
    mode: Literal["replace", "add", "toggle"] = "replace"


@dataclass
class RefreshGeometry: pass


@dataclass
class ShowOnly:
    uids: list[int] | None


@dataclass
class HideElements:
    uids: list[int]


@dataclass
class ShowEntireModel: pass

@dataclass
class OpenInspector: pass

@dataclass
class ToggleRenderFlag:
    flag: str        # "grid", "polygon", "lines", "labels", "wireframe", ...
    value: bool

@dataclass
class SetRenderMode:
    mode: str        # "shaded", "simple"

@dataclass
class ToggleRenderMode:
    pass


@dataclass
class DeleteSelected:
    pass


@dataclass
class StartDrawTool:
    mode: str = "line"

@dataclass
class CommitDrawnElement:
    element: Any
    
@dataclass
class StartPlaneTool:
    pass


@dataclass
class Undo:
    pass


@dataclass
class Redo:
    pass

@dataclass
class HoverChanged:
    pick_id: int = 0

@dataclass
class NewProject: pass

@dataclass
class OpenProject:
    path: str

@dataclass
class SaveProject:
    path: str | None = None  # None → mevcut yol

@dataclass
class SaveProjectAs:
    path: str

@dataclass
class CloseProject: pass

@dataclass
class ImportS2K:
    path: str
    mode: str = "import"

@dataclass
class ExportS2K:
    path: str

@dataclass
class QuitApp: pass

@dataclass
class StartPlane3pt: pass

@dataclass
class StartPlane2ptZ: pass

@dataclass
class ConvertFramesToLinks:
    link_prop_name: str = "DefaultLink"
    delete_original: bool = True

@dataclass
class PropagateGeometryChange:
    node_uids: list[int] = field(default_factory=list)