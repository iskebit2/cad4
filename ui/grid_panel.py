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
from domain.plane import Plane
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
        self._grid_plane_orientation = "XY"
        self._grid_plane_coordinate: float | None = None
        self._grid_plane_depth: float | None = None
        self._grid_plane_depth_unit = None

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
        if self.project is not None and self._grid_plane_depth is not None:
            new_unit = self.project.unit_system
            if self._grid_plane_depth_unit != new_unit:
                old_default = Plane.default_grid_plane_depth(self._grid_plane_depth_unit)
                new_default = Plane.default_grid_plane_depth(new_unit)
                self._grid_plane_depth *= new_default / old_default
                self._grid_plane_depth_unit = new_unit

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

        gp.x_coords = sorted(set(x_list))
        gp.y_coords = sorted(set(y_list))
        gp.z_coords = sorted(set(z_list))

        gs.set_coords(gp.x_coords, gp.y_coords, gp.z_coords)

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

        self._draw_project_grid_plane_creator()
        imgui.spacing()
        imgui.separator()

        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0), "Aktif Plane",
        )
        imgui.separator()

        project = self.project
        active_plane_id = (
            project.plane_mgr.active_plane_id if project is not None else None
        )
        active_plane = next(
            (
                plane for plane in project.planes.values()
                if plane.plane_id == active_plane_id
            ),
            None,
        ) if project is not None else None
        if active_plane is None:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.7, 0.7, 1.0), "(yok — global grid)",
            )
        else:
            imgui.text_colored(
                imgui.ImVec4(0.4, 0.9, 0.5, 1.0),
                f"Aktif Plane: {active_plane.name}",
            )
            if imgui.button("Plane etkinliğini kaldır", imgui.ImVec2(-1, 0)):
                project.plane_mgr.deactivate()

        active_name = getattr(gs, "active_user_plane", None)
        if active_name is not None:
            imgui.text_colored(
                imgui.ImVec4(0.4, 0.9, 0.5, 1.0),
                f"Aktif GridSystem Work Plane: {active_name}",
            )
            if imgui.button("Grid Work Plane etkinliğini kaldır"):
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
                self.grid.user_planes = [
                    plane for plane in self.grid.user_planes
                    if plane.name != to_delete.name
                ]

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

    def _draw_project_grid_plane_creator(self):
        project = self.project
        if project is None:
            return

        imgui.text_colored(
            imgui.ImVec4(0.5, 0.8, 1.0, 1.0),
            "Project Grid koordinatından Plane oluştur",
        )
        imgui.separator()

        if imgui.begin_combo(
            "Düzlem yönü##grid_plane_orientation",
            self._grid_plane_orientation,
        ):
            for orientation in ("XY", "XZ", "YZ"):
                if imgui.selectable(
                    orientation, orientation == self._grid_plane_orientation,
                )[1]:
                    self._grid_plane_orientation = orientation
                    self._grid_plane_coordinate = None
            imgui.end_combo()

        levels = Plane.grid_levels(project.grid, self._grid_plane_orientation)
        if not levels:
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.6, 0.5, 1.0),
                "Bu yönde kullanılabilir grid koordinatı yok.",
            )
            return
        if self._grid_plane_coordinate not in levels:
            self._grid_plane_coordinate = levels[0]
        level_axis = {"XY": "Z", "XZ": "Y", "YZ": "X"}[
            self._grid_plane_orientation
        ]
        level_label = f"{level_axis} = {self._grid_plane_coordinate:g}"
        if imgui.begin_combo("Grid koordinatı##grid_plane_level", level_label):
            for value in levels:
                label = f"{level_axis} = {value:g}"
                if imgui.selectable(
                    label, value == self._grid_plane_coordinate,
                )[1]:
                    self._grid_plane_coordinate = value
            imgui.end_combo()

        if (
            self._grid_plane_depth is None
            or self._grid_plane_depth_unit != project.unit_system
        ):
            self._grid_plane_depth = Plane.default_grid_plane_depth(
                project.unit_system,
            )
            self._grid_plane_depth_unit = project.unit_system
        depth_unit = project.unit_system.length_unit
        _, self._grid_plane_depth = imgui.input_float(
            f"Derinlik (±, {depth_unit})##grid_plane_depth",
            self._grid_plane_depth,
            step=self._grid_plane_depth * 0.1,
        )
        self._grid_plane_depth = max(0.0, self._grid_plane_depth)

        if imgui.button("Plane oluştur##project_grid_plane", imgui.ImVec2(-1, 0)):
            self._create_project_grid_plane(activate=False)
        if imgui.button(
            "Oluştur ve etkinleştir##project_grid_plane",
            imgui.ImVec2(-1, 0),
        ):
            self._create_project_grid_plane(activate=True)

    def _create_project_grid_plane(self, activate: bool):
        project = self.project
        if project is None or self._grid_plane_coordinate is None:
            return
        try:
            if self._grid_plane_depth_unit != project.unit_system:
                self._grid_plane_depth = Plane.default_grid_plane_depth(
                    project.unit_system,
                )
                self._grid_plane_depth_unit = project.unit_system
            orientation = self._grid_plane_orientation
            level_axis = {"XY": "Z", "XZ": "Y", "YZ": "X"}[orientation]
            name = (
                f"Grid_{orientation}_{level_axis}_"
                f"{self._grid_plane_coordinate:g}"
            )
            base_name = name
            suffix = 1
            while name in project.planes:
                name = f"{base_name}_{suffix}"
                suffix += 1
            plane = Plane.from_grid(
                project.grid,
                orientation,
                grid_coordinate=self._grid_plane_coordinate,
                name=name,
                depth_minus=self._grid_plane_depth,
                depth_plus=self._grid_plane_depth,
            )
            project.add_plane(plane)
            if activate:
                project.plane_mgr.activate(plane)
        except (TypeError, ValueError) as error:
            logger.error("[GridPanel] Grid plane oluşturulamadı: %s", error)

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
        self.grid.user_planes = [
            plane for plane in self.grid.user_planes
            if plane.name != pdef.name
        ]
        self.grid.user_planes.append(pdef)
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