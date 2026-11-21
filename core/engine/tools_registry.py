# core/engine/tools_registry.py
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from core.selection_manager import SelectionManager
from core.selection_policy import SelectionPolicy
from core.marquee_selector import MarqueeSelector
from app.commands.edit_controller import EditController
from tools.draw_manager import DrawManager
from plane.plane_creation_tool import PlaneCreationTool
from render.snapsquare import SnapSquareRenderer

if TYPE_CHECKING:
    from core.engine import Engine


class ToolsRegistry:
    """Engine araçlarını DI ile kurar. Test'te fake fabrikalar geçirilebilir."""

    def __init__(self, engine: "Engine") -> None:
        self.engine = engine
        self.sel_policy = None
        self.sel_mgr = None
        self.marquee = None
        self.edit = None
        self.draw_mgr = None
        self.plane_draw_mgr = None
        self.snap = None

        # Varsayılan fabrikalar (test'te override edilir)
        self._factory_sel_policy: Callable = SelectionPolicy
        self._factory_sel_mgr: Callable = SelectionManager
        self._factory_marquee: Callable = MarqueeSelector
        self._factory_edit: Callable = EditController
        self._factory_draw_mgr: Callable = DrawManager
        self._factory_plane_draw_mgr: Callable = PlaneCreationTool
        self._factory_snap: Callable = SnapSquareRenderer

    def build(self) -> None:
        eng = self.engine
        self.sel_policy = self._factory_sel_policy(eng.input)
        self.sel_mgr = self._factory_sel_mgr(eng.pipeline.renderer)
        self.marquee = self._factory_marquee(eng, self.sel_mgr, self.sel_policy)
        self.edit = self._factory_edit(eng)
        self.draw_mgr = self._factory_draw_mgr(eng)
        eng.input.register(self.draw_mgr)
        self.plane_draw_mgr = self._factory_plane_draw_mgr(eng)
        self.snap = self._factory_snap()

    def tick(self) -> None:
        pass