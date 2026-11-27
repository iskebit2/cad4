# ui/panels/polygon/assign_load_tab.py
from __future__ import annotations

from imgui_bundle import imgui
import app.commands as cmd
from app.commands import polygon_commands as PLC
from data.enums import _AREA_LOAD_DIRECTION_LABELS, _AREA_LOAD_DIRECTION_VALUES, LoadDirection
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame
from ui.base.inspector_panel import InspectorContext


class AssignLoadTab:
    def __init__(self) -> None:
        self._pattern_idx: int = 0
        self._dir_idx: int = 0
        self._value_kn: float = 0.0
        self._label: str = ""
        self._step_buf: float | None = None
        self._bins_buf: int | None = None

    def draw(self, ctx: InspectorContext, polygon: Polygon, service: AreaToFrame) -> None:
        imgui.spacing()
        patterns = sorted(ctx.project.load_patterns.keys()) if ctx.project else []
        if not patterns:
            imgui.text_disabled("Projede yük pattern'i yok.")
            return

        if self._pattern_idx >= len(patterns):
            self._pattern_idx = 0

        imgui.push_item_width(-1)
        _, self._pattern_idx = imgui.combo("##sp_pat", self._pattern_idx, patterns)
        _, self._dir_idx = imgui.combo("##sp_dir", self._dir_idx, list(_AREA_LOAD_DIRECTION_LABELS))
        _, self._value_kn = imgui.input_float("Değer (kN/m²)##sp_val", self._value_kn, 0.0, 0.0, "%.3f")
        _, self._label = imgui.input_text("Açıklama##sp_lbl", self._label)
        imgui.pop_item_width()

        if imgui.button("Poligona Yük Ata##sp_add_load", imgui.ImVec2(-1, 28)):
            ctx.app.put_command(
                cmd.AssignPolygonAreaLoad(
                    polygon_id=int(polygon.unique_id),
                    pattern_name=patterns[self._pattern_idx],
                    value_kn=float(self._value_kn),
                    direction=_AREA_LOAD_DIRECTION_VALUES[self._dir_idx],
                    source_name=self._label,
                )
            )

        imgui.separator()
        if imgui.collapsing_header("Grid Ayarları##sp_grid"):
            step, bins = service.get_grid_settings()
            if self._step_buf is None:
                self._step_buf = step
            if self._bins_buf is None:
                self._bins_buf = bins
            _, self._step_buf = imgui.input_float(f"Adım ({service.length_unit()})##sp_gstep", self._step_buf)
            _, self._bins_buf = imgui.input_int("Bin Sayısı##sp_gbins", self._bins_buf)
            if imgui.button("Grid Kaydet##sp_gsave", imgui.ImVec2(-1, 0)):
                ctx.app.put_command(
                    cmd.SetTransferGridSettings(float(self._step_buf), int(self._bins_buf))
                )