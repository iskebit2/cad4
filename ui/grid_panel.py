# ui/grid_panel.py
from __future__ import annotations

import math

from imgui_bundle import imgui

from domain.grid import Grid, ObliqueAxis
from ui.base_panel import BasePanel


class GridPanel(BasePanel):

    def __init__(self):
        super().__init__(title="Aks & Grid Yönetimi", width=460, height=700,
                         pos_first_use=(440, 80))
        self.app = None
        self.visible = False
        self._draft: dict | None = None
        self._obl: dict = self._blank_oblique()

    # ------------------------------------------------------------------
    @property
    def grid(self) -> Grid | None:
        p = getattr(self.app, "current_project", None)
        return getattr(p, "grid", None) if p else None

    @property
    def renderer(self):
        e = getattr(self.app, "engine", None)
        return getattr(getattr(e, "presentation", None) or e, "grid", None)

    def open(self, **kw):
        super().open(**kw)
        self._reset_draft()

    def _reset_draft(self):
        g = self.grid
        self._draft = None if g is None else {
            "xs": ", ".join(self._f(v) for v in sorted(set(g.x_coords))),
            "ys": ", ".join(self._f(v) for v in sorted(set(g.y_coords))),
            "zs": ", ".join(self._f(v) for v in sorted(set(g.z_coords))),
            "xn": ", ".join(g.x_labels),
            "yn": ", ".join(g.y_labels),
            "zn": ", ".join(g.z_labels),
            "boundary": "; ".join(f"{x:g},{y:g}" for x, y in g.boundary_coords),
            "show_labels": g.show_labels,
            "label_pos": g.label_position,
            "overflow": g.label_overflow,
        }

    @staticmethod
    def _blank_oblique() -> dict:
        return {"name": "", "x1": 0.0, "y1": 0.0, "x2": 10000.0, "y2": 10000.0}

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.grid is None:
            imgui.text_colored(imgui.ImVec4(0.95, 0.3, 0.3, 1.0), "Aktif grid yok")
            return
        if self._draft is None:
            self._reset_draft()

        if imgui.collapsing_header("Ortogonal Akslar", imgui.TreeNodeFlags_.default_open):
            self._ortho_section()
        if imgui.collapsing_header("Eğik Akslar", imgui.TreeNodeFlags_.default_open):
            self._oblique_section()
        if imgui.collapsing_header("Etiketler", imgui.TreeNodeFlags_.default_open):
            self._label_section()

    # ------------------------------------------------------------------
    def _ortho_section(self):
        d = self._draft
        imgui.push_item_width(-1)
        for key, hint in (("xs", "X koordinatları  (0, 4000, 8000)"),
                          ("xn", "X isimleri  (A, B, C)"),
                          ("ys", "Y koordinatları  (0, 5000, 10000)"),
                          ("yn", "Y isimleri  (1, 2, 3)"),
                          ("zs", "Z kotları  (0, 3500, 7000)"),
                          ("zn", "Z isimleri  (K1, K2, K3)"),
                          ("boundary", "Boundary  (x1,y1; x2,y2; ...)")):
            imgui.text_disabled(hint)
            _, d[key] = imgui.input_text(f"##{key}", d[key], 0)
        imgui.pop_item_width()

        imgui.spacing()
        w = (imgui.get_content_region_avail().x - 8) / 2.0
        if imgui.button("Uygula##ortho_apply", imgui.ImVec2(w, 30)):
            self._apply_ortho()
        imgui.same_line()
        if imgui.button("Sıfırla##ortho_reset", imgui.ImVec2(w, 30)):
            self._reset_draft()

    def _apply_ortho(self):
        d = self._draft
        g = self.grid
        xs = self._floats(d["xs"])
        ys = self._floats(d["ys"])
        zs = self._floats(d["zs"])
        if not xs or not ys:
            return
        g.x_coords = xs
        g.y_coords = ys
        g.z_coords = zs
        g.x_labels = self._strs(d["xn"])
        g.y_labels = self._strs(d["yn"])
        g.z_labels = self._strs(d["zn"])
        g.boundary_coords = self._pairs(d["boundary"])
        project = getattr(self.app, "current_project", None)
        if project is not None:
            project.invalidate_grid_planes()
        self._dirty()

    # ------------------------------------------------------------------
    def _oblique_section(self):
        d = self._obl
        imgui.push_item_width(-1)
        imgui.text_disabled("Aks adı")
        _, d["name"] = imgui.input_text("##obl_name", d["name"], 64)
        imgui.text_disabled("X1, Y1, X2, Y2")
        w = (imgui.get_content_region_avail().x - 12) / 4.0
        imgui.push_item_width(w)
        for k in ("x1", "y1", "x2", "y2"):
            _, d[k] = imgui.input_float(f"##obl_{k}", d[k], step=100.0, format="%.1f")
            imgui.same_line()
        imgui.pop_item_width()
        imgui.pop_item_width()

        if imgui.button("Ekle##obl_add", imgui.ImVec2(-1, 28)):
            self._add_oblique()

        for o in self.grid.oblique_axes:
            imgui.push_id(f"obl_{o.name}")
            ch, vis = imgui.checkbox("##v", o.visible)
            if ch:
                o.visible = vis
                self._dirty()
            imgui.same_line()
            imgui.text_colored(imgui.ImVec4(*o.color, 1.0), o.name or "-")
            imgui.same_line()
            imgui.text_disabled(f"({o.p1[0]:.0f},{o.p1[1]:.0f}) -> ({o.p2[0]:.0f},{o.p2[1]:.0f})")
            imgui.same_line()
            if imgui.small_button("Sil##del"):
                self.grid.oblique_axes = [x for x in self.grid.oblique_axes if x is not o]
                self._dirty()
            imgui.pop_id()

    def _add_oblique(self):
        d = self._obl
        name = d["name"].strip() or f"E{len(self.grid.oblique_axes) + 1}"
        self.grid.oblique_axes.append(ObliqueAxis(
            name=name, p1=(d["x1"], d["y1"]), p2=(d["x2"], d["y2"]),
        ))
        self._obl = self._blank_oblique()
        self._dirty()

    # ------------------------------------------------------------------
    def _label_section(self):
        d = self._draft
        _, d["show_labels"] = imgui.checkbox("Balonları göster", d["show_labels"])

        positions = ["end", "both_ends", "middle"]
        labels = ["Çizgi ucunda", "Her iki uçta", "Ortada"]
        idx = positions.index(d["label_pos"]) if d["label_pos"] in positions else 0
        ch, new_idx = imgui.combo("Konum", idx, labels)
        if ch:
            d["label_pos"] = positions[new_idx]

        _, d["overflow"] = imgui.input_float("Taşma (mm)", d["overflow"], step=50.0, format="%.0f")

        imgui.spacing()
        w = (imgui.get_content_region_avail().x - 8) / 2.0
        if imgui.button("Uygula##lbl_apply", imgui.ImVec2(w, 30)):
            g = self.grid
            g.show_labels = d["show_labels"]
            g.label_position = d["label_pos"]
            g.label_overflow = max(0.0, d["overflow"])
            self._dirty()
        imgui.same_line()
        if imgui.button("Sıfırla##lbl_reset", imgui.ImVec2(w, 30)):
            self._reset_draft()

    # ------------------------------------------------------------------
    def _dirty(self):
        if self.renderer:
            self.renderer.mark_dirty()

    @staticmethod
    def _f(v: float) -> str:
        return f"{int(v)}" if float(v).is_integer() else f"{v:g}"

    @staticmethod
    def _floats(text: str) -> list[float]:
        out = []
        for s in text.replace(",", " ").split():
            try:
                out.append(float(s))
            except ValueError:
                pass
        return out

    @staticmethod
    def _strs(text: str) -> list[str]:
        return [s.strip() for s in text.split(",") if s.strip()]

    @staticmethod
    def _pairs(text: str) -> list[tuple[float, float]]:
        out = []
        for chunk in text.split(";"):
            parts = chunk.split(",")
            if len(parts) != 2:
                continue
            try:
                out.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
        return out if len(out) >= 3 else []