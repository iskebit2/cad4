# ui/panels/joint_load_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from core.commands import project_commands as PC
from domain.definition import PointLoad
from domain.element import Node
from logging_config import CadLogger
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)


_DOF_ROWS = [
    ("fx", "Fx",    "kN",   0.1),
    ("fy", "Fy",    "kN",   0.1),
    ("fz", "Fz",    "kN",   0.1),
    ("mx", "Mx",    "kN·m", 0.1),
    ("my", "My",    "kN·m", 0.1),
    ("mz", "Mz",    "kN·m", 0.1),
]


class JointLoadPanel(PanelBase):
    __abstract__ = False
    panel_name = "joint_load"
    title = "Noktasal Yük"
    category = Category.LOADS
    quick = False
    context = ("selection_nodes", "patterns", "math_model")
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True

    width = 640
    height = 620
    pos_first_use = (80.0, 60.0)

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self.selection_nodes: list = []
        self.patterns: list[str] = []
        self.pattern: str = ""
        self.fx = self.fy = self.fz = 0.0
        self.mx = self.my = self.mz = 0.0
        self._status = ""

    # ------------------------------------------------------------------
    def _on_context_ready(self) -> None:
        nodes = getattr(self, "selection_nodes", None) or []
        pats = getattr(self, "patterns", None) or []
        self.selection_nodes = list(nodes)
        self.patterns = list(pats)
        if self.patterns and self.pattern not in self.patterns:
            self.pattern = self.patterns[0]
        if not self.patterns:
            self.pattern = ""

    # ------------------------------------------------------------------
    # 1. HEADER
    # ------------------------------------------------------------------
    def draw_header(self) -> None:
        self.section_label("Hedef Node'lar:")
        imgui.same_line()
        if not self.selection_nodes:
            imgui.text_colored(
                imgui.ImVec4(1.0, 0.5, 0.3, 1.0),
                "(Seçili node yok — sahne üzerinden seçin)",
            )
            return
        labels = [
            getattr(n, "label", None) or f"N_{n.unique_id}"
            for n in self.selection_nodes[:6]
        ]
        text = ", ".join(labels)
        if len(self.selection_nodes) > 6:
            text += f" ... (+{len(self.selection_nodes) - 6})"
        imgui.text_colored(
            imgui.ImVec4(0.5, 0.9, 0.5, 1.0),
            f"{len(self.selection_nodes)} adet: {text}",
        )

    # ------------------------------------------------------------------
    # 2. SETTINGS
    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        imgui.text("Pattern:")
        imgui.same_line(90)
        imgui.push_item_width(180)
        if imgui.begin_combo("##pattern", self.pattern or "(yok)"):
            for p in self.patterns:
                sel = (p == self.pattern)
                if imgui.selectable(p, sel)[0]:
                    self.pattern = p
                if sel:
                    imgui.set_item_default_focus()
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.same_line(300)
        imgui.text_disabled(f"({len(self.patterns)} pattern)")

    # ------------------------------------------------------------------
    # 4. TABLE
    # ------------------------------------------------------------------
    def draw_table(self) -> None:
        self.section_label("Yük Değerleri:")
        imgui.same_line()
        imgui.text_disabled("(UYGULA ile yeni yük eklenir)")

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("joint_load_table", 3, flags, imgui.ImVec2(0, 220)):
            return

        imgui.table_setup_column("Parametre", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Değer",     imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Birim",     imgui.TableColumnFlags_.width_fixed, 70)
        imgui.table_headers_row()

        for attr, label, unit, step in _DOF_ROWS:
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.text(label)

            imgui.table_set_column_index(1)
            imgui.push_item_width(-1)
            changed, val = imgui.input_float(
                f"##{attr}", float(getattr(self, attr)),
                step, 1.0, "%.4f",
            )
            if changed:
                setattr(self, attr, float(val))
            imgui.pop_item_width()

            imgui.table_set_column_index(2)
            imgui.text_disabled(unit)

        imgui.end_table()

    # ------------------------------------------------------------------
    # 5. ACTIONS
    # ------------------------------------------------------------------
    def draw_actions(self) -> None:
        can_apply = bool(self.pattern) and bool(self.selection_nodes)
        if self.action_button(" UYGULA ", 180, can_apply):
            self._apply()

        imgui.same_line()
        can_clear = bool(self.pattern) and bool(self.selection_nodes)
        if self.action_button("Temizle", 90, can_clear):
            self._clear()

        imgui.same_line()
        if self.action_button("Hedefi Yenile", 130, True):
            self._refresh_targets()

        imgui.spacing()
        if not self.selection_nodes:
            self.status_line("⚠ Seçili node yok — sahne üzerinden seçin", "warn")
        elif not self.pattern:
            self.status_line("⚠ Pattern seçilmedi", "warn")
        else:
            self.status_line(
                f"✓ {len(self.selection_nodes)} node | "
                f"F=({self.fx:+.2f}, {self.fy:+.2f}, {self.fz:+.2f}) kN | "
                f"M=({self.mx:+.2f}, {self.my:+.2f}, {self.mz:+.2f}) kN·m | "
                f"Pat={self.pattern}",
                "info",
            )

        if self._status:
            imgui.separator()
            imgui.text_wrapped(self._status)

    # ------------------------------------------------------------------
    # APPLY / CLEAR
    # ------------------------------------------------------------------
    def _apply(self) -> None:
        if not self.pattern or not self.selection_nodes:
            return
        queue = self.queue()
        n_queued = 0
        for n in self.selection_nodes:
            uid = getattr(n, "unique_id", None)
            if uid is None:
                continue
            cur = list(getattr(n, "loads", []) or [])
            cur.append(PointLoad(
                pattern_name=self.pattern,
                fx=self.fx, fy=self.fy, fz=self.fz,
                mx=self.mx, my=self.my, mz=self.mz,
            ))
            queue.put(PC.UpdateElementFields(uid, {"loads": cur}))
            n_queued += 1
        self._status = f"{n_queued} node'a yük eklendi."
        logger.info("[JointLoad] %d node kuyruğa eklendi", n_queued)

    def _clear(self) -> None:
        if not self.pattern or not self.selection_nodes:
            return
        queue = self.queue()
        n_queued = 0
        for n in self.selection_nodes:
            uid = getattr(n, "unique_id", None)
            if uid is None:
                continue
            cur = [
                pl for pl in (getattr(n, "loads", []) or [])
                if getattr(pl, "pattern_name", "") != self.pattern
            ]
            queue.put(PC.UpdateElementFields(uid, {"loads": cur}))
            n_queued += 1
        self._status = f"{n_queued} node'dan '{self.pattern}' yükü kaldırıldı."

    # ------------------------------------------------------------------
    def _refresh_targets(self) -> None:
        app = getattr(self, "app", None)
        if not app or not getattr(app, "engine", None):
            return
        scn = app.engine.math_model
        if scn is None:
            return
        sel = scn.get_selected()
        nodes = [e for e in sel if isinstance(e, Node)]
        if nodes:
            self.selection_nodes = nodes
            self._status = f"{len(nodes)} node hedef listesine alındı."

    def on_scene_selection_changed(self, selected: list) -> None:
        nodes = [e for e in selected if isinstance(e, Node)]
        if not nodes:
            return
        self.selection_nodes = nodes