# ui/viewport_panel.py
from __future__ import annotations
from pyglm import glm
from imgui_bundle import imgui
from ui.base_panel import BasePanel

from logging_config import CadLogger
logger = CadLogger.get(__name__)

class ViewportPanel(BasePanel):
    _PRESET_POSITIONS = {
        "top": (50, 100), "bottom": (50, 100),
        "front": (400, 100), "back": (400, 100),
        "left": (750, 100), "right": (750, 100),
        "iso": (400, 300), "iso_sw": (400, 300),
        "iso_se": (750, 300), "iso_ne": (400, 500),
        "iso_nw": (750, 500),
    }
    _MIN_W = 400
    _MIN_H = 300

    def __init__(self, app, viewport_name: str, manager, preset: str | None = None):
        super().__init__(
            title=f"Viewport: {viewport_name}",
            width=800, height=600,
            pos_first_use=self._PRESET_POSITIONS.get(preset or "", (300, 200)),
        )
        self.viewport_name = viewport_name
        self.manager = manager
        self.app = app
        self.visible = True
        self.plane = None
        self.is_2d: bool = False

        self._is_hovered: bool = False
        self._item_min = imgui.ImVec2(0.0, 0.0)
        
        # Ek UI ve geçici düzenleme durumları
        self.show_plane_settings: bool = False
        self._plane_edit_loaded_for: str | None = None
        self._edit_u_min = 0.0
        self._edit_u_max = 0.0
        self._edit_v_min = 0.0
        self._edit_v_max = 0.0
        self._edit_depth_minus = 0.0
        self._edit_depth_plus = 0.0
        self._edit_filter_mode = None

        self.show_filter_popup: bool = False
        # Filtre geçici state
        self._filter_name = ""
        self._filter_types: set[str] = set()
        self._filter_sections: set[str] = set()
        self._filter_materials: set[str] = set()
        self._filter_subtypes: set[str] = set()


    def _load_plane_edit(self, plane):
        """Plane değerlerini geçici düzenleme tamponuna yükler."""
        self._edit_u_min = 0.0 if plane.u_min is None else plane.u_min
        self._edit_u_max = 0.0 if plane.u_max is None else plane.u_max
        self._edit_v_min = 0.0 if plane.v_min is None else plane.v_min
        self._edit_v_max = 0.0 if plane.v_max is None else plane.v_max
        self._edit_depth_minus = plane.depth_minus
        self._edit_depth_plus = plane.depth_plus
        from plane.plane_policy import SectionFilterMode
        self._edit_filter_mode = getattr(plane, "filter_mode", SectionFilterMode.INTERSECT)
        self._plane_edit_loaded_for = plane.plane_id

    def _is_plane_edited(self, plane) -> bool:
        """Tampondaki değerler ile mevcut plane değerlerinin farklı olup olmadığını denetler."""
        from plane.plane_policy import SectionFilterMode
        p_mode = getattr(plane, "filter_mode", SectionFilterMode.INTERSECT)
        return (
            abs(self._edit_u_min - (plane.u_min or 0.0)) > 1e-6
            or abs(self._edit_u_max - (plane.u_max or 0.0)) > 1e-6
            or abs(self._edit_v_min - (plane.v_min or 0.0)) > 1e-6
            or abs(self._edit_v_max - (plane.v_max or 0.0)) > 1e-6
            or abs(self._edit_depth_minus - plane.depth_minus) > 1e-6
            or abs(self._edit_depth_plus - plane.depth_plus) > 1e-6
            or self._edit_filter_mode != p_mode
        )

    def _apply_plane_edit(self, plane):
        """Değişiklikleri plane nesnesine uygular ve render/geometriyi günceller."""
        plane.set_bounds(self._edit_u_min, self._edit_u_max, self._edit_v_min, self._edit_v_max, recenter=False)
        plane.depth_minus = max(0.0, self._edit_depth_minus)
        plane.depth_plus = max(0.0, self._edit_depth_plus)
        if self._edit_filter_mode is not None:
            if hasattr(plane, "set_filter_mode"):
                plane.set_filter_mode(self._edit_filter_mode)
            else:
                plane.filter_mode = self._edit_filter_mode
        
        proj = getattr(self.app, "current_project", None) if self.app else None
        eng = getattr(self.app, "engine", None) if self.app else None
        
        if eng is not None:
            if getattr(plane, "auto_assoc", False):
                try:
                    plane.refresh_assoc(eng.math_model, eng.scene)
                except Exception as e:
                    logger.warning("[ViewportPanel] refresh_assoc hatası: %s", e)
            
            vm = getattr(self.app, "viewport_manager", None)
            if vm is not None:
                vm.invalidate_all_visible_ids()
            
            if proj is not None:
                eng.update_geo(proj)
        
        vp = self.manager.get(self.viewport_name)
        if vp is not None and getattr(vp, "is_2d", False):
            vp.camera.set_section_filter(
                normal=plane.normal, origin=plane.origin,
                min_s=-plane.depth_minus, max_s= plane.depth_plus,
            )
        
        self._plane_edit_loaded_for = plane.plane_id

    def _draw_plane_settings_popup(self, vp):
        """Plane sınırlarını, derinlikleri ve filtreyi 'Apply' mekanizmasıyla düzenler."""
        plane = getattr(vp, "plane", None)
        if plane is None:
            imgui.text("Bu viewport'a ait Plane bulunamadı.")
            return

        if self._plane_edit_loaded_for != getattr(plane, "plane_id", None):
            self._load_plane_edit(plane)

        imgui.begin_child(f"PlaneSettings_{self.viewport_name}", imgui.ImVec2(0, 250), True)
        try:
            imgui.text(f"Plane: {plane.name}")
            imgui.separator()

            imgui.push_item_width(110)
            _, self._edit_u_min = imgui.input_float(f"u min##{plane.plane_id}", self._edit_u_min)
            imgui.same_line()
            _, self._edit_u_max = imgui.input_float(f"u max##{plane.plane_id}", self._edit_u_max)

            _, self._edit_v_min = imgui.input_float(f"v min##{plane.plane_id}", self._edit_v_min)
            imgui.same_line()
            _, self._edit_v_max = imgui.input_float(f"v max##{plane.plane_id}", self._edit_v_max)
            imgui.pop_item_width()

            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Kesit Derinlikleri (Depth)")
            imgui.push_item_width(110)
            _, self._edit_depth_minus = imgui.input_float(f"depth -##{plane.plane_id}", self._edit_depth_minus)
            imgui.same_line()
            _, self._edit_depth_plus = imgui.input_float(f"depth +##{plane.plane_id}", self._edit_depth_plus)
            imgui.pop_item_width()

            imgui.separator()
            from plane.plane_policy import SectionFilterMode
            modes = list(SectionFilterMode)
            current_mode = self._edit_filter_mode if self._edit_filter_mode is not None else SectionFilterMode.INTERSECT
            current_idx = modes.index(current_mode) if current_mode in modes else 0

            imgui.push_item_width(180)
            changed_combo, selected_idx = imgui.combo(f"Filtre Modu##{plane.plane_id}", current_idx, [m.value.upper() for m in modes])
            if changed_combo:
                self._edit_filter_mode = modes[selected_idx]
            imgui.pop_item_width()

            imgui.separator()

            can_apply = self._is_plane_edited(plane)
            if not can_apply:
                imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0))
                
            if imgui.button(f"Apply##apply_plane_{self.viewport_name}", imgui.ImVec2(80, 0)) and can_apply:
                self._apply_plane_edit(plane)
                
            if not can_apply:
                imgui.pop_style_color(1)

            imgui.same_line()
            if imgui.button(f"Revert##revert_plane_{self.viewport_name}", imgui.ImVec2(70, 0)):
                self._load_plane_edit(plane)

            imgui.same_line()
            if imgui.button(f"Kapat##close_plane_{self.viewport_name}", imgui.ImVec2(70, 0)):
                self.show_plane_settings = False
        finally:
            imgui.end_child()

    # ------------------------------------------------------------------
    def draw(self):
        vp = self.manager.get(self.viewport_name)
        if vp is None:
            return

        flags = (
            imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
        )
        expanded, p_open = imgui.begin(
            f"{self.title}###vp_{self.viewport_name}", True, flags,
        )
        
        try:
            if not p_open:
                self._close_and_remove()
                return
            if not expanded:
                self._is_hovered = False
                return
            vp.visible = True
            self._draw_viewport_toolbar(vp)
            if self.show_plane_settings:
                self._draw_plane_settings_popup(vp)
            if self.show_filter_popup:
                self._draw_filter_popup(vp)   # ★ YENİ
            self._draw_content(vp)
        finally:
            imgui.end()

    def _draw_viewport_toolbar(self, vp):
        imgui.push_style_var(imgui.StyleVar_.frame_padding, imgui.ImVec2(4, 2))
        
        # 2D/3D
        is_2d = getattr(vp, "is_2d", False)
        if imgui.button(f"Mode: {'2D' if is_2d else '3D'}##{self.viewport_name}"):
            self._toggle_2d_3d(vp)
        imgui.same_line()
        
        # Plane
        if imgui.button(f"⚙ Plane##{self.viewport_name}"):
            self.show_plane_settings = not self.show_plane_settings
        imgui.same_line()
        
        # ★ Filter Butonu (State'i sadece ilk açılışta yükle)
        has_filter = getattr(vp, "element_filter", None) is not None
        if has_filter:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.9, 0.6, 0.2, 1.0))
        if imgui.button(f"🔍 Filter##{self.viewport_name}"):
            self.show_filter_popup = not self.show_filter_popup
            if self.show_filter_popup:
                self._load_filter_state(vp)  # Sadece açılırken bir kez yüklenir
        if has_filter:
            imgui.pop_style_color(1)
        imgui.same_line()
        
        imgui.text_disabled(f"| {self._get_bounds_summary(vp)}")
        imgui.pop_style_var()
        imgui.separator()
        pfe = getattr(self.app.engine, "_plane_from_element", None) if self.app else None
        if pfe is not None and pfe.active:
            imgui.same_line()
            imgui.text_colored(
                imgui.ImVec4(0.3, 0.9, 0.3, 1.0),
                "● Element seç",
            )
            imgui.same_line()
            axis_text = "1-2" if pfe.frame_axis_12 else "1-3"
            if imgui.button(f"Eksen: {axis_text} (Space)"):
                pfe.frame_axis_12 = not pfe.frame_axis_12
            imgui.same_line()
            if imgui.button("İptal (Esc)"):
                self.app.engine.cancel_plane_from_element()

    def _draw_filter_popup(self, vp):
        """Filtre kurallarını düzenle ve uygula (ID çakışması giderilmiş hali)."""
        if not self.show_filter_popup:
            return
        
        imgui.begin_child(f"Filter_{self.viewport_name}", imgui.ImVec2(0, 280), True)
        imgui.text_colored(imgui.ImVec4(0.8, 0.85, 0.95, 1.0), "Element Filtresi")
        imgui.separator()
        
        # İsim
        imgui.push_item_width(200)
        _, self._filter_name = imgui.input_text(f"İsim (glob)##filter_name_{self.viewport_name}", self._filter_name, 128)
        imgui.pop_item_width()
        
        # Element tipleri
        imgui.text("Tipler:")
        for t in ("Frame", "Node", "Area", "Link", "Polygon", "Line"):
            checked = t in self._filter_types
            # ID çakışmasını önlemek için benzersiz scope eklendi
            clicked, new_checked = imgui.checkbox(f"{t}##ftype_{t}_{self.viewport_name}", checked)
            if clicked:
                if new_checked: 
                    self._filter_types.add(t)
                else: 
                    self._filter_types.discard(t)
            imgui.same_line()
        imgui.new_line()
        
        # Frame subtype
        if "Frame" in self._filter_types or not self._filter_types:
            imgui.text("Frame Alt-tip:")
            for sub in ("column", "beam", "brace"):
                checked = sub in self._filter_subtypes
                clicked, new_checked = imgui.checkbox(f"{sub}##fsub_{sub}_{self.viewport_name}", checked)
                if clicked:
                    if new_checked: 
                        self._filter_subtypes.add(sub)
                    else: 
                        self._filter_subtypes.discard(sub)
                imgui.same_line()
            imgui.new_line()
        
        # Sections (mevcut kesitlerden seç)
        proj = getattr(self.app, "current_project", None)
        if proj is not None:
            all_sections = self._collect_sections(proj)
            if all_sections:
                imgui.text("Kesitler:")
                for s in sorted(all_sections):
                    checked = s in self._filter_sections
                    clicked, new_checked = imgui.checkbox(f"{s}##fsec_{s}_{self.viewport_name}", checked)
                    if clicked:
                        if new_checked: 
                            self._filter_sections.add(s)
                        else: 
                            self._filter_sections.discard(s)
        
        imgui.separator()
        
        # Apply / Clear / Close
        if imgui.button(f"Apply##apply_filt_{self.viewport_name}", imgui.ImVec2(80, 0)):
            self._apply_filter(vp)
        imgui.same_line()
        if imgui.button(f"Temizle##clear_filt_{self.viewport_name}", imgui.ImVec2(80, 0)):
            self._clear_filter(vp)
        imgui.same_line()
        if imgui.button(f"Kapat##close_filt_{self.viewport_name}", imgui.ImVec2(80, 0)):
            self.show_filter_popup = False
        
        imgui.end_child()

    def _load_filter_state(self, vp):
        """Viewport'un filter'ını UI state'ine yükle."""
        q = getattr(vp, "element_filter", None)
        if q is None:
            self._filter_name = ""
            self._filter_types = set()
            self._filter_sections = set()
            self._filter_materials = set()
            self._filter_subtypes = set()
        else:
            self._filter_name = q.name_pattern or ""
            self._filter_types = set(q.element_types)
            self._filter_sections = set(q.sections)
            self._filter_materials = set(q.materials)
            self._filter_subtypes = set(q.structural_subtypes)

    def _apply_filter(self, vp):
        """UI state'inden ElementFilterQuery oluştur ve viewport'a ata."""
        from tools.filter_query import ElementFilterQuery
        q = ElementFilterQuery(
            name_pattern=self._filter_name.strip() or None,
            element_types=set(self._filter_types),
            sections=set(self._filter_sections),
            materials=set(self._filter_materials),
            structural_subtypes=set(self._filter_subtypes),
        )
        vp.set_element_filter(q if not q.is_empty() else None)
        logger.debug("[ViewportPanel] filter uygulandı: %s", vp.name)

    def _clear_filter(self, vp):
        vp.set_element_filter(None)
        self._filter_name = ""
        self._filter_types.clear()
        self._filter_sections.clear()
        self._filter_materials.clear()
        self._filter_subtypes.clear()

    def _collect_sections(self, project):
        """Projede kullanılan tüm kesit isimlerini topla."""
        names = set()
        try:
            for f in project.math_model.frames.values():
                sec = getattr(f, "section", None)
                if sec is not None:
                    names.add(getattr(sec, "name", str(sec)))
        except Exception:
            pass
        return names

    def _get_bounds_summary(self, vp) -> str:
        """Viewport'a bağlı plane sınırlarının özetini döndürür."""
        plane = getattr(vp, "plane", None)
        if plane and hasattr(plane, "boundary"):
            u_min, u_max, v_min, v_max = plane.boundary
            if u_min is not None and u_max is not None:
                return f"U[{u_min:.0f}, {u_max:.0f}] V[{v_min:.0f}, {v_max:.0f}]"
        return "Sınırsız"

    def _draw_content(self, vp):
        avail = imgui.get_content_region_avail()
        w = max(self._MIN_W, int(avail.x))
        h = max(self._MIN_H, int(avail.y))
        vp.resize(w, h)

        imgui.image(
            imgui.ImTextureRef(vp.texture_id()),
            imgui.ImVec2(float(w), float(h)),
            imgui.ImVec2(0, 1),
            imgui.ImVec2(1, 0),
        )
        self._item_min = imgui.get_item_rect_min()
        self._is_hovered = imgui.is_item_hovered()
        self._draw_marquee_overlay(vp)

    def _draw_marquee_overlay(self, vp):
        eng = self.app.engine if self.app is not None else None
        if eng is None:
            return
        marquee = eng.marquee
        if marquee is None or not marquee.is_active:
            return
        if (marquee.viewport_name is not None
                and marquee.viewport_name != self.viewport_name):
            return
        coords = marquee.get_box_coords()
        if coords is None:
            return
        x1, y1, x2, y2 = coords
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        mn_x, mx_x = min(x1, x2), max(x1, x2)
        mn_y, mx_y = min(y1, y2), max(y1, y2)
        p0 = imgui.ImVec2(self._item_min.x + mn_x, self._item_min.y + mn_y)
        p1 = imgui.ImVec2(self._item_min.x + mx_x, self._item_min.y + mx_y)

        if x2 < x1:
            fill = imgui.ImVec4(0.20, 0.85, 0.20, 0.22)
            border = imgui.ImVec4(0.30, 1.00, 0.30, 0.95)
        else:
            fill = imgui.ImVec4(0.20, 0.50, 0.95, 0.22)
            border = imgui.ImVec4(0.40, 0.75, 1.00, 0.95)

        dl = imgui.get_window_draw_list()
        dl.add_rect_filled(p0, p1, imgui.get_color_u32(fill))
        dl.add_rect(p0, p1, imgui.get_color_u32(border))

    def _close_and_remove(self):
        self.manager.remove_viewport(self.viewport_name)
        if self.app is not None:
            try:
                self.app._viewport_panels.remove(self)
            except ValueError:
                pass
            if self.app._last_active_viewport_name == self.viewport_name:
                self.app._last_active_viewport_name = None

    def _toggle_2d_3d(self, vp):
        """Viewport'u 2D (Camera.look_at_plane) ve 3D (Camera.restore_view) modlar arasında değiştir."""
        eng = getattr(self.app, "engine", None) if self.app else None
        if eng is None:
            return
        
        new_mode = not getattr(vp, "is_2d", False)
        
        if new_mode:
            plane = getattr(vp, "plane", None)
            if plane is None:
                proj = getattr(self.app, "current_project", None)
                if proj is not None:
                    plane = eng.default_xy_plane()
                    if plane is not None:
                        vp.plane = plane
            if plane is None:
                logger.warning("[ViewportPanel] 2D moda geçilemedi: plane yok")
                return
            
            # Camera sınıfındaki yerleşik save_view metodunu kullanıyoruz
            vp.camera.save_view()
            
            uc = 0.5 * ((plane.u_min or 0.0) + (plane.u_max or 0.0))
            vc = 0.5 * ((plane.v_min or 0.0) + (plane.v_max or 0.0))
            center = plane.to_3d((uc, vc))
            half_u = 0.5 * abs((plane.u_max or 0.0) - (plane.u_min or 0.0))
            half_v = 0.5 * abs((plane.v_max or 0.0) - (plane.v_min or 0.0))
            fit_radius = max(half_u, half_v) * 1.4
            if fit_radius < 1e-6:
                bounds = eng._combined_bounds()
                fit_radius = float(bounds.size) if bounds else 1000.0
            
            # Camera sınıfındaki look_at_plane metodunu çağırıyoruz
            vp.camera.look_at_plane(
                origin=center,
                u=plane.u, v=plane.v, n=plane.normal,
                fit_radius=fit_radius,
            )
            vp.camera.set_section_filter(
                normal=plane.normal, origin=plane.origin,
                min_s=-plane.depth_minus, max_s=+plane.depth_plus,
            )
            vp.is_2d = True
        else:
            # Camera sınıfındaki restore_view metodunu kullanıyoruz
            restored = vp.camera.restore_view()
            if not restored:
                vp.camera.reset()
            vp.camera.clear_section_filter()
            vp.is_2d = False
        
        vp.invalidate_visible_ids()