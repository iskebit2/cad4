# ui/line_properties_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from domain.line import Line
from domain.vertex import Vertex
from ui.base_panel import BasePanel
from ui.widgets.color_picker import color_edit3


class LinePropertiesPanel(BasePanel):

    W = 360
    H = 360

    STYLES = ("solid", "dashed", "dash_dot")
    STYLE_LABELS = ("Düz", "Kesik", "Kesik-nokta")

    def __init__(self):
        super().__init__(title="Line", width=self.W, height=self.H,
                         pos_first_use=(900, 440))
        self.app = None
        self.project = None
        self.context = None
        self._selected_ids: set[int] = set()
        self._drawing = False
        self._batch_color = [1.0, 1.0, 1.0]
        self._batch_width = 1.0
        self._batch_style = 0

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.context = ctx
        self.project = ctx.get("project")

    def on_selection_changed(self, selected: list):
        self._selected_ids = {
            int(e.unique_id) for e in selected
            if e.__class__.__name__ == "Line"
        }

    # ------------------------------------------------------------------
    def _lines(self) -> list[Line]:
        if not self.project or not self._selected_ids:
            return []
        lines = getattr(self.project, "lines", {})
        return [lines[i] for i in self._selected_ids if i in lines]

    def _refresh(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        pr = getattr(eng, "presentation_renderer", None) if eng else None
        if pr and self.project:
            pr.update_lines(list(getattr(self.project, "lines", {}).values()))

    def _manager(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        return getattr(eng, "draw_mgr", None) if eng else None

    # ------------------------------------------------------------------
    def draw_content(self):
        self._toolbar()
        imgui.separator()

        items = self._lines()
        if not items:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                               "Hazır. Çiz veya line seç.")
            return

        if len(items) == 1:
            self._properties_single(items[0])
        else:
            self._properties_multi(items)

    # ------------------------------------------------------------------
    def _toolbar(self):
        mgr = self._manager()
        drawing = self._drawing and mgr and mgr.is_active and mgr.mode == "line"
        if drawing:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.2, 0.55, 0.3, 1.0))
        if imgui.button("✎", imgui.ImVec2(26, 24)):
            self._start_drawing()
        if drawing:
            imgui.pop_style_color(1)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Line çiz")
        imgui.same_line(0, 2)

        if imgui.button("↕", imgui.ImVec2(26, 24)):
            self._create_column()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Kolon (düzleme dik)")

        imgui.same_line(0, 6)
        imgui.text("|")
        imgui.same_line(0, 6)

        items = self._lines()
        enabled = bool(items)
        if not enabled:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0))

        if imgui.button("⇄", imgui.ImVec2(26, 24)) and enabled:
            for ln in items:
                self._to_frame(ln)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Frame'e dönüştür")
        imgui.same_line(0, 2)

        if imgui.button("⊞", imgui.ImVec2(26, 24)) and enabled:
            for ln in items:
                self._to_link(ln)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Link'e dönüştür")
        imgui.same_line(0, 2)

        if imgui.button("🗑", imgui.ImVec2(26, 24)) and enabled:
            for ln in list(items):
                self._delete(ln)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Sil")
        if not enabled:
            imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    def _properties_single(self, ln: Line):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0),
                           f"{ln.label or 'Line'} (id={ln.unique_id})")

        imgui.text("Tip")
        imgui.same_line(80)
        imgui.text("Kolon" if ln.is_column else "Serbest")
        imgui.same_line()
        if imgui.checkbox("Kolon##col", ln.is_column):
            ln.is_column = not ln.is_column
            if ln.is_column:
                self._recompute_column(ln)
            ln.mark_dirty() if hasattr(ln, "mark_dirty") else None

        if ln.is_column:
            self._column_inputs(ln)
        else:
            self._endpoint_inputs(ln)

        self._line_style(ln)
        imgui.text(f"Uzunluk: {ln.length:.2f}")

    def _properties_multi(self, items: list[Line]):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0),
                           f"{len(items)} line seçili")
        imgui.separator()

        imgui.text("Renk")
        imgui.same_line(80)
        _, new_rgb = color_edit3("##bcolor", list(self._batch_color))
        self._batch_color = list(new_rgb)

        imgui.text("Kalınlık")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_width = imgui.input_float("##bwidth", self._batch_width, step=0.1, format="%.2f")
        imgui.pop_item_width()

        imgui.text("Stil")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_style = imgui.combo("##bstyle", self._batch_style, self.STYLE_LABELS)
        imgui.pop_item_width()

        imgui.spacing()
        if imgui.button("Tümüne Uygula", imgui.ImVec2(-1, 30)):
            self._apply_batch(items)

    def _apply_batch(self, items: list[Line]):
        color = tuple(self._batch_color[:3])
        style = self.STYLES[self._batch_style]
        for ln in items:
            ln.color = color
            ln.width = float(self._batch_width)
            ln.style = style
        self._refresh()

    # ------------------------------------------------------------------
    def _line_style(self, ln: Line):
        imgui.separator()
        imgui.text("Renk")
        imgui.same_line(80)
        rgb = list(ln.color[:3]) if ln.color else [1.0, 1.0, 1.0]
        changed, new_rgb = color_edit3("##lcolor", rgb)
        if changed:
            ln.color = tuple(new_rgb[:3])
            self._refresh()

        imgui.text("Kalınlık")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        changed, val = imgui.input_float("##lwidth", ln.width, step=0.1, format="%.2f")
        imgui.pop_item_width()
        if changed:
            ln.width = float(val)
            self._refresh()

        imgui.text("Stil")
        imgui.same_line(80)
        cur = self.STYLES.index(ln.style) if ln.style in self.STYLES else 0
        imgui.push_item_width(-1)
        changed, idx = imgui.combo("##lstyle", cur, self.STYLE_LABELS)
        imgui.pop_item_width()
        if changed:
            ln.style = self.STYLES[idx]
            self._refresh()

    # ------------------------------------------------------------------
    def _endpoint_inputs(self, ln: Line):
        imgui.separator()
        imgui.text("Başlangıç")
        imgui.same_line(80)
        x, y, z = ln.v1.x, ln.v1.y, ln.v1.z
        w = (imgui.get_content_region_avail().x - 8) / 3.0
        imgui.push_item_width(w)
        cx, x = imgui.input_float("##v1x", x, format="%.2f"); imgui.same_line()
        cy, y = imgui.input_float("##v1y", y, format="%.2f"); imgui.same_line()
        cz, z = imgui.input_float("##v1z", z, format="%.2f")
        imgui.pop_item_width()
        if cx or cy or cz:
            ln.v1 = Vertex(float(x), float(y), float(z))
            self._refresh()

        imgui.text("Bitiş")
        imgui.same_line(80)
        x, y, z = ln.v2.x, ln.v2.y, ln.v2.z
        imgui.push_item_width(w)
        cx, x = imgui.input_float("##v2x", x, format="%.2f"); imgui.same_line()
        cy, y = imgui.input_float("##v2y", y, format="%.2f"); imgui.same_line()
        cz, z = imgui.input_float("##v2z", z, format="%.2f")
        imgui.pop_item_width()
        if cx or cy or cz:
            ln.v2 = Vertex(float(x), float(y), float(z))
            self._refresh()

    def _column_inputs(self, ln: Line):
        imgui.separator()
        x, y = ln.v1.x, ln.v1.y
        w = (imgui.get_content_region_avail().x - 8) / 2.0
        imgui.text("X, Y")
        imgui.same_line(80)
        imgui.push_item_width(w)
        cx, x = imgui.input_float("##colx", x, format="%.2f"); imgui.same_line()
        cy, y = imgui.input_float("##coly", y, format="%.2f")
        imgui.pop_item_width()

        z_lo = min(ln.v1.z, ln.v2.z)
        z_hi = max(ln.v1.z, ln.v2.z)
        imgui.text("Bottom Z")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        cz1, z_lo = imgui.input_float("##zlo", z_lo, format="%.2f")
        imgui.pop_item_width()

        imgui.text("Top Z")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        cz2, z_hi = imgui.input_float("##zhi", z_hi, format="%.2f")
        imgui.pop_item_width()

        if cx or cy or cz1 or cz2:
            ln.v1 = Vertex(float(x), float(y), float(z_lo))
            ln.v2 = Vertex(float(x), float(y), float(z_hi))
            self._refresh()

    def _recompute_column(self, ln: Line):
        x, y = ln.v1.x, ln.v1.y
        z_lo = min(ln.v1.z, ln.v2.z)
        z_hi = max(ln.v1.z, ln.v2.z)
        if abs(z_hi - z_lo) < 1e-3:
            z_hi = z_lo + 3000.0
        ln.v1 = Vertex(x, y, z_lo)
        ln.v2 = Vertex(x, y, z_hi)

    # ------------------------------------------------------------------
    def _start_drawing(self):
        mgr = self._manager()
        if mgr is None:
            return
        if mgr.is_active and mgr.mode == "line":
            mgr.cancel()
            self._drawing = False
            return
        mgr.cancel()
        mgr.start(mode="line")
        self._drawing = True

    def _create_column(self):
        eng = getattr(self.app, "engine", None)
        if eng is None or self.project is None:
            return
        plane = self.project.active_plane
        if plane is None:
            return
        x, y = float(plane.origin[0]), float(plane.origin[1])
        z_bottom = float(plane.origin[2])
        z_top = z_bottom + 3000.0
        ln = Line(
            v1=Vertex(x, y, z_bottom),
            v2=Vertex(x, y, z_top),
            is_column=True,
        )
        self.project.add_line(ln)
        self._refresh()

    def _to_frame(self, ln: Line):
        eng = getattr(self.app, "engine", None)
        if eng is None or self.project is None:
            return
        from domain.element import Frame, Node
        ni = Node(ln.v1.x, ln.v1.y, ln.v1.z, label="")
        nj = Node(ln.v2.x, ln.v2.y, ln.v2.z, label="")
        self.project.math_model.add_node(ni)
        self.project.math_model.add_node(nj)
        sec = next(iter(self.project.sections.values()), None)
        if sec is None:
            return
        frame = Frame(ni, nj, sec)
        self.project.math_model.add_frame(frame)
        self._delete(ln)
        eng.update_geo(self.project)

    def _to_link(self, ln: Line):
        eng = getattr(self.app, "engine", None)
        if eng is None or self.project is None:
            return
        from domain.element import Link, Node
        ni = Node(ln.v1.x, ln.v1.y, ln.v1.z, label="")
        nj = Node(ln.v2.x, ln.v2.y, ln.v2.z, label="")
        self.project.math_model.add_node(ni)
        self.project.math_model.add_node(nj)
        link = Link(ni, nj)
        self.project.math_model.add_link(link)
        self._delete(ln)
        eng.update_geo(self.project)

    def _delete(self, ln: Line):
        if self.project is None:
            return
        lines = self.project.math_model.lines
        lines.pop(ln.unique_id, None)
        self._selected_ids.discard(ln.unique_id)
        self._refresh()