# ui/panels/debug_panel.py
from __future__ import annotations

import glfw
from imgui_bundle import imgui

from ui.base.panel_base import PanelBase, Category


class DebugPanel(PanelBase):
    panel_name = "debug_panel"
    title = "Debug & Input Inspector"
    category = Category.DEBUG
    quick = False
    context = ("engine",)
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True

    width = 560
    height = 680
    pos_first_use = (960.0, 60.0)

    engine = None

    # ------------------------------------------------------------------
    def draw_header(self) -> None:
        app = self.app
        initialized = getattr(app, "initialized", False) if app else False
        imgui.text(f"initialized: {initialized}")
        eng = self.engine
        if eng is None:
            imgui.text_disabled("Engine hazır değil")
            return
        imgui.same_line()
        imgui.text_disabled(f"| viewports: {len(getattr(eng.viewport_manager, 'viewports', {}) or {})}")

    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        eng = self.engine
        if eng is None:
            return
        self._draw_input(eng.input)
        self._draw_context_sensitivity(eng)  # ★ Yeni: Bağlam duyarlı girdi izleme
        self._draw_handlers(eng.input)
        self._draw_tools(eng)
        self._draw_bindings(eng.input)

    # ------------------------------------------------------------------
    def _draw_input(self, inp) -> None:
        self.section_label("Input State & Modifiers")
        state = inp.state
        imgui.text(f"mouse pos: ({state.mouse_pos.x:.0f}, {state.mouse_pos.y:.0f})")
        imgui.text(f"mouse delta: ({state.mouse_delta.x:.1f}, {state.mouse_delta.y:.1f})")
        imgui.text(f"buttons: {dict(state.buttons)}")
        imgui.text(f"modifiers raw: {state.modifiers}")
        
        # Net modifikatör bayrakları
        ctrl = inp.is_ctrl()
        shift = inp.is_shift()
        alt = inp.is_alt()
        imgui.text(f"Active Modifiers -> CTRL: {ctrl} | SHIFT: {shift} | ALT: {alt}")

    # ------------------------------------------------------------------
    def _draw_context_sensitivity(self, eng) -> None:
        self.section_label("Context-Sensitive & Picking (Double/Right Click)")
        
        # 1. UIHost / Viewport Bağlamı
        app = self.app
        ui_host = getattr(app, "ui", None) if app else None
        ui_info = ui_host.get_interaction_debug_info() if ui_host and hasattr(ui_host, "get_interaction_debug_info") else {}
        
        imgui.text(f"Hovered Viewport: {ui_info.get('hovered_viewport', 'None / UI Arka Planı')}")
        imgui.text(f"Active Viewport Panels: {ui_info.get('active_viewport_count', 0)}")

        # 2. Engine / 3D Nesne Hover Durumu
        hover_id = getattr(eng, "hover_id", 0)
        element = None
        if hover_id > 0 and hasattr(eng, "sel_mgr"):
            element = eng.sel_mgr.find_element_by_id(hover_id)
            
        imgui.text(f"3D Hover ID: {hover_id}")
        if element:
            elem_type = type(element).__name__
            imgui.text(f"-> 3D Nesne Üzerinde: {elem_type} (ID: {hover_id}) [Çift tık: Properties | Sağ tık: Nesne Menüsü]")
        else:
            imgui.text_disabled("-> Boşlukta / Viewport Alanında [Çift tık: Zoom Extents | Sağ tık: Viewport Menüsü]")

        # 3. Context Handler Durumu
        ctx_handler = getattr(eng.input, "_context_pick_handler", None)
        imgui.text(f"Context Pick Handler: {'Aktif' if ctx_handler is not None else 'Yok (Standart Akış)'}")

    # ------------------------------------------------------------------
    def _draw_handlers(self, inp) -> None:
        handlers = getattr(inp, "_handlers", [])
        imgui.separator()
        self.section_label(f"Handlers ({len(handlers)})")
        for h in handlers:
            name = type(h).__name__
            active = getattr(h, "is_active", False)
            imgui.text(f"{name}: active={active}")

    # ------------------------------------------------------------------
    def _draw_tools(self, eng) -> None:
        imgui.separator()
        self.section_label("Tools")
        dm = getattr(eng, "draw_mgr", None)
        if dm is not None:
            imgui.text(
                f"draw_mgr: active={dm.is_active} mode={getattr(dm, 'mode', '?')} "
                f"points={len(getattr(dm, 'points', []))}"
            )
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is not None:
            imgui.text(
                f"plane_mgr: active={pdm.is_active} stage={getattr(pdm, 'stage', '?')} "
                f"mode={getattr(pdm, 'mode', '?')}"
            )

    # ------------------------------------------------------------------
    def _draw_bindings(self, inp) -> None:
        bindings = getattr(inp, "_bindings", {})
        imgui.separator()
        self.section_label(f"Bindings ({len(bindings)})")
        for (key, mods), action in bindings.items():
            key_name = glfw.get_key_name(key, 0) or str(key)
            mod_str = ""
            if mods & glfw.MOD_CONTROL:
                mod_str += "CTRL+"
            if mods & glfw.MOD_SHIFT:
                mod_str += "SHIFT+"
            if mods & glfw.MOD_ALT:
                mod_str += "ALT+"
            fn = getattr(action, "__name__", type(action).__name__)
            imgui.text(f"{mod_str}{key_name} → {fn}")