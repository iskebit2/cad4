# ui/panels/grid_panel.py
from __future__ import annotations

import re

from imgui_bundle import imgui

from domain.grid import Grid, ObliqueAxis
from ui.base.panel_base import PanelBase, Category
from viewport.viewport import ViewUCS, ViewVolume


_FLOAT_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


class GridPanel(PanelBase):
    __abstract__ = False
    panel_name = "grid"
    title = "Grid Settings"
    category = Category.VIEW
    quick = True
    menu_label = "Grid Settings"
    icon = "hash"
    shortcut = "CTRL+G"
    context = ("project", "scene")

    def __init__(self, app=None):
        super().__init__(app=app)
        self.width = 460
        self.height = 840
        self.pos_first_use = (200, 100)
        self.uses_draft = False
        self.show_apply_bar = False
        self._draft: dict | None = None
        self._obl: dict = self._blank_oblique()
        self._plane_index: dict[str, int] = {"XY": 0, "XZ": 0, "YZ": 0}

    def _refresh_draft(self) -> None:
        self.draft = None
        self._original = None
        self._dirty = False

    @property
    def grid(self) -> Grid | None:
        p = getattr(self.app, "current_project", None)
        return p.grid if p is not None else None

    @property
    def length_unit(self) -> str:
        p = getattr(self.app, "current_project", None)
        return p.unit_system.length_unit if p is not None else ""

    @property
    def renderer(self):
        e = getattr(self.app, "engine", None)
        return getattr(e, "grid", None) if e is not None else None

    def open(self, **kw) -> None:
        super().open(**kw)
        self._reset_draft()

    def _reset_draft(self) -> None:
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

    def draw_content(self) -> None:
        g = self.grid
        if g is None:
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
        if imgui.collapsing_header("Düzlem Viewport", imgui.TreeNodeFlags_.default_open):
            self._viewport_section()

    def _ortho_section(self) -> None:
        d = self._draft
        u = self.length_unit
        imgui.push_item_width(-1)
        for key, hint in (
            ("xs", f"X koordinatları ({u})"),
            ("xn", "X isimleri  (A, B, C)"),
            ("ys", f"Y koordinatları ({u})"),
            ("yn", "Y isimleri  (1, 2, 3)"),
            ("zs", f"Z kotları ({u})"),
            ("zn", "Z isimleri  (K1, K2, K3)"),
            ("boundary", f"Boundary ({u})  x1,y1; x2,y2; ..."),
        ):
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

    def _apply_ortho(self) -> None:
        g = self.grid
        if g is None:
            return
        d = self._draft
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
        self._commit()

    def _oblique_section(self) -> None:
        d = self._obl
        u = self.length_unit
        imgui.push_item_width(-1)
        imgui.text_disabled("Aks adı")
        _, d["name"] = imgui.input_text("##obl_name", d["name"], 64)
        imgui.text_disabled(f"X1, Y1, X2, Y2 ({u})")
        w = (imgui.get_content_region_avail().x - 12) / 4.0
        imgui.push_item_width(w)
        for k in ("x1", "y1", "x2", "y2"):
            _, d[k] = imgui.input_float(f"##obl_{k}", d[k], step=100.0, format="%.1f")
            imgui.same_line()
        imgui.pop_item_width()
        imgui.pop_item_width()

        if imgui.button("Ekle##obl_add", imgui.ImVec2(-1, 28)):
            self._add_oblique()

        g = self.grid
        if g is None:
            return
        for o in g.oblique_axes:
            imgui.push_id(f"obl_{o.name}")
            ch, vis = imgui.checkbox("##v", o.visible)
            if ch:
                o.visible = vis
                self._commit()
            imgui.same_line()
            imgui.text_colored(imgui.ImVec4(*o.color, 1.0), o.name or "-")
            imgui.same_line()
            imgui.text_disabled(
                f"({o.p1[0]:.0f},{o.p1[1]:.0f}) -> ({o.p2[0]:.0f},{o.p2[1]:.0f})"
            )
            imgui.same_line()
            if imgui.small_button("Sil##del"):
                g.oblique_axes = [x for x in g.oblique_axes if x is not o]
                self._commit()
            imgui.pop_id()

    def _add_oblique(self) -> None:
        g = self.grid
        if g is None:
            return
        d = self._obl
        name = d["name"].strip() or f"E{len(g.oblique_axes) + 1}"
        g.oblique_axes.append(ObliqueAxis(
            name=name, p1=(d["x1"], d["y1"]), p2=(d["x2"], d["y2"]),
        ))
        self._obl = self._blank_oblique()
        self._commit()

    def _label_section(self) -> None:
        d = self._draft
        u = self.length_unit
        _, d["show_labels"] = imgui.checkbox("Balonları göster", d["show_labels"])

        positions = ["end", "both_ends", "middle"]
        labels = ["Çizgi ucunda", "Her iki uçta", "Ortada"]
        idx = positions.index(d["label_pos"]) if d["label_pos"] in positions else 0
        ch, new_idx = imgui.combo("Konum", idx, labels)
        if ch:
            d["label_pos"] = positions[new_idx]

        _, d["overflow"] = imgui.input_float(
            f"Taşma ({u})", d["overflow"], step=50.0, format="%.0f"
        )

        imgui.spacing()
        w = (imgui.get_content_region_avail().x - 8) / 2.0
        if imgui.button("Uygula##lbl_apply", imgui.ImVec2(w, 30)):
            g = self.grid
            if g is not None:
                g.show_labels = d["show_labels"]
                g.label_position = d["label_pos"]
                g.label_overflow = max(0.0, d["overflow"])
                self._commit()
        imgui.same_line()
        if imgui.button("Sıfırla##lbl_reset", imgui.ImVec2(w, 30)):
            self._reset_draft()

    def _viewport_section(self) -> None:
        u = self.length_unit
        imgui.text_disabled(f"Grid düzleminde viewport aç ({u})")
        for plane in ("XY", "XZ", "YZ"):
            levels = self._plane_levels(plane)
            if not levels:
                imgui.text_disabled(f"{plane}: seviye yok")
                continue
            idx = max(0, min(self._plane_index.get(plane, 0), len(levels) - 1))
            imgui.text(f"{plane} seviyesi")
            imgui.same_line()
            imgui.push_item_width(120)
            items = [f"{v:g}" for v in levels]
            ch, new_idx = imgui.combo(f"##lvl_{plane}", idx, items)
            if ch:
                self._plane_index[plane] = new_idx
            imgui.pop_item_width()
            imgui.same_line()
            if imgui.button(f"Aç##open_{plane}"):
                self._open_plane_viewport(plane)

    def _plane_levels(self, plane: str) -> list[float]:
        g = self.grid
        if g is None:
            return []
        if plane == "XY":
            return sorted(set(g.z_coords))
        if plane == "XZ":
            return sorted(set(g.y_coords))
        if plane == "YZ":
            return sorted(set(g.x_coords))
        return []

    def _make_ucs(self, plane: str, level: float) -> ViewUCS:
        if plane == "XY":
            return ViewUCS.from_axes((0.0, 0.0, level), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        if plane == "XZ":
            return ViewUCS.from_axes((0.0, level, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        return ViewUCS.from_axes((level, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

    def _make_volume(self, plane: str) -> ViewVolume:
        g = self.grid
        xs = sorted(set(g.x_coords)) or [0.0]
        ys = sorted(set(g.y_coords)) or [0.0]
        zs = sorted(set(g.z_coords)) or [0.0]
        v = ViewVolume()
        if plane == "XY":
            v.set_bounds(xs[0], xs[-1], ys[0], ys[-1])
        elif plane == "XZ":
            v.set_bounds(xs[0], xs[-1], zs[0], zs[-1])
        else:
            v.set_bounds(ys[0], ys[-1], zs[0], zs[-1])
        return v

    def _open_plane_viewport(self, plane: str) -> None:
        levels = self._plane_levels(plane)
        if not levels:
            return
        idx = max(0, min(self._plane_index.get(plane, 0), len(levels) - 1))
        level = levels[idx]
        ucs = self._make_ucs(plane, level)
        volume = self._make_volume(plane)
        ui = getattr(self.app, "ui", None)
        if ui is None:
            return
        ui.open_viewport_on_plane(
            name_hint=f"{plane}_{level:g}",
            ucs=ucs,
            volume=volume,
            is_2d=True,
        )

    def _commit(self) -> None:
        r = self.renderer
        if r is not None:
            r.mark_dirty()
        p = getattr(self.app, "current_project", None)
        if p is not None:
            p.invalidate_grid_planes()

    @staticmethod
    def _f(v: float) -> str:
        return f"{int(v)}" if float(v).is_integer() else f"{v:g}"

    @classmethod
    def _floats(cls, text: str) -> list[float]:
        return [float(s) for s in text.replace(",", " ").split() if _FLOAT_RE.match(s)]

    @staticmethod
    def _strs(text: str) -> list[str]:
        return [s.strip() for s in text.split(",") if s.strip()]

    @classmethod
    def _pairs(cls, text: str) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for chunk in text.split(";"):
            parts = chunk.split(",")
            if len(parts) != 2:
                continue
            a, b = parts[0].strip(), parts[1].strip()
            if _FLOAT_RE.match(a) and _FLOAT_RE.match(b):
                out.append((float(a), float(b)))
        return out if len(out) >= 3 else []