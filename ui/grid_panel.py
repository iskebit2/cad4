# ui/grid_panel.py
"""GridPanel — Aks koordinatları tabanlı grid ayarları."""
from typing import Callable, Optional
import glm
import imgui

from data.enums import GridPlane
from domain.definition import GridPlaneDef
from ui.base_panel import BasePanel

class GridPanel(BasePanel):
    PLANES = [GridPlane.XY, GridPlane.XZ, GridPlane.YZ]

    def __init__(self, on_change: Optional[Callable] = None,
                 on_work_plane_activate: Optional[Callable] = None):
        super().__init__(
            title="Grid ve Work Plane",
            width=400, height=500,
            pos_first_use=(480, 100),
        )
        self.grid = None
        self.camera = None
        self.on_change = on_change
        self.on_work_plane_activate = on_work_plane_activate

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

    def open(self, grid=None, camera=None):
        super().open()
        if grid is not None:
            self.grid = grid
            # Mevcut koordinatları string'e çevir
            self._x_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in grid.x_coords]))
            self._y_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in grid.y_coords]))
            self._z_text = ", ".join(map(str, [int(v) if v.is_integer() else v for v in grid.z_coords]))
            self._initialized_texts = True
        if camera is not None:
            self.camera = camera

    def get_label_anchors(self):
        """
        Her plane için label anchor noktaları döner.
        
        Returns
        -------
        list[dict]:
            Her biri: {
                'pos': (x,y,z) dünya koordinatı,
                'text': 'X1' gibi,
                'axis': 'X'|'Y'|'Z',
                'plane': GridPlane
            }
        """
        ox, oy, oz = self.origin.x, self.origin.y, self.origin.z
        xs = [ox + x for x in self.x_coords]
        ys = [oy + y for y in self.y_coords]
        zs = [oz + z for z in self.z_coords]
        
        if not xs or not ys or not zs:
            return []
        
        labels = []
        # Label'ları grid kenarından biraz dışarı taşıyalım (kullanıcı görsün)
        # Axis sırası: X, Y, Z (grid standartı)
        
        for plane, p in self.planes.items():
            if not p["visible"]:
                continue
                
            if plane == GridPlane.XY:
                # Alt kenar (Y=min) boyunca X etiketleri
                y_edge = ys[0]
                for i, x in enumerate(xs):
                    labels.append({
                        "pos": (x, y_edge, zs[0]),
                        "text": f"X{i+1}",
                        "axis": "X",
                        "plane": plane,
                    })
                # Sol kenar (X=min) boyunca Y etiketleri
                x_edge = xs[0]
                for i, y in enumerate(ys):
                    labels.append({
                        "pos": (x_edge, y, zs[0]),
                        "text": f"Y{i+1}",
                        "axis": "Y",
                        "plane": plane,
                    })
            
            elif plane == GridPlane.XZ:
                # Z=min hizasında X etiketleri (Y=min kenarında)
                y_edge = ys[0]
                for i, x in enumerate(xs):
                    labels.append({
                        "pos": (x, y_edge, zs[0]),
                        "text": f"X{i+1}",
                        "axis": "X",
                        "plane": plane,
                    })
                # X=min kenarında Z etiketleri
                x_edge = xs[0]
                for i, z in enumerate(zs):
                    labels.append({
                        "pos": (x_edge, y_edge, z),
                        "text": f"Z{i+1}",
                        "axis": "Z",
                        "plane": plane,
                    })
            
            elif plane == GridPlane.YZ:
                x_edge = xs[0]
                for i, y in enumerate(ys):
                    labels.append({
                        "pos": (x_edge, y, zs[0]),
                        "text": f"Y{i+1}",
                        "axis": "Y",
                        "plane": plane,
                    })
                for i, z in enumerate(zs):
                    labels.append({
                        "pos": (x_edge, ys[0], z),
                        "text": f"Z{i+1}",
                        "axis": "Z",
                        "plane": plane,
                    })
        
        return labels

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.grid is None:
            imgui.text_colored("Grid bağlı değil", 0.9, 0.5, 0.5, 1.0)
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
    # GLOBAL GRID (mevcut içerik)
    # ------------------------------------------------------------------
    def _draw_global_grid(self):
        g = self.grid

        if not self._initialized_texts:
            self._x_text = ", ".join(map(str, g.x_coords))
            self._y_text = ", ".join(map(str, g.y_coords))
            self._z_text = ", ".join(map(str, g.z_coords))
            self._initialized_texts = True

        imgui.text_colored("Düzlemler", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        for plane in self.PLANES:
            p = g.planes[plane]
            changed, val = imgui.checkbox(
                f"  {plane.name} Düzlemi##vis", p["visible"])
            if changed:
                g.set_plane(plane, visible=val)
                self._notify()

        imgui.spacing()
        imgui.separator()

        imgui.text_colored("Aks Koordinatları (Virgülle ayırın)",
                           0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        _, self._x_text = imgui.input_text("X Aksları", self._x_text, 256)
        _, self._y_text = imgui.input_text("Y Aksları", self._y_text, 256)
        _, self._z_text = imgui.input_text("Z Kotları", self._z_text, 256)

        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            try:
                x_list = [float(v.strip()) for v in self._x_text.split(",") if v.strip()]
                y_list = [float(v.strip()) for v in self._y_text.split(",") if v.strip()]
                z_list = [float(v.strip()) for v in self._z_text.split(",") if v.strip()]
                g.set_coords(x_list, y_list, z_list)
                if self.camera:
                    center, size = g.get_bounds()
                    self.camera.update_bounds(center, size)
                self._notify()
            except ValueError:
                pass

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
            g.set_origin(ox, oy, oz)
            self._notify()

        if self.camera is not None:
            if imgui.button("Origin → Model Merkezi", width=-1):
                center, size = g.get_bounds()
                g.set_origin(float(center.x), float(center.y), float(center.z))
                self.camera.update_bounds(center, size)
                self._notify()

        imgui.spacing()
        imgui.separator()

        imgui.text_colored("Kamera Hizalama", 0.5, 0.8, 1.0, 1.0)
        if self.camera is not None:
            if imgui.button("Kamerayı Üst Görünüşe (TOP) Al", width=-1):
                self.camera.set_view_preset("top")
                self._notify()
        else:
            imgui.text_colored("Kamera bağlı değil", 0.7, 0.5, 0.5, 1.0)

    # ------------------------------------------------------------------
    # WORK PLANES
    # ------------------------------------------------------------------
    def _draw_work_planes(self):
        g = self.grid

        imgui.text_colored("Aktif Work Plane", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        active_name = g.active_user_plane
        if active_name is None:
            imgui.text_colored("(yok — global grid)", 0.7, 0.7, 0.7, 1.0)
        else:
            imgui.text_colored(f"Aktif: {active_name}", 0.4, 0.9, 0.5, 1.0)
            if imgui.button("Aktifliği Kaldır", width=-1):
                g.set_active_user_plane(None)
                self._notify()

        imgui.spacing()
        imgui.separator()

        # ---- Mevcut plane listesi ----
        imgui.text_colored("Tanımlı Work Plane'ler", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()

        if not g.user_planes:
            imgui.text_colored("  Henüz yok", 0.6, 0.6, 0.6, 1.0)
        else:
            to_delete = None
            for pdef in g.user_planes:
                is_active = (pdef.name == active_name)
                # Görünürlük checkbox
                ch_vis, val = imgui.checkbox(
                    f"##vis_{pdef.name}", pdef.visible)
                if ch_vis:
                    pdef.visible = val
                    g.rebuild_user_plane(pdef)
                    self._notify()

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

            if to_delete is not None:
                g.remove_user_plane(to_delete.name)
                self._notify()

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
            # U'yu normal'e dikleştir
            n = glm.normalize(glm.vec3(*self._new_normal))
            u = glm.vec3(*self._new_u_axis)
            u = u - n * glm.dot(u, n)
            if glm.length(u) < 1e-6:
                u = glm.vec3(1, 0, 0) - n * n.x
            u = glm.normalize(u)
            self._new_u_axis = [u.x, u.y, u.z]

        imgui.spacing()
        imgui.push_item_width(120)
        _, self._new_spacing_u = imgui.input_float(
            "Spacing U", self._new_spacing_u, step=100.0)
        _, self._new_count_u = imgui.input_int(
            "Count U (her yön)", self._new_count_u)
        _, self._new_spacing_v = imgui.input_float(
            "Spacing V", self._new_spacing_v, step=100.0)
        _, self._new_count_v = imgui.input_int(
            "Count V (her yön)", self._new_count_v)
        imgui.pop_item_width()

        # Sınırla
        self._new_count_u = max(1, min(200, self._new_count_u))
        self._new_count_v = max(1, min(200, self._new_count_v))
        self._new_spacing_u = max(1.0, self._new_spacing_u)
        self._new_spacing_v = max(1.0, self._new_spacing_v)

        imgui.spacing()

        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        if imgui.button("Ekle", width=btn_w):
            name = (self._new_name or f"PLANE-{self._name_seq}").strip()
            # Çakışma varsa suffix ekle
            existing = {p.name for p in g.user_planes}
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
            g.add_user_plane(pdef)
            self._notify()

        imgui.same_line()
        if imgui.button("Ekle ve Aktifleştir", width=btn_w):
            name = (self._new_name or f"PLANE-{self._name_seq}").strip()
            existing = {p.name for p in g.user_planes}
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
            g.add_user_plane(pdef)
            self._activate_work_plane(pdef)

    # ------------------------------------------------------------------
    def _draw_vec3_inputs(self, tag: str, vec: list):
        imgui.push_item_width(90)
        imgui.text("X"); imgui.same_line(20)
        cx, vec[0] = imgui.input_float(f"##{tag}x", float(vec[0]),
                                        step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Y"); imgui.same_line(20)
        cy, vec[1] = imgui.input_float(f"##{tag}y", float(vec[1]),
                                        step=100.0, format="%.3f")
        imgui.same_line(); imgui.text("Z"); imgui.same_line(20)
        cz, vec[2] = imgui.input_float(f"##{tag}z", float(vec[2]),
                                        step=100.0, format="%.3f")
        imgui.pop_item_width()

    # ------------------------------------------------------------------
    def _activate_work_plane(self, pdef: GridPlaneDef):
        g = self.grid
        g.set_active_user_plane(pdef.name)
        self._notify()

        if callable(self.on_work_plane_activate):
            try:
                self.on_work_plane_activate(pdef)
            except Exception:
                import traceback
                traceback.print_exc()

    # ------------------------------------------------------------------
    def _notify(self):
        if callable(self.on_change):
            try:
                self.on_change()
            except Exception:
                import traceback
                traceback.print_exc()