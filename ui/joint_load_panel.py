# ui/joint_load_panel.py
import imgui
from ui.base_panel import BasePanel
from domain.definition import PointLoad
from logging_config import CadLogger

logger = CadLogger.get(__name__)

class JointLoadPanel(BasePanel):
    def __init__(self):
        self.visible = False
        self.selected_nodes = []
        self.patterns = []
        self.pattern = ""
        self.fx = self.fy = self.fz = 0.0
        self.mx = self.my = self.mz = 0.0
        self.dirty = False

    def set_context(self, ctx):
        self.selected_nodes = ctx.get("selection_nodes", [])
        self.patterns = ctx.get("patterns", [])
        if self.patterns and self.pattern not in self.patterns:
            self.pattern = self.patterns[0]

    def open(self):  self.visible = True
    def close(self): self.visible = False

    def draw(self):
        if not self.visible: return
        imgui.set_next_window_size(360, 340, imgui.ONCE)
        _, opened = imgui.begin("Noktasal Yük", True)
        if not opened:
            self.close(); imgui.end(); return

        imgui.text(f"Seçili düğüm: {len(self.selected_nodes)}")

        if self.patterns:
            if imgui.begin_combo("Pattern", self.pattern or "(yok)"):
                for p in self.patterns:
                    if imgui.selectable(p, p == self.pattern)[0]:
                        self.pattern = p
                imgui.end_combo()

        imgui.separator()
        _, self.fx = imgui.input_float("Fx (kN)", self.fx)
        _, self.fy = imgui.input_float("Fy (kN)", self.fy)
        _, self.fz = imgui.input_float("Fz (kN)", self.fz)
        _, self.mx = imgui.input_float("Mx (kN·m)", self.mx)
        _, self.my = imgui.input_float("My (kN·m)", self.my)
        _, self.mz = imgui.input_float("Mz (kN·m)", self.mz)

        imgui.separator()
        if imgui.button("Uygula", width=120):
            self._apply()
        imgui.same_line()
        if imgui.button("Seçililerden Kaldır", width=160):
            self._clear()

        imgui.end()

    def _apply(self):
        if not self.pattern or not self.selected_nodes:
            return
        for n in self.selected_nodes:
            n.loads.append(PointLoad(
                pattern_name=self.pattern,
                fx=self.fx, fy=self.fy, fz=self.fz,
                mx=self.mx, my=self.my, mz=self.mz,
            ))
        self._refresh_renderer()
        logger.info("[JointLoad] %d node'a uygulandı", len(self.selected_nodes))

    def _clear(self):
        for n in self.selected_nodes:
            if hasattr(n, "loads"):
                n.loads = [pl for pl in n.loads if pl.pattern_name != self.pattern]
        self._refresh_renderer()

    def _refresh_renderer(self):
        app = getattr(self, "app", None)
        if not app or not app.engine: return
        r = app.engine.renderer
        if r and getattr(r, "load_renderer", None):
            r.load_renderer.update(app.engine.scene,
                                   camera_scale=r._compute_cam_scale())