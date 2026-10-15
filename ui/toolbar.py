# ui/toolbar.py
"""
ImGui Toolbar — Sekmeli ve kategorize edilmiş modern üst şerit.
"""
from typing import Callable, Dict
from domain.definition import UnitSystem
import imgui


class Toolbar:
    HEIGHT = 32.0

    def __init__(self, callbacks: Dict[str, Callable], panel_states: Dict[str, Callable] = None):
        self.callbacks = callbacks or {}
        self.panel_states = panel_states or {}
        self.current_unit = None

    def draw(self, model_text: str = "MODEL: YENİ SAHNE", draw_active: bool = False, current_unit=None):
        self.current_unit = current_unit
        flags = (
            imgui.WINDOW_NO_SCROLLBAR
            | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
            | imgui.WINDOW_NO_SAVED_SETTINGS
        )

        try:
            imgui.begin_viewport_side_bar(imgui.DIRECTION_UP, True, self.HEIGHT, flags)
        except AttributeError:
            imgui.begin_main_menu_bar()
            self._draw_content(model_text, draw_active)
            imgui.end_main_menu_bar()
            return

        self._draw_content(model_text, draw_active)
        imgui.end()

    def _draw_content(self, model_text: str, draw_active: bool):
        # --- Dosya & Proje Grubu ---
        if imgui.button("≡ Menü"):
            self._fire("menu")
        imgui.same_line()

        self._styled_button("Aç", (0.18, 0.35, 0.55, 1.00), lambda: self._fire("open"))
        imgui.same_line()
        self._styled_button("Kaydet", (0.18, 0.50, 0.32, 1.00), lambda: self._fire("save"))
        imgui.same_line()

        imgui.separator()
        imgui.same_line()

        # --- Çizim Modu ---
        if draw_active:
            draw_color, draw_label = (0.20, 0.60, 0.35, 1.00), "Çizim [AÇIK]"
        else:
            draw_color, draw_label = (0.22, 0.28, 0.38, 1.00), "Çiz (D)"
        self._styled_button(draw_label, draw_color, lambda: self._fire("draw"))
        imgui.same_line()

        imgui.separator()
        imgui.same_line()

        # --- Assign (Yük Atama) Grubu ---
        assign_state = self._get_panel_state("assign_area_load")
        assign_color = (0.25, 0.45, 0.65, 1.00) if not assign_state else (0.35, 0.65, 0.45, 1.00)
        
        if imgui.begin_menu("Assign (Atama)"):
            if imgui.menu_item("Assign Area Load to Frame...", selected=assign_state)[0]:
                self._fire("assign_area_load")
            
            imgui.separator()
            # Diğer yük atama butonları için yerler (Şimdilik boş/pasif)
            if imgui.menu_item("Assign Frame Load... (Yakında)", selected=False, enabled=False)[0]:
                pass
            if imgui.menu_item("Assign Joint Load... (Yakında)", selected=False, enabled=False)[0]:
                pass
            if imgui.menu_item("Assign Area Uniform Load... (Yakında)", selected=False, enabled=False)[0]:
                pass
            imgui.separator()
            if imgui.menu_item("Distribute Selected Polygon Loads")[0]:
                self._fire("distribute_polygon_loads")
            if imgui.menu_item("Assign Frame Load... (Yakında)", selected=False, enabled=False)[0]:
                pass
            imgui.separator()
            if imgui.menu_item("Align Frames to Polygon Plane")[0]:
                self._fire("align_frames_to_polygon")
            imgui.separator()
            if imgui.menu_item("Check Load Balance")[0]:
                self._fire("check_load_balance")
            imgui.end_menu()
        imgui.same_line()

        imgui.separator()
        imgui.same_line()

        if imgui.begin_menu("Görünüm & Araçlar"):
            vis_state = self._get_panel_state("visibility")
            filter_state = self._get_panel_state("view_filter")
            grid_state = self._get_panel_state("grid")
            inspector_state = self._get_panel_state("inspector")

            if imgui.menu_item("Görünürlük Paneli (Visibility)", selected=vis_state)[0]:
                self._fire("visibility")
            if imgui.menu_item("Görünüm Filtresi (View Filter - F6)", selected=filter_state)[0]:
                self._fire("view_filter")
            if imgui.menu_item("Grid Ayarları (Grid - Ctrl+G)", selected=grid_state)[0]:
                self._fire("grid")
            if imgui.menu_item("Grid Etiketleri", selected=self.panel_states.get("grid_labels", lambda: True)())[0]:
                self._fire("grid_labels")
            if imgui.menu_item("Inspector (Ctrl+P)", selected=inspector_state)[0]:
                self._fire("inspector")

            imgui.separator()

            if imgui.menu_item("Render Modu Değiştir (F3)")[0]:
                self._fire("render_mode")
            if imgui.menu_item("Akıllı Düzlem Modu (F11)", selected=self._get_panel_state("smart_plane"))[0]:
                self._fire("smart_plane")

            imgui.separator()

            # --- LOCAL AXES ---
            axes_on       = self._get_panel_state("local_axes")
            axes_sel_only = self._get_panel_state("local_axes_selected_only")

            if imgui.menu_item("Local Axes Göster (E)", selected=axes_on)[0]:
                self._fire("local_axes")
            if imgui.menu_item("  └ Sadece Seçililerde",
                            selected=axes_sel_only,
                            enabled=axes_on)[0]:
                self._fire("local_axes_selected_only")

            imgui.end_menu()
        imgui.same_line()

        # --- Yönetim & Tanımlar ---
        if imgui.begin_menu("Yönetim & Tanımlar"):
            if imgui.menu_item("Tanımlar (Definitions - Ctrl+R)", selected=self._get_panel_state("definitions"))[0]:
                self._fire("definitions")
            if imgui.menu_item("Proje Bilgileri (Info)", selected=self._get_panel_state("project_info"))[0]:
                self._fire("project_info")
            if imgui.menu_item("Yapılandırma (Config)", selected=self._get_panel_state("project_config"))[0]:
                self._fire("project_config")
            if imgui.menu_item("Analiz (Analysis)", selected=self._get_panel_state("analysis"))[0]:
                self._fire("analysis")
            if imgui.menu_item("Rapor (Report)", selected=self._get_panel_state("report"))[0]:
                self._fire("report")
            imgui.end_menu()
        imgui.same_line()

        # --- Rüzgar & Özel Analizler ---
        self._styled_button("Zones", (0.15, 0.45, 0.60, 1.00), lambda: self._fire("wind"))
        imgui.same_line()

        # --- Tek ve Kalıcı Birim Seçici ---
        unit_label = f"Birim: {self.current_unit.name} ({self.current_unit.force_unit}, {self.current_unit.length_unit})" if self.current_unit else "Birim: N-mm"
        
        if imgui.begin_menu(unit_label):
            for unit in UnitSystem:
                is_selected = (self.current_unit == unit)
                if imgui.menu_item(f"{unit.name} ({unit.force_unit}, {unit.length_unit})", selected=is_selected)[0]:
                    if "on_unit_change" in self.callbacks:
                        self.callbacks["on_unit_change"](unit)
            imgui.end_menu()
        imgui.same_line()

        # Model Durum Bilgisi
        imgui.text_colored(model_text, 0.60, 0.65, 0.72, 1.00)

    def _get_panel_state(self, key: str) -> bool:
        fn = self.panel_states.get(key)
        if callable(fn):
            return bool(fn())
        return False

    def _styled_button(self, label: str, base_color, on_click):
        hovered = tuple(min(c + 0.08, 1.0) for c in base_color[:3]) + (1.0,)
        active = tuple(min(c + 0.15, 1.0) for c in base_color[:3]) + (1.0,)

        imgui.push_style_color(imgui.COLOR_BUTTON, *base_color)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hovered)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *active)
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 4.0)

        clicked = imgui.button(label)

        imgui.pop_style_var(1)
        imgui.pop_style_color(3)

        if clicked and callable(on_click):
            on_click()
    
    def _fire(self, key: str):
        fn = self.callbacks.get(key)
        if callable(fn):
            fn()