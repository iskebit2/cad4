# ui/grid_panel.py
"""GridPanel — aks koordinatları + work plane yönetimi.

Tek doğruluk kaynağı: Project.grid (GridConfig).
GridSystem (engine.grid) türetilmiş — Project.grid'ten beslenir.
"""
from __future__ import annotations

from pyglm import glm
from imgui_bundle import imgui

from data.enums import GridPlane
from domain.definition import GridPlaneDef
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class GridPanel(BasePanel):
    PLANES = [GridPlane.XY, GridPlane.XZ, GridPlane.YZ]

    def __init__(self):
        super().__init__(
            title="Grid ve Work Plane",
            width=400, height=500,
            pos_first_use=(480, 100),
        )
        self.app = None
        self.visible = False

        self._x_text = ""
        self._y_text = ""
        self._z_text = ""
        self._initialized_texts = False

        self._new_name = "PLANE-1"
        self._new_origin = [0.0, 0.0, 3000.0]
        self._new_normal = [0.0, 0.0, 1.0]
        self._new_u_axis = [1.0, 0.0, 0.0]
        self._new_spacing_u = 1000.0
        self._new_spacing_v = 1000.0
        self._new_count_u = 10
        self._new_count_v = 10
        self._name_seq = 1

    # ----------------------------------------------------------------
    # CONTEXT
    # ----------------------------------------------------------------
    @property
    def project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    @property
    def engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    @property
    def grid_system(self):
        eng = self.engine
        return getattr(eng, "grid", None) if eng else None

    @property
    def camera(self):
        eng = self.engine
        return getattr(eng, "cam", None) if eng else None

    @property
    def grid(self):
        """Project.grid (GridConfig) — tek doğruluk kaynağı."""
        proj = self.project
        return getattr(proj, "grid", None) if proj else None

    # ----------------------------------------------------------------
    # OPEN / TEXT CACHE
    # ----------------------------------------------------------------
    def open(self):
        super().open()
        self._sync_texts_from_project()

    def _sync_texts_from_project(self):
        g = self.grid
        if g is None:
            return
        fmt = lambda v: int(v) if float(v).is_integer() else float(v)
        self._x_text = ", ".join(str(fmt(v)) for v in g.x_coords)
        self._y_text = ", ".join(str(fmt(v)) for v in g.y_coords)
        self._z_text = ", ".join(str(fmt(v)) for v in g.z_coords)
        self._initialized_texts = True

    def on_unit_changed(self):
        """Birim değişince text cache'i yenile."""
        self._sync_texts_from_project()

    # ----------------------------------------------------------------
    # DRAW
    # ----------------------------------------------------------------
    def draw_content(self):
        gs = self.grid_system
        if gs is None or self.grid is None:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.5, 0.5, 1.0),
                "Grid bağlı değil (Project veya Engine yok)",
            )
            return

        if not self._initialized_texts:
            self._sync_texts_from_project()

        if imgui.begin_tab_bar("grid_tabs"):
            if imgui.begin_tab_item("Global Grid")[0]:
                self._draw_global_grid()
                imgui.end_tab_item()
            if imgui.begin_tab_item("Work Planes")[0]:
                self._draw_work_planes()
                imgui.end_tab_item()
            imgui.end_tab_bar()

    # ----------------------------------------------------------------
    # GLOBAL GRID
    # ----------------------------------------------------------------
    def _draw_global_grid(self):
        gs = self.grid_system
        gp = self.grid

        imgui.text_colored(imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Düzlemler")
        imgui.separator()

        for plane in self.PLANES:
            if plane not in gs.planes:
                continue
            is_vis = gs.planes[plane].get("visible", False)
            changed, val = imgui.checkbox(
                f"  {plane.name} Düzlemi##vis", is_vis,
            )
            if changed:
                gs.set_plane(plane, visible=val)
                key = plane.name
                if key in gp.planes_visibility:
                    gp.planes_visibility[key] = bool(val)

        imgui.spacing()
        imgui.separator()
        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0),
            "Aks Koordinatları (virgülle ayırın)",
        )
        imgui.separator()

        _, self._x_text = imgui.input_text("X Aksları", self._x_text, 256)
        _, self._y_text = imgui.input_text("Y Aksları", self._y_text, 256)
        _, self._z_text = imgui.input_text("Z Kotları", self._z_text, 256)

        imgui.spacing()
        if imgui.button("Uygula", imgui.ImVec2(-1, 0)):
            self._apply_axis_coords()

        imgui.spacing()
        imgui.separator()

        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Origin (Kaydırma Merkezi)",
        )
        ox, oy, oz = gp.origin_x, gp.origin_y, gp.origin_z
        imgui.text("X"); imgui.same_line(30)
        cx, ox = imgui.input_float("##ox", ox, step=100.0)
        imgui.same_line(); imgui.text("Y"); imgui.same_line(30)
        cy, oy = imgui.input_float("##oy", oy, step=100.0)
        imgui.same_line(); imgui.text("Z"); imgui.same_line(30)
        cz, oz = imgui.input_float("##oz", oz, step=100.0)
        if cx or cy or cz:
            self._apply_origin(ox, oy, oz)

        cam = self.camera
        if cam is not None:
            if imgui.button("Origin → Model Merkezi", imgui.ImVec2(-1, 0)):
                try:
                    center, size = gs.get_bounds()
                    self._apply_origin(
                        float(center.x), float(center.y), float(center.z),
                    )
                    cam.update_bounds(center, size)
                except Exception:
                    logger.exception("[GridPanel] Origin → model merkezi hatası")

        imgui.spacing()
        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Kamera Hizalama")
        if cam is not None:
            if imgui.button("Kamerayı Üst Görünüşe (TOP) Al", imgui.ImVec2(-1, 0)):
                cam.set_view_preset("top")
        else:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.5, 0.5, 1.0), "Kamera bağlı değil",
            )

    def _apply_axis_coords(self):
        try:
            x_list = [float(v.strip()) for v in self._x_text.split(",") if v.strip()]
            y_list = [float(v.strip()) for v in self._y_text.split(",") if v.strip()]
            z_list = [float(v.strip()) for v in self._z_text.split(",") if v.strip()]
        except ValueError:
            logger.error("[GridPanel] Geçersiz aks koordinatı")
            return

        gp = self.grid
        gs = self.grid_system
        if gp is None or gs is None:
            return

        gp.x_coords = list(x_list)
        gp.y_coords = list(y_list)
        gp.z_coords = list(z_list)

        gs.set_coords(x_list, y_list, z_list)

        cam = self.camera
        if cam is not None:
            try:
                center, size = gs.get_bounds()
                cam.update_bounds(center, size)
            except Exception:
                pass

    def _apply_origin(self, x: float, y: float, z: float):
        gp = self.grid
        gs = self.grid_system
        if gp is None or gs is None:
            return
        gp.origin_x = float(x)
        gp.origin_y = float(y)
        gp.origin_z = float(z)
        gs.set_origin(x, y, z)

    # ----------------------------------------------------------------
    # WORK PLANES
    # ----------------------------------------------------------------
    def _draw_work_planes(self):
        gs = self.grid_system

        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Aktif Work Plane",
        )
        imgui.separator()

        active_name = getattr(gs, "active_user_plane", None)
        if active_name is None:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.7, 0.7, 1.0), "(yok — global grid)",
            )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.4, 0.9, 0.5, 1.0), f"Aktif: {active_name}",
            )
            if imgui.button("Aktifliği Kaldır", imgui.ImVec2(-1, 0)):
                gs.set_active_user_plane(None)

        imgui.spacing()
        imgui.separator()
        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Tanımlı Work Plane'ler",
        )
        imgui.separator()

        user_planes = getattr(gs, "user_planes", [])
        if not user_planes:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "  Henüz yok",
            )
        else:
            to_delete = None
            for pdef in user_planes:
                is_active = (pdef.name == active_name)
                ch_vis, val = imgui.checkbox(
                    f"##vis_{pdef.name}", pdef.visible,
                )
                if ch_vis:
                    pdef.visible = val
                    gs.rebuild_user_plane(pdef)

                imgui.same_line()
                if is_active:
                    imgui.push_style_color(
                        imgui.Col_.text, imgui.ImVec4(0.4, 1.0, 0.5, 1.0),
                    )
                imgui.text(pdef.name)
                if is_active:
                    imgui.pop_style_color(1)

                imgui.same_line()
                if imgui.small_button(f"Aktifleştir##{pdef.name}"):
                    gs.set_active_user_plane(pdef.name)

                imgui.same_line()
                if imgui.small_button(f"X##del_{pdef.name}"):
                    to_delete = pdef

            if to_delete is not None:
                gs.remove_user_plane(to_delete.name)

        imgui.spacing()
        imgui.separator()
        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Yeni Work Plane",
        )
        imgui.separator()

        imgui.push_item_width(120)
        _, self._new_name = imgui.input_text("İsim", self._new_name, 64)
        imgui.pop_item_width()

        imgui.spacing()
        imgui.text("Origin (düzlem merkezi):")
        self._draw_vec3_inputs("orig", self._new_origin)

        imgui.spacing()
        imgui.text("Normal (düzlemin baktığı yön):")
        self._draw_vec3_inputs("nrm", self._new_normal)
        imgui.same_line()
        if imgui.small_button("Birimle##nrm_norm"):
            n = glm.normalize(glm.vec3(*self._new_normal))
            self._new_normal = [n.x, n.y, n.z]

        imgui.spacing()
        imgui.text("U Axis (yatay yön):")
        self._draw_vec3_inputs("uax", self._new_u_axis)
        imgui.same_line()
        if imgui.small_button("Dikle##u_perp"):
            n = glm.normalize(glm.vec3(*self._new_normal))
            u = glm.vec3(*self._new_u_axis)
            u = u - n * glm.dot(u, n)
            if glm.length(u) < 1e-6:
                u = glm.vec3(1, 0, 0) - n * n.x
            u = glm.normalize(u)
            self._new_u_axis = [u.x, u.y, u.z]

        imgui.spacing()
        imgui.push_item_width(120)
        _, self._new_spacing_u = imgui.input_float("Spacing U", self._new_spacing_u, step=100.0)
        _, self._new_count_u = imgui.input_int("Count U (her yön)", self._new_count_u)
        _, self._new_spacing_v = imgui.input_float("Spacing V", self._new_spacing_v, step=100.0)
        _, self._new_count_v = imgui.input_int("Count V (her yön)", self._new_count_v)
        imgui.pop_item_width()

        self._new_count_u = max(1, min(200, self._new_count_u))
        self._new_count_v = max(1, min(200, self._new_count_v))
        self._new_spacing_u = max(1.0, self._new_spacing_u)
        self._new_spacing_v = max(1.0, self._new_spacing_v)

        imgui.spacing()
        avail = imgui.get_content_region_avail().x
        btn_w = (avail - 8) * 0.5

        if imgui.button("Ekle", imgui.ImVec2(btn_w, 0)):
            self._create_and_add_plane(activate=False)

        imgui.same_line()
        if imgui.button("Ekle ve Aktifleştir", imgui.ImVec2(btn_w, 0)):
            self._create_and_add_plane(activate=True)

    def _create_and_add_plane(self, activate: bool = False):
        gs = self.grid_system
        if not gs:
            return

        name = (self._new_name or f"PLANE-{self._name_seq}").strip()
        existing = {p.name for p in getattr(gs, "user_planes", [])}
        base = name
        i = 1
        while name in existing:
            name = f"{base}-{i}"
            i += 1
        self._name_seq += 1

        pdef = GridPlaneDef(
            name=name,
            origin=tuple(self._new_origin),
            normal=tuple(self._new_normal),
            u_axis=tuple(self._new_u_axis),
            spacing_u=self._new_spacing_u,
            spacing_v=self._new_spacing_v,
            count_u=self._new_count_u,
            count_v=self._new_count_v,
            visible=True,
        )
        gs.add_user_plane(pdef)
        if activate:
            gs.set_active_user_plane(pdef.name)

    def _draw_vec3_inputs(self, tag: str, vec: list):
        imgui.push_item_width(90)
        imgui.text("X"); imgui.same_line(20)
        _, vec[0] = imgui.input_float(f"##{tag}x", float(vec[0]), step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Y"); imgui.same_line(20)
        _, vec[1] = imgui.input_float(f"##{tag}y", float(vec[1]), step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Z"); imgui.same_line(20)
        _, vec[2] = imgui.input_float(f"##{tag}z", float(vec[2]), step=100.0, format="%.3f")
        imgui.pop_item_width()