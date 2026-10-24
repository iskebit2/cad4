# app/cad_app.py
import os
from typing import Dict, List, Optional, Set

import glfw
import imgui
import numpy as np
from OpenGL.GL import *

from app.cad_window import CadWindow
from app.panel_registry import PANEL_SPECS, CATEGORY_ORDER
from app.toolbar import Toolbar

from core.gl_engine import Engine
from core.plane_draw_manager import PlaneDrawManager
from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)

from app.ui_capture import (
    mouse_over_ui,
    keyboard_captured_by_ui,
    sync_modifiers_from_glfw,
    mods_to_dict,
)

from data.enums import UnitSystem, GridPlane
from domain.definition import Section
from domain.element import Frame, Node, Area, Link
from domain.project import Project
from tools import frame_to_link
from tools.s2kloader import S2KLoader
from ui.file_dialog import ImGuiFileDialog
from ui.imgui_backend import UiBackend
from ui.main_menu import MainMenuPopup
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, window: CadWindow):
        # --- 1. Temel durum ---
        self.window = window
        self.engine: Optional[Engine] = None
        self.inspector: Optional[InspectorWindow] = None
        self.initialized = False

        self.current_project = Project()
        self.current_file_path: Optional[str] = None
        self._model_text = "MODEL: YENİ SAHNE"

        self.section_catalog: Dict[str, Section] = {}
        self.hover_visual_enabled = True
        self.show_loads = False

        # --- 2. Mouse durumu ---
        self._pending: List[tuple] = []
        self._mouse_pressed: Set[str] = set()
        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False
        self._show_only_ids: Optional[Set[int]] = None

        # --- 3. Merkezi kayıtlar ---
        self._init_registry()          # panels, shortcuts
        self._init_shortcuts()         # key_shortcuts
        self._init_actions()           # _actions

        # --- 4. UI backend + callbacks ---
        self.ui_backend = UiBackend(window.window)
        self.ui_backend.setup()
        window._wire_callbacks()
        window.on_key_down      = self.on_key_down
        window.on_key_up        = self.on_key_up
        window.on_mouse_button  = self.on_mouse_button
        window.on_mouse_move    = self.on_mouse_move
        window.on_scroll        = self.on_scroll
        window.on_resize        = self._on_resize
        window.on_char          = self.on_char
        window.on_focus         = self.on_window_focus

        # --- 5. Toolbar ---
        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        # --- 6. Yardımcı bileşenler ---
        self.main_menu = MainMenuPopup()
        self.file_dialog = ImGuiFileDialog()

        
        
        self._load_section_catalog()


    # ==================================================================
    # REGISTRY
    # ==================================================================
    def _init_registry(self):
        self.panels: Dict[str, dict] = {}
        self._panels_by_category: Dict[str, List[str]] = {}
        self._shortcut_map: Dict[str, str] = {}

        for spec in PANEL_SPECS:
            if spec.get("kind", "panel") != "panel":
                continue
            name = spec["name"]
            try:
                inst = spec["cls"]()
                inst.app = self
            except Exception:
                logger.exception("[Registry] Panel başlatılamadı: %s", name)
                continue

            self.panels[name] = {
                "instance":   inst,
                "title":      spec["title"],
                "category":   spec["category"],
                "quick":      spec.get("quick", False),
                "shortcut":   spec.get("shortcut"),
                "menu_label": spec.get("menu_label"),
                "icon":       spec.get("icon"),
                "context":    spec.get("context", []),
            }
            self._panels_by_category.setdefault(spec["category"], []).append(name)
            if spec.get("shortcut"):
                self._shortcut_map[spec["shortcut"]] = name

        # Kısayol attribute erişimi için: self.s2k_panel vs.
        for name, entry in self.panels.items():
            setattr(self, name, entry["instance"])

        # S2K özel callback'leri (BasePanel ile değil, kendi sözleşmesiyle)
        s2k = self.panels.get("s2k_panel")
        if s2k:
            inst = s2k["instance"]
            inst.on_import_complete = self._on_s2k_import_complete
            inst.get_project        = lambda: self.current_project
            inst.get_selected_elements = lambda: self._selected()


        # --- Inspector: app + catalog (scene set_project'te) ---
        ins = self.panels.get("inspector")
        if ins:
            inst = ins["instance"]
            inst.app = self
            inst.set_catalog(ProjectCatalog(self.current_project))

    def _context_resolvers(self) -> Dict[str, callable]:
        scn = self.engine.scene if self.engine else None
        selection = list(scn.get_selected()) if scn else []
        project = self.current_project

        return {
            "scene":            lambda: scn,
            "catalog":          lambda: project,
            "project":          lambda: project,
            "selection":        lambda: selection,
            "selection_frames": lambda: [e for e in selection if isinstance(e, Frame)],
            "selection_areas":  lambda: [e for e in selection if isinstance(e, Area)],
            "selection_links":  lambda: [e for e in selection if isinstance(e, Link)],
            "patterns":         lambda: list(getattr(project, "load_patterns", {}).keys()),
            "sections":         lambda: list(getattr(project, "sections", {}).keys()),
            "materials":        lambda: list(getattr(project, "materials", {}).keys()),
        }

    def _resolve_panel_context(self, keys: List[str]) -> dict:
        if not keys:
            return {}
        resolvers = self._context_resolvers()
        ctx = {}
        for key in keys:
            fn = resolvers.get(key)
            if fn is None:
                logger.warning("[Context] Bilinmeyen anahtar: %s", key)
                continue
            try:
                ctx[key] = fn()
            except Exception:
                logger.exception("[Context] %s çözümlenemedi", key)
        return ctx

    def _prepare_panel_before_open(self, name, panel):
        keys = self.panels[name].get("context", [])
        ctx = self._resolve_panel_context(keys)
        logger.debug(f"[prep] {name} context_keys={keys} ctx_keys={list(ctx.keys())} "
            f"frames={len(ctx.get('selection_frames', []))}")
        panel.set_context(ctx)

    def toggle_panel(self, name: str):
        entry = self.panels.get(name)
        if not entry:
            return
        p = entry["instance"]
        if getattr(p, "visible", False):
            p.close()
            return
        self._prepare_panel_before_open(name, p)
        p.open()

    def _selected(self):
        if self.engine and self.engine.scene:
            return self.engine.scene.get_selected()
        return []

    # ==================================================================
    # FRAME DÖNGÜSÜ
    # ==================================================================
    def _ensure_engine(self):
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return
        try:
            self.engine = Engine(w, h)
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.engine.plane_draw_mgr = PlaneDrawManager(self.engine)
            if self.engine.renderer:
                self.engine.renderer.set_plane_draw_mgr(self.engine.plane_draw_mgr)
            self.initialized = True


            from pathlib import Path

            PROJECT_ROOT = Path(__file__).resolve().parent.parent
            TEST_MODEL = PROJECT_ROOT / "betonarme.cd4"
            self._load_project(str(TEST_MODEL))

            if self.current_project:
                self.set_project(self.current_project)
        except Exception:
            logger.exception("[Init] Engine başlatma hatası")
            self.initialized = True

    def frame(self, dt: float):
        self._ensure_engine()
        if not self.initialized:
            return

        self.ui_backend.begin_frame()

        current_unit = self.current_project.unit_system if self.current_project else None

        # 1) Toolbar
        self.toolbar.draw(model_text=self._model_text, current_unit=current_unit)
        self.file_dialog.draw()

        # 2) Bekleyen event'ler
        self.process_pending()

        # 3) Sahne dirty ise renderer'ı güncelle
        self._update_scene_if_dirty()

        # 4) Render
        self._render_scene(dt)

        # 5) Paneller
        self._draw_panels()

        self.ui_backend.end_frame()

        # 6) Pick sonucu
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def _update_scene_if_dirty(self):
        scn = self.engine.scene if self.engine else None
        if scn and hasattr(scn, "is_dirty") and scn.is_dirty():
            if self.engine.renderer:
                self.engine.renderer.update_geo(scn)
            scn.clear_dirty()

    def _draw_panels(self):
        self.main_menu.draw()
        # BasePanel sözleşmesi: visible + draw
        for entry in self.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False) and hasattr(panel, "draw"):
                panel.draw()
        

    def _render_scene(self, dt: float):
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)
        try:
            glEnable(GL_DEPTH_TEST)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            self.engine.renderer.set_dt(dt)
            self.engine.renderer.render(self.engine.cam)

            self._draw_snap_indicator(w, h)

            if self.engine.draw_mgr.is_active:
                mvp = (self.engine.cam.get_projection_matrix()
                       @ self.engine.cam.get_view_matrix())
                self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

            pdm = getattr(self.engine, "plane_draw_mgr", None)
            if pdm and pdm.is_active:
                self._draw_pdm_hud(pdm)
        finally:
            glViewport(0, 0, w, h)
            glUseProgram(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # ==================================================================
    # KISAYOLLAR / AKTIONS
    # ==================================================================
    def _init_shortcuts(self):
        self._key_shortcuts: Dict[int, tuple] = {}
        for shortcut, panel_name in self._shortcut_map.items():
            parts = shortcut.split("+")
            key_name = parts[-1]
            mods = {p.upper() for p in parts[:-1]}
            glfw_key = getattr(glfw, f"KEY_{key_name}", None)
            if glfw_key is None:
                logger.warning("[Shortcut] Geçersiz: %s", shortcut)
                continue
            self._key_shortcuts[glfw_key] = (
                panel_name, "CTRL" in mods, "SHIFT" in mods,
            )

    def _build_toolbar_commands(self) -> dict:
        cmds = {
            # Dosya
            "new_project": self._new_project,
            "open":        self._on_toolbar_open,
            "save":        self._quick_save,
            "save_as":     self._save_as_project,
            "close_app":   lambda: glfw.set_window_should_close(self.window.window, True),
            "s2k_import":  self._open_s2k_panel_import,
            "s2k_export":  self._open_s2k_panel_export,
            # Çizim
            "draw_poly":   self._toggle_draw_mode,
            "draw_plane":  self._toggle_plane_draw,
            # Diğer
            "render_mode":      lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis": self._toggle_loads_visibility,
            "local_axes":       self._toggle_local_axes,
            "show_only":        self.toggle_show_only,
            "convert_to_link":  lambda: self.convert_selected_frames_to_links("DefaultLink"),
            "on_unit_change":   self.set_unit_system,
        }
        for name in self.panels:
            cmds[name] = (lambda n=name: self.toggle_panel(n))
        return cmds

    def _build_panel_states(self) -> dict:
        states = {
            "draw_poly":  lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_plane": lambda: bool(self.engine and getattr(self.engine, "plane_draw_mgr", None) and self.engine.plane_draw_mgr.is_active),
            "local_axes": lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads": lambda: bool(self.engine and self.engine.renderer and self.engine.renderer.show.get("loads", True)),
            "show_only":  lambda: self._show_only_ids is not None,
        }
        for name in self.panels:
            states[name] = (lambda n=name: getattr(self.panels[n]["instance"], "visible", False))
        return states

    def _init_actions(self):
        self._actions = {
            "save_project": self._save_project,
            "update_geo":   self._on_update_geo,
        }

    def _dispatch_key(self, key, eng):
        if key == glfw.KEY_ESCAPE:
            return self._on_escape()

        # Registry kısayolları
        entry = self._key_shortcuts.get(key)
        if entry:
            panel_name, needs_ctrl, needs_shift = entry
            if (eng.input.is_ctrl_pressed() == needs_ctrl
                    and eng.input.is_shift_pressed() == needs_shift):
                self.toggle_panel(panel_name)
                return

        if key == glfw.KEY_F3:
            return eng.renderer.toggle_render_mode()
        if key == glfw.KEY_D and not eng.input.is_ctrl_pressed():
            return self._toggle_draw_mode()
        if key == glfw.KEY_W and eng.input.is_shift_pressed():
            return self._toggle_plane_draw()
        if key == glfw.KEY_C and eng.draw_mgr.is_active:
            return eng.draw_mgr.close()
        if key == glfw.KEY_L and not eng.input.is_ctrl_pressed():
            return self._toggle_loads_visibility()
        if key == glfw.KEY_DELETE:
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info("[Key] Silindi=%s Reddedildi=%s", deleted, rejected)
            return

        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_J: return self.toggle_show_only()
            if key == glfw.KEY_Z: return eng.sel_mgr.undo()
            if key == glfw.KEY_Y: return eng.sel_mgr.redo()
            if key == glfw.KEY_S:
                return (self._save_as_project()
                        if eng.input.is_shift_pressed() else self._quick_save())
            if key == glfw.KEY_O: return self._on_toolbar_open()
            if key == glfw.KEY_E: return self._open_s2k_panel_export()


    # ==================================================================
    # DOSYA / SAHNE / PANEL AKSİYONLARI
    # ==================================================================
    def _new_project(self):
        self.set_project(Project())
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"
        logger.info("[File] Yeni proje")

    def _load_project(self, path: str):
        logger.debug("....", path)
        try:
            self.set_project(Project.load(path))
            if self.engine:
                self.engine.fit_view()
                self.engine.sel_mgr.clear()
            self.current_file_path = path
            self._model_text = f"MODEL: {os.path.basename(path)}"
        except Exception:
            logger.exception("[File] Proje yükleme hatası")

    def _save_project(self, path: str):
        try:
            self.current_project.save(path)
            self.current_file_path = path
            self._model_text = f"MODEL: {os.path.basename(path)}"
        except Exception:
            logger.exception("[File] Proje kaydetme hatası")

    def _quick_save(self):
        if self.current_file_path:
            self._save_project(self.current_file_path)
        else:
            self._on_toolbar_save()

    def _save_as_project(self):
        self._on_toolbar_save()

    def _on_toolbar_open(self):
        self.file_dialog.open(
            mode="open", filters=[".cd4"], title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(), on_select=self._load_project,
        )

    def _on_toolbar_save(self):
        self.file_dialog.open(
            mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)",
            initial_dir=os.getcwd(), default_name="model_projesi.cd4",
            on_select=self._save_project,
        )

    # ------------------------------------------------------------------
    # S2K
    # ------------------------------------------------------------------
    def _open_s2k_panel_import(self):
        entry = self.panels.get("s2k_panel")
        if not entry:
            return
        p = entry["instance"]
        p.open(mode=getattr(p, "MODE_IMPORT", "import"))

    def _open_s2k_panel_export(self):
        entry = self.panels.get("s2k_panel")
        if not entry:
            return
        p = entry["instance"]
        p.open(mode=getattr(p, "MODE_EXPORT", "export"))

    def _on_s2k_import_complete(self, project: Project):
        self.set_project(project)
        scn = project.scene
        self._model_text = f"MODEL: S2K import ({len(getattr(scn, 'frames', {}))} çubuk)"
        logger.info("[S2K] Import tamam")

    def _import_s2k_direct(self):
        """F10 test yolu."""
        candidates = [
            os.path.join(os.getcwd(), "tests", "eski_.s2k"),
            r"D:\Program\cad4\tests\eski_.s2k",
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            logger.error("[Direct] Dosya yok: %s", candidates)
            return
        try:
            project = S2KLoader(path).load(Project())
            self.set_project(project)
            self._model_text = f"MODEL: eski_.s2k ({len(project.scene.frames)} çubuk)"
        except Exception:
            logger.exception("[Direct] Hata")

    # ------------------------------------------------------------------
    # Sahne
    # ------------------------------------------------------------------
    def set_project(self, project: Project):
        self.current_project = project
        if not self.engine:
            logger.warning("[set_project] engine yok — sadece proje atandı")
            return
        if project.scene is None:
            return

        scn = project.scene
        self.engine.set_scene(scn)

        if self.inspector:
            self.inspector.set_catalog(ProjectCatalog(project))
            self.inspector.set_scene(scn)

        if self.engine.renderer:
            try:
                self.engine.renderer.update_geo(scn)
            except Exception:
                logger.exception("[set_project] update_geo hatası")

        # Grid senkronizasyonu
        g = getattr(project, "grid", None)
        if g and self.engine.grid:
            self.engine.grid.set_coords(g.x_coords, g.y_coords, g.z_coords)
            self.engine.grid.set_origin(g.origin_x, g.origin_y, g.origin_z)
            for plane_name, vis in g.planes_visibility.items():
                try:
                    self.engine.grid.set_plane(GridPlane[plane_name], visible=vis)
                except KeyError:
                    pass
        else:
            self.engine.fit_view()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

    def _on_update_geo(self):
        if self.engine and self.engine.renderer and self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)

    def set_unit_system(self, unit_system: UnitSystem):
        self.current_project.unit_system = unit_system
        if self.engine and self.engine.grid:
            self.engine.grid.rebuild_all()
        logger.info("[Units] %s", unit_system.name)

    def _on_section_changed(self):
        if self.engine and self.engine.scene:
            scn = self.engine.scene
            scn.mark_dirty()
            if self.engine.renderer:
                self.engine.renderer.update_geo(scn)
                scn.clear_dirty()

    # ------------------------------------------------------------------
    # Seçim / hover
    # ------------------------------------------------------------------
    def _on_selection_changed(self, selected_elements):
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if self.inspector:
            self.inspector.set_selection(selected_elements)

        # Açık panellere canlı seçim hook'u
        for name, entry in self.panels.items():
            p = entry["instance"]
            if not getattr(p, "visible", False):
                continue
            hook = getattr(p, "on_scene_selection_changed", None)
            if callable(hook):
                try:
                    hook(selected_elements)
                except Exception:
                    logger.exception("[Selection] %s hook hatası", name)
                    
    def _on_hover_changed(self, element):
        pass

    # ------------------------------------------------------------------
    # Görünüm modları
    # ------------------------------------------------------------------
    def _toggle_draw_mode(self):
        if not self.engine or not self.engine.draw_mgr:
            return
        mgr = self.engine.draw_mgr
        mgr.close() if mgr.is_active else mgr.start()

    def _toggle_plane_draw(self):
        pdm = getattr(self.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            return
        for entry in self.panels.values():
            p = entry["instance"]
            if getattr(p, "visible", False):
                try:
                    p.close()
                except Exception:
                    pass
        pdm.start()

    def _toggle_local_axes(self):
        if self.engine and self.engine.scene:
            self.engine.scene.show_local_axes = not self.engine.scene.show_local_axes

    def _toggle_loads_visibility(self):
        if self.engine and self.engine.renderer:
            cur = self.engine.renderer.show.get("loads", True)
            self.engine.renderer.show["loads"] = not cur
            self.show_loads = not cur

    def toggle_show_only(self):
        if not self.engine or not self.engine.scene:
            return
        scn = self.engine.scene
        if self._show_only_ids is None:
            selected = scn.get_selected()
            if not selected:
                return
            self._show_only_ids = {e.unique_id for e in selected}
        else:
            self._show_only_ids = None

        scn._render_filter = self._show_only_ids
        if self._show_only_ids is not None:
            self.engine.renderer.update_geo(scn)
        else:
            self.engine.set_scene(scn)

    def convert_selected_frames_to_links(
        self, link_prop_name: str = "DefaultLink", delete_original: bool = True,
    ):
        if not self.engine or not self.engine.scene:
            return
        scn = self.engine.scene
        frames = [e for e in scn.get_selected() if isinstance(e, Frame)]
        if not frames:
            return

        report = frame_to_link.convert_frames_to_links(
            scene=scn, project=self.current_project,
            frames=frames, link_prop_name=link_prop_name,
            delete_original=delete_original,
        )

        if self._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self._show_only_ids -= removed
            self._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self._show_only_ids

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()


    # ==================================================================
    # EVENT HANDLERS
    # ==================================================================

    def on_char(self, codepoint):
        try:
            import imgui
            io = imgui.get_io()
            io.add_input_character(codepoint)
        except Exception:
            pass
        return True

    def on_key_down(self, key, scancode, mods):
        try:
            io = imgui.get_io()
            io.keys_down[key] = True       # bu çalışır (index erişimi)
        except Exception:
            pass

        # Modifier'ları DOĞRUDAN mods'tan oku (glfw garanti eder)
        try:
            io = imgui.get_io()
            io.key_ctrl  = bool(mods & glfw.MOD_CONTROL)
            io.key_shift = bool(mods & glfw.MOD_SHIFT)
            io.key_alt   = bool(mods & glfw.MOD_ALT)
            io.key_super = bool(mods & glfw.MOD_SUPER)
        except Exception:
            pass

        self._pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        
        try:
            io = imgui.get_io()
            io.keys_down[key] = False
        except Exception:
            pass

        # Sadece o modifier bırakıldıysa False yap
        try:
            io = imgui.get_io()
            if key in (glfw.KEY_LEFT_CONTROL, glfw.KEY_RIGHT_CONTROL):
                io.key_ctrl = False
            elif key in (glfw.KEY_LEFT_SHIFT, glfw.KEY_RIGHT_SHIFT):
                io.key_shift = False
            elif key in (glfw.KEY_LEFT_ALT, glfw.KEY_RIGHT_ALT):
                io.key_alt = False
            elif key in (glfw.KEY_LEFT_SUPER, glfw.KEY_RIGHT_SUPER):
                io.key_super = False
        except Exception:
            pass

        self._pending.append(("key_up", (key, scancode)))
        return True

    def on_mouse_button(self, button, action, mods):
        self._pending.append(("button", (button, action, mods)))
        return True

    def on_mouse_move(self, x, y):
        self._pending.append(("move", (x, y)))
        return True

    def on_scroll(self, xoffset, yoffset):
        try:
            import imgui
            io = imgui.get_io()
            io.mouse_wheel += yoffset
        except Exception:
            pass
        self._pending.append(("scroll", (xoffset, yoffset)))
        return True

    def on_window_focus(self, focused: bool):
        if not focused:
            eng = self.engine
            if eng and eng.input:
                eng.input.clear_modifiers()

    def process_pending(self):
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        for kind, args in events:
            try:
                if kind == "move":
                    self._handle_move(*args)
                elif kind == "button":
                    self._handle_button(*args)
                elif kind == "scroll":
                    self._handle_scroll(*args)
                elif kind == "key_down":
                    self._handle_key_down(*args)
                elif kind == "key_up":
                    self._handle_key_up(*args)
            except Exception:
                logger.exception("Event işleme hatası: %s %s", kind, args)

    def _handle_button(self, button, action, mods):
        eng = self.engine
        if eng is None:
            return
        self._sync_from_glfw_mods(mods)

        x, y = self.window.get_mouse_pos()

        # UI yakaladıysa geç
        if mouse_over_ui():
            return

        # Plane Draw aktifse tıklamayı öncelikli olarak PDM yönlendirsin
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is not None and pdm.is_active:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                if pdm.on_mouse_click(x, y):
                    return

        if button == glfw.MOUSE_BUTTON_LEFT:
            kivy_btn, name = MOUSE_BUTTON_LEFT, "left"
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            kivy_btn, name = MOUSE_BUTTON_RIGHT, "right"
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            kivy_btn, name = MOUSE_BUTTON_MIDDLE, "middle"
        else:
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
            eng.input.set_button_state(kivy_btn, action == glfw.PRESS)

        if action == glfw.PRESS:
            self._mouse_pressed.add(name)
            self._on_down(name, x, y)
        elif action == glfw.RELEASE:
            self._mouse_pressed.discard(name)
            self._on_up(name, x, y)

    def _on_down(self, name, x, y):
        eng = self.engine
        if eng.active_smart_plane_mode:
            eng.smart_analyzer.handle_mouse_click((x, y))
            return

        if name == "middle":
            self._middle_down(x, y)
        elif name == "right":
            self._right_down()
        elif name == "left":
            self._left_down(x, y)

    def _on_up(self, name, x, y):
        eng = self.engine
        if name == "left":
            self._left_up(x, y)
        elif name == "right":
            eng.pending_pick_check = False
        elif name == "middle":
            eng.pending_pick_check = False
            eng.clear_hover()

    def _left_down(self, x, y):
        eng = self.engine
        
        
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _left_up(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active or eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                ctrl = eng.input.is_ctrl_pressed()
                eng.handle_pick_from_hover(ctrl)

    def _right_down(self):
        eng = self.engine
        element = eng.renderer.get_element_from_id(eng.hover_id) if eng.hover_id > 0 else None
        if element:
            self.toggle_panel("inspector")

    def _middle_down(self, x: float, y: float):
        eng = self.engine
        eng.pending_pick_check = False
        eng.clear_hover()

        import time
        if eng.input.begin_middle_click(x, y, time.time()):
            eng.fit_view()

    def _middle_move(self, dx, dy, x, y):
        eng = self.engine
        eng.input.update_middle_drag(x, y)

        if eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)

        eng.pending_pick_check = False
        eng.clear_hover()

    def _handle_move(self, x, y):
        eng = self.engine
        if eng is None or mouse_over_ui():
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
        dx = eng.input.mouse_delta.x if eng.input else 0
        dy = eng.input.mouse_delta.y if eng.input else 0

        self._sync_modifiers()

        # --- PDM: her zaman hover pick + PDM hover, ama diğer işlemler atlanır ---
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            # PDM kendi hover'ını hesaplasın
            pdm.on_mouse_move(x, y)
            # 3D sahne hover'ı da çalışsın (highlight, snap)
            eng.update_world_pos(x, y)
            eng.start_hover_pick(int(x), int(y))
            # Camera/marquee/draw_mgr atlanır
            return

        # --- Normal akış (PDM yok) ---
        if "middle" in self._mouse_pressed:
            self._middle_move(dx, dy, x, y)
            return
        if "left" in self._mouse_pressed and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return
        if "right" in self._mouse_pressed:
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return

        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

        if eng.active_smart_plane_mode:
            view = np.array(eng.cam.get_view_matrix(), dtype=float)
            proj = np.array(eng.cam.get_projection_matrix(), dtype=float)
            eng.smart_analyzer.handle_mouse_move((x, y), view, proj, (self.window.fb_width, self.window.fb_height))

    def _handle_scroll(self, xoffset, yoffset):
        eng = self.engine
        if eng is None or mouse_over_ui():
            return
        if yoffset > 0:
            eng.cam.zoom(1.0)
        elif yoffset < 0:
            eng.cam.zoom(-1.0)

    def _handle_key_down(self, key, scancode, mods):
        eng = self.engine
        if not eng:
            return

        self._sync_from_glfw_mods(mods)

        logger.info(f"[KeyDown] key={key} ctrl={eng.input.is_ctrl_pressed() if eng.input else '?'} "
                f"ui_captured={keyboard_captured_by_ui()}")
        
        if keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active and pdm.on_key_press(key):
            return

        if eng.input:
            eng.input.handle_key_down(key)

        if eng.active_smart_plane_mode and eng.smart_analyzer.handle_key_press(key):
            return

        self._dispatch_key(key, eng)

    def _handle_key_up(self, key, scancode):
        eng = self.engine
        if eng is None:
            return
        if eng.input:
            eng.input.handle_key_up(key)
        self._sync_modifiers()

    def _on_escape(self):
        eng = self.engine
        if eng is None:
            return
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm._step_back()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return
        eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()

    # ==================================================================
    # YARDIMCI METOTLAR VE İŞLEM SERVİSLERİ
    # ==================================================================
    def _draw_snap_indicator(self, w, h):
        if not self.engine:
            return
        snap = self.engine.snap
        if snap is None or not getattr(self.engine, "hover_visual_enabled", True):
            return
        mx, my = self.engine.input.mouse_pos.x, self.engine.input.mouse_pos.y
        if not self.engine.draw_mgr:
            return
        if self.engine.draw_mgr.is_active or self.engine.hover_id > 0:
            snap.draw_snap(mx, my, w, h, active=True)

    def _draw_pdm_hud(self, pdm):
        import imgui
        stage_text = {
            pdm.STAGE_P0: "p0: İlk noktayı seç",
            pdm.STAGE_P1: "p1: U vektörünü belirle",
            pdm.STAGE_P2: "p2: V vektörünü belirle",
            pdm.STAGE_DEPTH_PLUS: f"depth_plus: mouse yukarı/aşağı ({pdm.depth_plus:.0f}mm) — tıkla → sonraki",
            pdm.STAGE_DEPTH_MINUS: f"depth_minus: mouse aşağı/yukarı ({pdm.depth_minus:.0f}mm) — tıkla → onayla",
        }.get(pdm.stage, "")

        io = imgui.get_io()
        w, h = io.display_size
        imgui.set_next_window_position(w / 2 - 200, 20)
        imgui.set_next_window_size(400, 40)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 8))
        expanded, _ = imgui.begin("##pdm_hud", False,
                                imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE |
                                imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_INPUTS)
        if expanded:
            imgui.text_colored(stage_text, 1.0, 0.9, 0.4, 1.0)
        imgui.end()
        imgui.pop_style_var()

    def _on_resize(self, w, h):
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _sync_modifiers(self):
        eng = self.engine
        if eng is None or eng.input is None:
            return
        eng.input.update_modifiers(sync_modifiers_from_glfw(self.window.window))


    def _sync_from_glfw_mods(self, mods: int):
        eng = self.engine
        if eng and eng.input:
            eng.input.update_modifiers(mods_to_dict(mods))

    def _load_section_catalog(self):
        from pathlib import Path
        from data.section_catalog import load_catalog_from_dir

        data_dir = Path(__file__).parent.parent / "data"
        try:
            self.section_catalog = load_catalog_from_dir(data_dir)
            logger.info(f"[CadApp] Kesit kataloğu: {len(self.section_catalog)} kesit")
        except Exception:
            logger.exception("[CadApp] Katalog yüklenemedi")
            self.section_catalog = {}
            
    # ==================================================================
    # KAPANIŞ
    # ==================================================================
    def shutdown(self):
        self.ui_backend.shutdown()