# app/commands/polygon_commands.py
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.commands.base import Command, CommandMeta, CommandResult, get_current_app
from core.units import Dimension, UnitSystem, convert_value
from data.enums import DistType, LoadDirection, PolygonType
from domain.definition import AreaUniformLoad, FrameDistributedLoad
from plane.plane import Plane
from tools.area_to_frame import AreaToFrame, TransferBatch
from tools.polygon_load_transfer import merge_frame_distributed_loads


@dataclass
class SetPolygonType(Command):
    polygon_ids: list[int] = None
    poly_type: PolygonType = PolygonType.GENERIC

    def __post_init__(self) -> None:
        self._app = None
        self._before = []

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        self._before = []
        for pid in self.polygon_ids or []:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                self._before.append((pid, poly.poly_type))
                poly.poly_type = self.poly_type
                poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(handled=True, geometry_dirty=True)

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        for pid, old_type in self._before:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                poly.poly_type = old_type
                poly.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class SetPolygonDistType(Command):
    polygon_ids: list[int] = None
    dist_type: DistType = DistType.TWO_WAY

    def __post_init__(self) -> None:
        self._app = None
        self._before = []

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        self._before = []
        for pid in self.polygon_ids or []:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                self._before.append((pid, poly.dist_type))
                poly.set_dist_type(self.dist_type)
                poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(handled=True, geometry_dirty=True)

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        for pid, old_dist in self._before:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                poly.set_dist_type(old_dist)
                poly.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class SetPolygonColor(Command):
    polygon_ids: list[int] = None
    color: list[float] = None

    def __post_init__(self) -> None:
        self._app = None
        self._before = []

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        self._before = []
        for pid in self.polygon_ids or []:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                self._before.append((pid, list(poly.color)))
                poly.color = list(self.color)
                poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(handled=True, geometry_dirty=True)

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        for pid, old_color in self._before:
            poly = project.polygons.get(int(pid))
            if poly is not None:
                poly.color = list(old_color)
                poly.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class PolygonToPlane(Command):
    polygon_id: int = 0

    def __post_init__(self) -> None:
        self._app = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return CommandResult(handled=False, message="Polygon yok.", level="warn")
        plane = Plane.from_element(poly, name=f"Plane_Polygon_{poly.unique_id}")
        if self._app.engine and hasattr(self._app.engine, "math_model"):
            plane.fit_to_math_model(self._app.engine.math_model)
        project.add_plane(plane)
        project.activate_plane(plane)
        return CommandResult(
            handled=True,
            project_dirty=True,
            message=f"{plane.name} düzlemi oluşturuldu ve aktif edildi.",
            level="success",
        )

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        project.remove_plane(f"Plane_Polygon_{self.polygon_id}")


@dataclass
class ApplyPolygonAssoc(Command):
    polygon_id: int = 0
    associated: set[int] = None
    excluded: set[int] = None

    def __post_init__(self) -> None:
        self._app = None
        self._before_associated = set()
        self._before_excluded = set()
        self._before_frame_ids = []

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return CommandResult(handled=False, message="Polygon yok.", level="warn")
        ad = project.polygon_analysis_data(poly)
        self._before_associated = set(poly.associated)
        self._before_excluded = set(poly.excluded)
        self._before_frame_ids = list(ad.associated_frame_ids)
        poly.associated = set(self.associated or ())
        poly.excluded = set(self.excluded or ())
        poly.association_revision += 1
        ad.associated_frame_ids = sorted(poly.associated)
        poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(
            handled=True,
            geometry_dirty=True,
            message=f"{len(poly.associated)} frame assoc uygulandı.",
            level="success",
        )

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        poly = project.polygons.get(int(self.polygon_id))
        if poly is not None:
            ad = project.polygon_analysis_data(poly)
            poly.associated = set(self._before_associated)
            poly.excluded = set(self._before_excluded)
            poly.association_revision += 1
            ad.associated_frame_ids = list(self._before_frame_ids)
            poly.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class AssignPolygonAreaLoad(Command):
    polygon_id: int = 0
    pattern_name: str = ""
    value_kn: float = 0.0
    direction: LoadDirection = LoadDirection.GRAVITY
    source_name: str = ""

    def __post_init__(self) -> None:
        self._app = None
        self._index = -1

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None or self.pattern_name not in project.load_patterns:
            return CommandResult(handled=False, message="Polygon veya pattern yok.", level="warn")
        direction = self.direction
        if isinstance(direction, str):
            direction = LoadDirection[direction]
        val = float(
            convert_value(
                Dimension.AREA_LOAD,
                float(self.value_kn),
                UnitSystem.KN_M,
                project.unit_system,
            )
        )
        ad = project.polygon_analysis_data(poly)
        ad.assigned_loads.append(
            AreaUniformLoad(
                pattern_name=self.pattern_name,
                direction=direction,
                value=val,
                source_name=self.source_name,
            )
        )
        self._index = len(ad.assigned_loads) - 1
        project.math_model.mark_dirty()
        return CommandResult(
            handled=True,
            message=f"{self.pattern_name} ({self.value_kn:.2f} kN/m²) atandı.",
            level="success",
        )

    def undo(self) -> None:
        if self._app is None:
            return
        project = self._app.current_project
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return
        ad = project.polygon_analysis_data(poly)
        if 0 <= self._index < len(ad.assigned_loads):
            ad.assigned_loads.pop(self._index)
        project.math_model.mark_dirty()


@dataclass
class RemovePolygonAreaLoad(Command):
    polygon_id: int = 0
    index: int = 0

    def __post_init__(self) -> None:
        self._app = None
        self._removed = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return CommandResult(handled=False, message="Polygon yok.", level="warn")
        ad = project.polygon_analysis_data(poly)
        if not (0 <= self.index < len(ad.assigned_loads)):
            return CommandResult(handled=False, message="Geçersiz index.", level="warn")
        self._removed = ad.assigned_loads.pop(self.index)
        poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(handled=True)

    def undo(self) -> None:
        if self._app is None or self._removed is None:
            return
        project = self._app.current_project
        poly = project.polygons.get(int(self.polygon_id))
        if poly is not None:
            ad = project.polygon_analysis_data(poly)
            ad.assigned_loads.insert(self.index, self._removed)
            poly.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class SetTransferGridSettings(Command):
    step: float = 200.0
    n_bins: int = 12

    def __post_init__(self) -> None:
        self._app = None
        self._before = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        service = AreaToFrame(project)
        self._before = service.get_grid_settings()
        service.set_grid_settings(self.step, self.n_bins)
        return CommandResult(handled=True, message="Grid ayarları güncellendi.", level="info")

    def undo(self) -> None:
        if self._app is None or self._before is None:
            return
        project = getattr(self._app, "current_project", None)
        if project is not None:
            AreaToFrame(project).set_grid_settings(*self._before)


@dataclass
class ResetWindZoneOverride(Command):
    polygon_id: int = 0
    direction_key: str = ""
    zone_index: int = 0

    def __post_init__(self) -> None:
        self._app = None
        self._before = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return CommandResult(handled=False, message="Polygon yok.", level="warn")
        zones = (poly.zone_children_by_direction or {}).get(self.direction_key, [])
        if not (0 <= self.zone_index < len(zones)):
            return CommandResult(handled=False, message="Geçersiz zone index.", level="warn")
        zone = zones[self.zone_index]
        self._before = (zone.get("cpe10_override"), zone.get("cpe1_override"))
        zone["cpe10_override"] = None
        zone["cpe1_override"] = None
        poly.mark_dirty()
        project.math_model.mark_dirty()
        return CommandResult(handled=True, message="Zone override sıfırlandı.", level="info")

    def undo(self) -> None:
        if self._app is None or self._before is None:
            return
        project = getattr(self._app, "current_project", None)
        if project is None:
            return
        poly = project.polygons.get(int(self.polygon_id))
        if poly is None:
            return
        zones = (poly.zone_children_by_direction or {}).get(self.direction_key, [])
        if 0 <= self.zone_index < len(zones):
            zones[self.zone_index]["cpe10_override"] = self._before[0]
            zones[self.zone_index]["cpe1_override"] = self._before[1]
            poly.mark_dirty()
            project.math_model.mark_dirty()


@dataclass
class ApplyFrameTransferAction(Command):
    staged_loads: dict[int, dict[str, FrameDistributedLoad]] = None
    mode: str = "replace"

    def __post_init__(self) -> None:
        self._app = None
        self._snapshot: dict[int, dict[str, Any]] = {}

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None or not self.staged_loads:
            return CommandResult(handled=False, message="Aktarım verisi yok.", level="warn")
        frames = project.math_model.frames
        self._snapshot = {}
        for fid in self.staged_loads:
            frame = frames.get(int(fid))
            if frame is not None:
                self._snapshot[int(fid)] = deepcopy(frame.dist_load_sets)
        touched = merge_frame_distributed_loads(project.math_model, self.staged_loads, self.mode)
        project.math_model.mark_dirty()
        return CommandResult(
            handled=True,
            geometry_dirty=True,
            message=f"{len(touched)} frame güncellendi ({self.mode}).",
            level="success",
        )

    def undo(self) -> None:
        if self._app is None or not self._snapshot:
            return
        project = getattr(self._app, "current_project", None)
        if project is None:
            return
        frames = project.math_model.frames
        for fid, prev_sets in self._snapshot.items():
            frame = frames.get(int(fid))
            if frame is not None:
                frame.dist_load_sets = deepcopy(prev_sets)
                frame.mark_dirty()
        project.math_model.mark_dirty()


@dataclass
class CommitFrameTransferBatch(Command):
    batch: TransferBatch = None

    def __post_init__(self) -> None:
        self._app = None
        self._snapshot: dict[int, dict[str, Any]] = {}

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None or self.batch is None:
            return CommandResult(handled=False, message="Aktarım verisi yok.", level="warn")
        frames = project.math_model.frames
        self._snapshot = {}
        for fid in self.batch.staged_loads:
            frame = frames.get(int(fid))
            if frame is not None:
                self._snapshot[int(fid)] = deepcopy(frame.dist_load_sets)
        touched = AreaToFrame(project).commit_batch(self.batch)
        return CommandResult(
            handled=True,
            geometry_dirty=True,
            message=f"{len(touched)} frame güncellendi ({self.batch.mode}).",
            level="success",
        )

    def undo(self) -> None:
        if self._app is None or not self._snapshot:
            return
        project = getattr(self._app, "current_project", None)
        if project is None:
            return
        frames = project.math_model.frames
        for fid, prev_sets in self._snapshot.items():
            frame = frames.get(int(fid))
            if frame is not None:
                frame.dist_load_sets = deepcopy(prev_sets)
                frame.mark_dirty()
        project.math_model.mark_dirty()


_META_BY_TYPE: dict[type, CommandMeta] = {
    SetPolygonType: CommandMeta(
        label="Polygon Tipi",
        category="Polygon",
        tooltip="Seçili polygon'ların tipini değiştir",
        visible_in_ui=False,
    ),
    SetPolygonDistType: CommandMeta(
        label="Yük Dağıtım Yönü",
        category="Polygon",
        tooltip="Seçili polygon'ların dağıtım yönünü değiştir",
        visible_in_ui=False,
    ),
    SetPolygonColor: CommandMeta(
        label="Polygon Rengi",
        category="Polygon",
        visible_in_ui=False,
    ),
    PolygonToPlane: CommandMeta(
        label="Plane'e Dönüştür",
        category="Polygon",
        visible_in_ui=False,
    ),
    ApplyPolygonAssoc: CommandMeta(
        label="Frame Assoc Uygula",
        category="Polygon",
        visible_in_ui=False,
    ),
    AssignPolygonAreaLoad: CommandMeta(
        label="Alan Yükü Ata",
        category="Polygon",
        visible_in_ui=False,
    ),
    RemovePolygonAreaLoad: CommandMeta(
        label="Alan Yükü Sil",
        category="Polygon",
        visible_in_ui=False,
    ),
    SetTransferGridSettings: CommandMeta(
        label="Transfer Grid Ayarları",
        category="Polygon",
        visible_in_ui=False,
    ),
    ResetWindZoneOverride: CommandMeta(
        label="Rüzgar Zone Override Sıfırla",
        category="Polygon",
        visible_in_ui=False,
    ),
    ApplyFrameTransferAction: CommandMeta(
        label="Frame Yük Aktarımı Uygula",
        category="Polygon",
        visible_in_ui=False,
    ),
    CommitFrameTransferBatch: CommandMeta(
        label="Frame Yük Aktarımını Uygula",
        category="Polygon",
        visible_in_ui=False,
    ),
}


_ALL_TYPES: list[type] = [
    SetPolygonType,
    SetPolygonDistType,
    SetPolygonColor,
    PolygonToPlane,
    ApplyPolygonAssoc,
    AssignPolygonAreaLoad,
    RemovePolygonAreaLoad,
    SetTransferGridSettings,
    ResetWindZoneOverride,
    ApplyFrameTransferAction,
    CommitFrameTransferBatch,
]


def register(registry) -> None:
    for cmd_type in _ALL_TYPES:
        registry.register(cmd_type, _META_BY_TYPE.get(cmd_type))