# ui/grid_panel.py
"""GridPanel — Aks koordinatları tabanlı grid ayarları."""
from typing import Optional
import glm
import imgui

from data.enums import GridPlane
from domain.definition import GridPlaneDef
from ui.base_panel import BasePanel

from logging_config import CadLogger
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
        
        self.project = None
        self.camera = None

        
        # Input buffer cache (metin kutularının anlık durumu için)
        self._x_text = ""
        self._y_text = ""
        self._z_text = ""
        self._initialized_texts = False

        # Yeni work plane form buffer
        self._new_name = "PLANE-1"
        self._new_origin = [0.0, 0.0, 3000.0]
        self._new_normal = [0.0, 0.0, 1.0]
        self._new_u_axis = [1.0, 0.0, 0.0]
        self._new_spacing_u = 1000.0
        self._new_spacing_v = 1000.0
        self._new_count_u = 10
        self._new_count_v = 10
        self._name_seq = 1

        self._active_tab = 0  # 0 = Global Grid, 1 = Work Planes

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _camera(self):
        return getattr(getattr(self.app, "engine", None), "cam", None) if self.app else None
    
    def open(self):
        self.project = self._project()
        self.camera = self._camera()
        super().open()
        g = self.grid
        if g is not None:
            # Mevcut koordinatları string'e çevir[cite: 11]
            self._x_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.x_coords]))
            self._y_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.y_coords]))
            self._z_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.z_coords]))
            self._initialized_texts = True
            
    @property
    def grid(self):
        """Doğrudan ana motorun GridSystem (OpenGL renderer) nesnesini döndürür."""
        if self.app:
            engine = getattr(self.app, "engine", None)
            if engine and hasattr(engine, "grid"):
                return engine.grid
        return None

    def get_label_anchors(self):
        """
        Her plane için label anchor noktaları döner.
        """
        g = self.grid
        if not g:
            return []

        ox, oy, oz = g.origin_x, g.origin_y, g.origin_z
        xs = [ox + x for x in g.x_coords]
        ys = [oy + y for y in g.y_coords]
        zs = [oz + z for z in g.z_coords]
        
        if not xs or not ys or not zs:
            return []
        
        labels = []
        for plane, p in g.planes_visibility.items():
            # Not: Plane görünürlük sözlüğü yapısına göre uyarlanmıştır.
            pass
            
        return labels

    # ------------------------------------------------------------------
    def draw_content(self):
        g = self.grid
        if g is None:
            imgui.text_colored("Grid bağlı değil (Project bulunamadı)", 0.9, 0.5, 0.5, 1.0)
            return

        # Sekmeler
        if imgui.begin_tab_bar("grid_tabs"):
            if imgui.begin_tab_item("Global Grid")[0]:
                self._draw_global_grid()
                imgui.end_tab_item()
            if imgui.begin_tab_item("Work Planes")[0]:
                self._draw_work_planes()
                imgui.end_tab_item()
            imgui.end_tab_bar()

    # ------------------------------------------------------------------
    # GLOBAL GRID
    # ------------------------------------------------------------------
    def _draw_global_grid(self):
        g = self.grid

        if not self._initialized_texts:
            self._x_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.x_coords]))
            self._y_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.y_coords]))
            self._z_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in g.z_coords]))
            self._initialized_texts = True

        imgui.text_colored("Düzlemler", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        
        # GridSystem.planes yapısı: {GridPlane.XY: {"visible": True}, ...}
        for plane in self.PLANES:
            if plane in g.planes:
                is_vis = g.planes[plane].get("visible", False)
                changed, val = imgui.checkbox(f"  {plane.name} Düzlemi##vis", is_vis)
                if changed:
                    g.set_plane(plane, visible=val)

        imgui.spacing()
        imgui.separator()

        imgui.text_colored("Aks Koordinatları (Virgülle ayırın)", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        _, self._x_text = imgui.input_text("X Aksları", self._x_text, 256)
        _, self._y_text = imgui.input_text("Y Aksları", self._y_text, 256)
        _, self._z_text = imgui.input_text("Z Kotları", self._z_text, 256)

        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            try:
                # String'i virgüllere göre bölüp float'a çevir
                x_list = [float(v.strip()) for v in self._x_text.split(",") if v.strip()]
                y_list = [float(v.strip()) for v in self._y_text.split(",") if v.strip()]
                z_list = [float(v.strip()) for v in self._z_text.split(",") if v.strip()]
                
                
                
                # 1. Görsel Engine Grid'i güncelle
                if g and hasattr(g, "set_coords"):
                    g.set_coords(x_list, y_list, z_list)

                # 2. Proje modelini (Single Source of Truth) güncelle ki save() sırasında diske yazılsın!
                proj = self._project()
                if proj and hasattr(proj, "grid") and proj.grid:
                    proj.grid.x_coords = list(x_list)
                    proj.grid.y_coords = list(y_list)
                    proj.grid.z_coords = list(z_list)

                engine = getattr(self.app, "engine", None) if self.app else None
                camera = getattr(engine, "cam", None) if engine else None
                if camera and hasattr(g, "get_bounds"):
                    center, size = g.get_bounds()
                    camera.update_bounds(center, size)
            except Exception as e:
                logger.error(f"[Panel Hata] Uygula sırasında hata: {e}")

        imgui.spacing()
        imgui.separator()

        imgui.text_colored("Origin (Kaydırma Merkezi)", 0.5, 0.8, 1.0, 1.0)
        ox, oy, oz = g.origin.x, g.origin.y, g.origin.z
        imgui.text("X"); imgui.same_line(30)
        cx, ox = imgui.input_float("##ox", ox, step=100.0)
        imgui.same_line(); imgui.text("Y"); imgui.same_line(30)
        cy, oy = imgui.input_float("##oy", oy, step=100.0)
        imgui.same_line(); imgui.text("Z"); imgui.same_line(30)
        cz, oz = imgui.input_float("##oz", oz, step=100.0)
        if cx or cy or cz:
            g.set_origin(ox, oy, oz)  # GridSystem.set_origin otomatik rebuild_all çağırır

        engine = getattr(self.app, "engine", None) if self.app else None
        camera = getattr(engine, "cam", None) if engine else None

        if camera is not None and hasattr(g, "get_bounds"):
            if imgui.button("Origin → Model Merkezi", width=-1):
                center, size = g.get_bounds()
                g.set_origin(float(center.x), float(center.y), float(center.z))
                camera.update_bounds(center, size)

        imgui.spacing()
        imgui.separator()

        imgui.text_colored("Kamera Hizalama", 0.5, 0.8, 1.0, 1.0)
        if camera is not None:
            if imgui.button("Kamerayı Üst Görünüşe (TOP) Al", width=-1):
                camera.set_view_preset("top")
        else:
            imgui.text_colored("Kamera bağlı değil", 0.7, 0.5, 0.5, 1.0)

    # ------------------------------------------------------------------
    # WORK PLANES
    # ------------------------------------------------------------------
    def _draw_work_planes(self):
        g = self.grid

        imgui.text_colored("Aktif Work Plane", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        active_name = getattr(g, "active_user_plane", None)
        if active_name is None:
            imgui.text_colored("(yok — global grid)", 0.7, 0.7, 0.7, 1.0)
        else:
            imgui.text_colored(f"Aktif: {active_name}", 0.4, 0.9, 0.5, 1.0)
            if imgui.button("Aktifliği Kaldır", width=-1):
                if hasattr(g, "set_active_user_plane"):
                    g.set_active_user_plane(None)

        imgui.spacing()
        imgui.separator()

        # ---- Mevcut plane listesi ----
        imgui.text_colored("Tanımlı Work Plane'ler", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        user_planes = getattr(g, "user_planes", [])
        if not user_planes:
            imgui.text_colored("  Henüz yok", 0.6, 0.6, 0.6, 1.0)
        else:
            to_delete = None
            for pdef in user_planes:
                is_active = (pdef.name == active_name)
                ch_vis, val = imgui.checkbox(f"##vis_{pdef.name}", pdef.visible)
                if ch_vis:
                    pdef.visible = val
                    if hasattr(g, "rebuild_user_plane"):
                        g.rebuild_user_plane(pdef)

                imgui.same_line()
                if is_active:
                    imgui.push_style_color(imgui.COLOR_TEXT, 0.4, 1.0, 0.5, 1.0)
                imgui.text(pdef.name)
                if is_active:
                    imgui.pop_style_color(1)

                imgui.same_line()
                if imgui.small_button(f"Aktifleştir##{pdef.name}"):
                    self._activate_work_plane(pdef)

                imgui.same_line()
                if imgui.small_button(f"X##del_{pdef.name}"):
                    to_delete = pdef

            if to_delete is not None and hasattr(g, "remove_user_plane"):
                g.remove_user_plane(to_delete.name)

        imgui.spacing()
        imgui.separator()

        # ---- Yeni plane formu ----
        imgui.text_colored("Yeni Work Plane", 0.5, 0.8, 1.0, 1.0)
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
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        if imgui.button("Ekle", width=btn_w):
            self._create_and_add_plane(activate=False)

        imgui.same_line()
        if imgui.button("Ekle ve Aktifleştir", width=btn_w):
            self._create_and_add_plane(activate=True)

    def _create_and_add_plane(self, activate: bool = False):
        g = self.grid
        if not g:
            return

        name = (self._new_name or f"PLANE-{self._name_seq}").strip()
        existing = {p.name for p in getattr(g, "user_planes", [])}
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
        
        if hasattr(g, "add_user_plane"):
            g.add_user_plane(pdef)
            
        if activate:
            self._activate_work_plane(pdef)

    # ------------------------------------------------------------------
    def _draw_vec3_inputs(self, tag: str, vec: list):
        imgui.push_item_width(90)
        imgui.text("X"); imgui.same_line(20)
        _, vec[0] = imgui.input_float(f"##{tag}x", float(vec[0]), step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Y"); imgui.same_line(20)
        _, vec[1] = imgui.input_float(f"##{tag}y", float(vec[1]), step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Z"); imgui.same_line(20)
        _, vec[2] = imgui.input_float(f"##{tag}z", float(vec[2]), step=100.0, format="%.3f")
        imgui.pop_item_width()

    # ------------------------------------------------------------------
    def _activate_work_plane(self, pdef: GridPlaneDef):
        g = self.grid
        if g and hasattr(g, "set_active_user_plane"):
            g.set_active_user_plane(pdef.name)