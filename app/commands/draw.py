# app/commands/draw.py
from __future__ import annotations

from typing import Any

from app.commands import project_commands as PC
from app.commands.base import Command
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from domain.line import Line
from domain.polygon import Polygon


class AddDrawnElementCommand(Command):
    """
    DrawManager tarafından üretilen Line veya Polygon nesnesini
    projeye ekler ve Undo/Redo geçmişine kaydeder.
    """

    def __init__(self, project, engine, element: Any) -> None:
        self.project = project
        self.engine = engine
        self.element = element

    def execute(self) -> None:
        if isinstance(self.element, Line):
            self.project.add_line(self.element)
        elif isinstance(self.element, Polygon):
            self.project.add_polygon(self.element)
        else:
            raise TypeError(f"Desteklenmeyen çizim elemanı: {type(self.element).__name__}")
        self._sync_view()

    def undo(self) -> None:
        if isinstance(self.element, Line):
            if hasattr(self.project, "remove_line"):
                self.project.remove_line(self.element)
            elif hasattr(self.project, "lines"):
                self.project.lines.pop(getattr(self.element, "unique_id", None), None)
        elif isinstance(self.element, Polygon):
            if hasattr(self.project, "remove_polygon"):
                self.project.remove_polygon(self.element)
            elif hasattr(self.project, "polygons"):
                self.project.polygons.pop(getattr(self.element, "unique_id", None), None)
        self._sync_view()

    def _sync_view(self) -> None:
        if self.engine is None:
            return
        self.engine.update_geo(self.project)
        pr = getattr(self.engine, "presentation_renderer", None)
        if pr is not None and hasattr(self.project, "polygons"):
            pr.update_polygons(list(self.project.polygons.values()))

    @property
    def name(self) -> str:
        return f"Draw({type(self.element).__name__})"


# ------------------------------------------------------------------
# Komut İşleyicileri (CommandRegistry)
# ------------------------------------------------------------------

@command(PC.StartDrawTool)
def _start_draw(app, cmd: PC.StartDrawTool) -> CommandResult:
    eng = app.engine
    if eng is None or eng.draw_mgr is None:
        return CommandResult(handled=False)

    mode_map = {
        "line": "line",
        "poly": "sequential",
        "polygon": "sequential",
        "sequential": "sequential",
        "rect": "rectangle",
        "rectangle": "rectangle",
        "single": "single_point",
        "single_point": "single_point",
    }
    mode = mode_map.get(cmd.mode.lower().strip())
    if mode is None:
        return CommandResult(
            handled=True,
            message=f"Geçersiz çizim modu: '{cmd.mode}' (line, poly, rect, single)",
            level="warn",
        )

    eng.draw_mgr.start(mode=mode)
    return CommandResult(
        handled=True,
        message=f"Çizim modu aktif: {mode} (Bitir: Enter/C, İptal: Esc)",
        level="info",
    )


@command(PC.CommitDrawnElement)
def _commit_drawn(app, cmd: PC.CommitDrawnElement) -> CommandResult:
    eng = app.engine
    ctrl = app.edit_controller
    project = app.project_service.project
    if eng is None or ctrl is None or project is None or cmd.element is None:
        return CommandResult(handled=False)

    undo_cmd = AddDrawnElementCommand(project=project, engine=eng, element=cmd.element)
    if not ctrl.commands.execute(undo_cmd):
        return CommandResult(handled=True, message="Çizim kaydedilemedi.", level="warn")

    if eng.sel_mgr is not None:
        eng.sel_mgr.select(cmd.element)

    return CommandResult(
        handled=True,
        geometry_dirty=True,
        message=f"{type(cmd.element).__name__} oluşturuldu.",
        level="success",
    )


# ------------------------------------------------------------------
# Terminal (CommandPanel) Kısayol Komutları
# ------------------------------------------------------------------

@factory("draw")
def _f_draw(args: list[str]):
    mode = args[0] if args else "line"
    return PC.StartDrawTool(mode=mode)


@factory("draw_line")
def _f_draw_line(args: list[str]):
    return PC.StartDrawTool(mode="line")


@factory("draw_poly")
def _f_draw_poly(args: list[str]):
    return PC.StartDrawTool(mode="sequential")


@factory("draw_rect")
def _f_draw_rect(args: list[str]):
    return PC.StartDrawTool(mode="rectangle")