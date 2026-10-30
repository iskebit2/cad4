# ui/widgets/plane_2d_tools.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from imgui_bundle import imgui


class ToolKind(Enum):
    SELECT = auto()
    DRAW_LINE = auto()
    DRAW_POLY = auto()
    DRAW_AREA = auto()
    PLACE_JOINT_LOAD = auto()
    PLACE_DIST_LOAD = auto()
    PLACE_AREA_LOAD = auto()
    MEASURE = auto()
    ANNOTATE = auto()


@dataclass
class ToolContext:
    mouse_uv: tuple[float, float] | None
    snap_uv: tuple[float, float] | None
    mods: tuple[bool, bool]
    hover: tuple[str, int] | None
    zoom: float


class Tool(Protocol):
    kind: ToolKind

    def on_click(self, ctx: ToolContext, scene, plane) -> bool: ...
    def on_move(self, ctx: ToolContext, scene, plane) -> None: ...
    def on_right_click(self, ctx: ToolContext) -> None: ...
    def draw_preview(self, dl, to_screen, ctx: ToolContext) -> None: ...
    def draw_ui(self, plane, scene) -> None: ...   # ← panelde gösterilecek form
    def cancel(self) -> None: ...
    def is_active(self) -> bool: ...


# ============================================================================
# PLACE DIST LOAD TOOL
# ============================================================================
@dataclass
class PlaceDistLoadTool:
    """Frame yayılı yük yerleştir.

    Akış:
        1) Frame'e tıkla → _pending = {"frame_id": uid}
        2) Panelde form: pattern, coord_sys, dir, q1, q2, is_relative
        3) Apply / Enter → frame.dist_load_sets[pattern]'e yaz
        4) Escape → iptal
    """
    kind: ToolKind = ToolKind.PLACE_DIST_LOAD
    _pending: dict = field(default_factory=dict)

    # Form state
    pattern: str = "DEAD"
    coord_sys: str = "Global"
    load_dir: str = "6"            # SAP kod: 6=GZ, 7=Gravity
    q1: float = 0.0
    q2: float = 0.0
    is_relative: bool = True
    x1: float = 0.0
    x2: float = 1.0
    mode: str = "REPLACE"

    # Pattern/coord_sys seçenekleri (panel dolduracak)
    available_patterns: list[str] = field(default_factory=list)
    available_coordsys: list[str] = field(default_factory=lambda: ["Global", "Local"])

    # ------------------------------------------------------------------
    # TOOL PROTOCOL
    # ------------------------------------------------------------------
    def on_click(self, ctx: ToolContext, scene, plane) -> bool:
        """Frame'e tıkla → pending olarak işaretle."""
        if not ctx.hover:
            self._pending = {}
            return False
        kind, uid = ctx.hover
        if kind != "frame":
            self._pending = {}
            return False
        self._pending = {"frame_id": int(uid)}
        return True

    def on_move(self, ctx: ToolContext, scene, plane) -> None:
        pass

    def on_right_click(self, ctx: ToolContext) -> None:
        """Sağ tık — formu sıfırla."""
        self._reset_form()

    def is_active(self) -> bool:
        return bool(self._pending)

    def cancel(self) -> None:
        self._pending = {}
        self._reset_form()

    # ------------------------------------------------------------------
    # PREVIEW
    # ------------------------------------------------------------------
    def draw_preview(self, dl, to_screen, ctx: ToolContext) -> None:
        """Seçili frame üzerine önizleme trapezoid çiz."""
        if not self._pending:
            return
        # Bu kısım LoadOverlay benzeri; ana view'da seçili frame zaten highlight.
        # Sadece değer önizlemesi:
        fid = self._pending.get("frame_id")
        if fid is None or ctx.hover != ("frame", fid):
            return
        # Frame hover'da — ek bilgi metni
        # asıl önizleme view'da seçim rengiyle yapılır.

    # ------------------------------------------------------------------
    # FORM UI
    # ------------------------------------------------------------------
    def draw_ui(self, plane, scene) -> None:
        """Panelde gösterilecek form — aktif olduğunda."""
        if not self._pending:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.75, 0.85, 1.0),
                "Yayılı yük için bir frame'e tıkla",
            )
            return

        fid = self._pending.get("frame_id")
        frame = scene.frames.get(fid) if scene else None
        if frame is None:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.4, 0.4, 1.0), "Frame bulunamadı",
            )
            self._pending = {}
            return

        # Frame bilgisi
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.9, 0.7, 1.0),
            f"Frame: {frame.label} (#{fid})",
        )
        imgui.separator()

        # Pattern seçimi
        imgui.text("Pattern")
        imgui.same_line(120)
        if self.available_patterns:
            try:
                cur_idx = self.available_patterns.index(self.pattern)
            except ValueError:
                cur_idx = 0
            imgui.set_next_item_width(180)
            if imgui.begin_combo("##pat", self.available_patterns[cur_idx]):
                for i, p in enumerate(self.available_patterns):
                    if imgui.selectable(p, i == cur_idx)[0]:
                        self.pattern = p
                imgui.end_combo()
        else:
            imgui.set_next_item_width(180)
            _, self.pattern = imgui.input_text("##pat", self.pattern)

        # CoordSys
        imgui.text("CoordSys")
        imgui.same_line(120)
        try:
            cs_idx = self.available_coordsys.index(self.coord_sys)
        except ValueError:
            cs_idx = 0
        imgui.set_next_item_width(180)
        if imgui.begin_combo("##cs", self.available_coordsys[cs_idx]):
            for i, cs in enumerate(self.available_coordsys):
                if imgui.selectable(cs, i == cs_idx)[0]:
                    self.coord_sys = cs
            imgui.end_combo()

        # Direction
        imgui.text("Direction")
        imgui.same_line(120)
        dir_items = [
            ("6", "6 - Global Z"),
            ("7", "7 - Gravity"),
            ("2", "2 - Local 2"),
            ("3", "3 - Local 3"),
            ("4", "4 - Global X"),
            ("5", "5 - Global Y"),
        ]
        try:
            d_idx = [d for d, _ in dir_items].index(self.load_dir)
        except ValueError:
            d_idx = 0
        imgui.set_next_item_width(180)
        if imgui.begin_combo("##dir", dir_items[d_idx][1]):
            for i, (val, lbl) in enumerate(dir_items):
                if imgui.selectable(lbl, i == d_idx)[0]:
                    self.load_dir = val
            imgui.end_combo()

        # is_relative
        imgui.text("Relative")
        imgui.same_line(120)
        _, self.is_relative = imgui.checkbox("##rel", self.is_relative)

        # x1, x2 (relative 0-1)
        imgui.text("x1")
        imgui.same_line(120)
        imgui.set_next_item_width(80)
        _, self.x1 = imgui.input_float("##x1", self.x1, 0.05, 0.1)
        imgui.same_line()
        imgui.text("x2")
        imgui.same_line()
        imgui.set_next_item_width(80)
        _, self.x2 = imgui.input_float("##x2", self.x2, 0.05, 0.1)
        self.x1 = max(0.0, min(1.0, self.x1))
        self.x2 = max(self.x1 + 0.001, min(1.0, self.x2))

        # q1, q2
        imgui.text("q1")
        imgui.same_line(120)
        imgui.set_next_item_width(80)
        _, self.q1 = imgui.input_float("##q1", self.q1, 0.1, 1.0)
        imgui.same_line()
        imgui.text("q2")
        imgui.same_line()
        imgui.set_next_item_width(80)
        _, self.q2 = imgui.input_float("##q2", self.q2, 0.1, 1.0)

        # mode
        imgui.text("Mode")
        imgui.same_line(120)
        mode_items = ["REPLACE", "ADD"]
        try:
            m_idx = mode_items.index(self.mode)
        except ValueError:
            m_idx = 0
        imgui.set_next_item_width(180)
        if imgui.begin_combo("##mode", mode_items[m_idx]):
            for i, m in enumerate(mode_items):
                if imgui.selectable(m, i == m_idx)[0]:
                    self.mode = m
            imgui.end_combo()

        imgui.separator()

        # Apply / Cancel
        can_apply = abs(self.q1) + abs(self.q2) > 1e-12
        if not can_apply:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0),
            )
        if imgui.button("Apply", imgui.ImVec2(100, 26)) and can_apply:
            self._apply_to_frame(frame, scene)
        if not can_apply:
            imgui.pop_style_color(1)
        imgui.same_line()
        if imgui.button("Cancel", imgui.ImVec2(100, 26)):
            self.cancel()

    # ------------------------------------------------------------------
    # APPLY
    # ------------------------------------------------------------------
    def _apply_to_frame(self, frame, scene) -> None:
        from domain.definition import FrameDistributedLoad, LoadSegment

        # Load set yoksa oluştur
        load_set = frame.dist_load_sets.get(self.pattern)
        if load_set is None or self.mode == "REPLACE":
            load_set = FrameDistributedLoad(
                pattern_name=self.pattern,
                coord_sys=self.coord_sys,
                load_dir=self.load_dir,
                mode=self.mode,
                is_relative=self.is_relative,
                segments=[],
            )
        else:
            # ADD modu — mevcut segment'leri koru
            pass

        # Segment ekle (x1 < x2 sıralı)
        x1, x2 = (self.x1, self.x2) if self.x1 < self.x2 else (self.x2, self.x1)
        q1, q2 = (self.q1, self.q2) if self.x1 < self.x2 else (self.q2, self.q1)
        load_set.add_segment(x1=x1, x2=x2, q1=q1, q2=q2)

        frame.dist_load_sets[self.pattern] = load_set
        frame.mark_dirty()

        if scene is not None:
            scene.mark_dirty()

        # Pending'i temizle (form sıfırla, frame seçimi kalksın)
        self._pending = {}

    # ------------------------------------------------------------------
    def _reset_form(self) -> None:
        self.q1 = 0.0
        self.q2 = 0.0
        self.x1 = 0.0
        self.x2 = 1.0
        self.mode = "REPLACE"

    # ------------------------------------------------------------------
    def set_patterns(self, patterns: list[str]) -> None:
        """Panelden doldurulur — projede tanımlı pattern'lar."""
        self.available_patterns = list(patterns)
        if self.pattern not in self.available_patterns and self.available_patterns:
            self.pattern = self.available_patterns[0]