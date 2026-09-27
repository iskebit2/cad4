# ui_manager/uimanager.py

import imgui
from imgui.integrations.glfw Renderer
from OpenGL.GL import *
import io
import sys
from contextlib import redirect_stdout
from typing import List, Tuple, Optional, Any, Dict
import numpy as np
import glm

import traceback
from datetime import datetime
from domain.element import Node, Frame, Area, Link
from ui.command_line import CommandLine
from ui.properties_window import PropertiesWindow
import logging
logger = logging.getLogger(__name__)


class DebugConsole:
    """
    stdout'u yakalayıp ImGui penceresinde gösteren sınıf
    """
    def __init__(self, max_lines: int = 1000):
        self.logs: List[str] = []
        self.max_lines = max_lines
        self.buffer = io.StringIO()
        self._original_stdout = sys.stdout
        self.auto_scroll = True
        self.filter_text = ""
        
    def write(self, text: str):
        """stdout.write yerine geçer"""
        if text.strip():
            self.logs.append(text.rstrip())
            if len(self.logs) > self.max_lines:
                self.logs = self.logs[-self.max_lines:]
        
        self._original_stdout.write(text)
    
    def flush(self):
        """stdout.flush için"""
        self._original_stdout.flush()
    
    def clear(self):
        """Logları temizle"""
        self.logs.clear()
    
    def start_capture(self):
        """stdout'u yakalamaya başla"""
        sys.stdout = self
    
    def stop_capture(self):
        """stdout'u eski haline döndür"""
        sys.stdout = self._original_stdout
    
    def get_filtered_logs(self) -> List[str]:
        """Filtre uygulanmış logları döndür"""
        if not self.filter_text:
            return self.logs
        
        filtered = []
        for log in self.logs:
            if self.filter_text.lower() in log.lower():
                filtered.append(log)
        return filtered


class UIManager:
    """Tüm UI işlerinden sorumlu sınıf"""
    
    # Constants
    _STATUS_BAR_HEIGHT = 25
    _ERROR_DISPLAY_TIME = 5.0
    
    def __init__(self, window, engine, imgui_impl, selection_manager, def_mgr=None):
        self.window = window
        self.engine = engine
        self.imgui_impl = imgui_impl
        self.selection = selection_manager

        self.width, self.height = engine.w, engine.h
        
        # UI bileşenleri
        self.show_demo_window = False
        self.show_metrics = False
        self.show_debug_console = False
        self.show_properties = False
        
        # Menü durumları
        self.show_grid = True
        self.show_gizmo = True
        self.auto_rotate_lights = False
        # Görünürlük kontrolleri
        self.show_node = True
        self.show_frame = True
        self.show_area = True
        self.show_link = True
        self.frame_render_mode = "SOLID"
        
        # Debug console
        self.debug_console = DebugConsole(max_lines=5000)
        self.debug_console.start_capture()
        self.console_auto_scroll = True
        
        # ===== PROPERTIES WINDOW İÇİN =====
        self.property_filter_type = "All"
        self.editing_element_id: Optional[int] = None
        self._prop_edit_buffer: Dict[str, Any] = {}
        self.has_unsaved_changes = False
        
        # ===== MARQUEE SELECTION İÇİN =====
        # Marquee selection için
        self._pending_selection: Optional[Dict] = None
        self.selection_start: Optional[Tuple[float, float]] = None
        self.is_selecting = False
        
        # Mesaj yönetimi
        self.error_message: Optional[str] = None
        self.error_time: Optional[datetime] = None

        logger.debug(f"UIManager received def_mgr with sections: {list(def_mgr.sections.keys()) if def_mgr else 'None'}")
        self.properties_window = PropertiesWindow(
            selection_manager, 
            engine.renderer,
            def_mgr
        )
        engine.ui_manager = self
        
        # ImGui style
        self._setup_imgui_style()
        
        self.command_line = CommandLine(engine)
    
    def update_def_mgr(self, def_mgr):
        """Definition manager'ı güncelle - scene yüklendikten sonra çağrılır"""
        self.properties_window.update_def_mgr(def_mgr)
        
    def _setup_imgui_style(self):
        """ImGui için style ayarları"""
        try:
            style = imgui.get_style()
            style.window_rounding = 5.0
            style.frame_rounding = 3.0
            style.grab_rounding = 3.0
            
            colors = style.colors
            colors[imgui.COLOR_WINDOW_BACKGROUND] = (0.08, 0.08, 0.08, 0.94)
            colors[imgui.COLOR_FRAME_BACKGROUND] = (0.16, 0.16, 0.16, 1.00)
            colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = (0.20, 0.20, 0.20, 1.00)
            colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = (0.28, 0.28, 0.28, 1.00)
        except Exception as e:
            logger.error(f"Style setup error: {e}")
    
    def _show_error(self, message: str):
        """Hata mesajı göster"""
        self.error_message = message
        self.error_time = datetime.now()
        logger.error(message)
    
    def _update_all_renderers(self):
        """Tüm renderer'ları güncelle"""
        if hasattr(self.engine, 'renderer'):
            self.engine.renderer._update_all_renderers()
    
    def _node_restraint(self):
        """Node restraint editor'ü aç"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Node)]
        
        if len(selected) == 1:
            # Tek node seçili
            self.restraint_edit_node = selected[0]
            if self.restraint_edit_node.restraint:
                # Mevcut restraint varsa buffer'a yükle
                r = self.restraint_edit_node.restraint
                self.restraint_edit_buffer = {
                    'ux': r.ux, 'uy': r.uy, 'uz': r.uz,
                    'rx': r.rx, 'ry': r.ry, 'rz': r.rz
                }
            else:
                # Yoksa hepsini False yap
                self.restraint_edit_buffer = {
                    'ux': False, 'uy': False, 'uz': False,
                    'rx': False, 'ry': False, 'rz': False
                }
            self.show_restraint_editor = True
            logger.info(f"Opening restraint editor for node: {self.restraint_edit_node.label}")
        elif len(selected) > 1:
            logger.warning("Please select only one node to edit restraints")
        else:
            logger.warning("No node selected")
    
    def _render_restraint_editor(self):
        """Restraint editor penceresini çiz"""
        if not self.show_restraint_editor or not self.restraint_edit_node:
            return
        
        imgui.set_next_window_size(400, 300, imgui.ONCE)
        imgui.set_next_window_position(100, 100, imgui.ONCE)
        
        opened, self.show_restraint_editor = imgui.begin(
            f"Restraint Editor - Node: {self.restraint_edit_node.label}",
            self.show_restraint_editor,
            imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_ALWAYS_AUTO_RESIZE
        )
        
        if opened:
            imgui.text("Node Coordinates:")
            imgui.text(f"  X: {self.restraint_edit_node.x:.2f}")
            imgui.text(f"  Y: {self.restraint_edit_node.y:.2f}")
            imgui.text(f"  Z: {self.restraint_edit_node.z:.2f}")
            
            imgui.separator()
            
            # ===== 6 DOF CHECKBOX =====
            imgui.text("Degrees of Freedom:")
            imgui.spacing()
            
            # Translational DOFs
            changed, self.restraint_edit_buffer['ux'] = imgui.checkbox("UX (X Translation)", self.restraint_edit_buffer['ux'])
            changed, self.restraint_edit_buffer['uy'] = imgui.checkbox("UY (Y Translation)", self.restraint_edit_buffer['uy'])
            changed, self.restraint_edit_buffer['uz'] = imgui.checkbox("UZ (Z Translation)", self.restraint_edit_buffer['uz'])
            
            imgui.spacing()
            
            # Rotational DOFs
            changed, self.restraint_edit_buffer['rx'] = imgui.checkbox("RX (X Rotation)", self.restraint_edit_buffer['rx'])
            changed, self.restraint_edit_buffer['ry'] = imgui.checkbox("RY (Y Rotation)", self.restraint_edit_buffer['ry'])
            changed, self.restraint_edit_buffer['rz'] = imgui.checkbox("RZ (Z Rotation)", self.restraint_edit_buffer['rz'])
            
            imgui.separator()
            
            # ===== FAST RESTRAINTS =====
            imgui.text("Quick Presets:")
            imgui.spacing()
            
            col_count = 4
            button_width = (imgui.get_content_region_available_width() - (col_count - 1) * 5) / col_count
            
            # Ankastre (Fully Fixed)
            if imgui.button("🔒 Fixed", width=button_width):
                self.restraint_edit_buffer = {
                    'ux': True, 'uy': True, 'uz': True,
                    'rx': True, 'ry': True, 'rz': True
                }
            imgui.same_line()
            
            # Pinned (UX, UY, UZ fixed, rotations free)
            if imgui.button("📌 Pinned", width=button_width):
                self.restraint_edit_buffer = {
                    'ux': True, 'uy': True, 'uz': True,
                    'rx': False, 'ry': False, 'rz': False
                }
            imgui.same_line()
            
            # Roller (UZ fixed only)
            if imgui.button("⚙️ Roller", width=button_width):
                self.restraint_edit_buffer = {
                    'ux': False, 'uy': False, 'uz': True,
                    'rx': False, 'ry': False, 'rz': False
                }
            imgui.same_line()
            
            # Free (all false)
            if imgui.button("🔄 Free", width=button_width):
                self.restraint_edit_buffer = {
                    'ux': False, 'uy': False, 'uz': False,
                    'rx': False, 'ry': False, 'rz': False
                }
            
            imgui.spacing()
            imgui.separator()
            
            # ===== BUTTONS =====
            if imgui.button("Apply", width=120):
                self._apply_restraint_changes()
                self.show_restraint_editor = False
            
            imgui.same_line()
            
            if imgui.button("Cancel", width=120):
                self.show_restraint_editor = False
            
            imgui.same_line()
            
            if imgui.button("Clear All", width=120):
                self.restraint_edit_buffer = {
                    'ux': False, 'uy': False, 'uz': False,
                    'rx': False, 'ry': False, 'rz': False
                }
        
        imgui.end()
    
    def _apply_restraint_changes(self):
        """Restraint değişikliklerini uygula"""
        if not self.restraint_edit_node:
            return
        
        from domain.element import Restraint
        
        # Yeni restraint oluştur
        new_restraint = Restraint(
            ux=self.restraint_edit_buffer['ux'],
            uy=self.restraint_edit_buffer['uy'],
            uz=self.restraint_edit_buffer['uz'],
            rx=self.restraint_edit_buffer['rx'],
            ry=self.restraint_edit_buffer['ry'],
            rz=self.restraint_edit_buffer['rz']
        )
        
        # Node'a ata
        self.restraint_edit_node.restraint = new_restraint
        self.restraint_edit_node.mark_dirty()
        
        # Renderer'ları güncelle
        if hasattr(self.engine, 'renderer') and self.engine.renderer:
            self.engine.renderer.update_geo(self.engine.scene)
        
        logger.info(f"Applied restraints to node {self.restraint_edit_node.label}: {new_restraint}")
    
    def _draw_restraint_editor(self, attr, val, elements):
        """Restraint editörü - Restraint NESNESİ için"""
        imgui.text_disabled("RESTRAINT (UX,UY,UZ,RX,RY,RZ)")
        
        axes = ['ux', 'uy', 'uz', 'rx', 'ry', 'rz']
        axis_labels = ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ']
        
        # Her axis için push/pop sayısını kontrol et
        for i, (axis, label) in enumerate(zip(axes, axis_labels)):
            attr_path = f"{attr}.{axis}"
            
            # Ortak değer kontrolü
            first_val = None
            common_val = True
            
            # İlk elementten değer al
            if elements and hasattr(elements[0], attr):
                target = getattr(elements[0], attr)
                if target is not None:
                    first_val = getattr(target, axis, False)
                else:
                    first_val = False
                    common_val = False
            
            # Diğer elementlerle karşılaştır
            for e in elements[1:]:
                if hasattr(e, attr):
                    target = getattr(e, attr)
                    current_val = getattr(target, axis, False) if target is not None else False
                    if current_val != first_val:
                        common_val = False
                        break
            
            # PushStyle - sadece common_val False ise
            if not common_val:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            
            # Buffer'dan veya first_val'den değeri al
            if attr_path in self._prop_edit_buffer:
                display_val = self._prop_edit_buffer[attr_path]
            else:
                display_val = first_val if first_val is not None else False
            
            changed, new_v = imgui.checkbox(f"{label}##{attr_path}", display_val)
            if changed:
                self._prop_edit_buffer[attr_path] = new_v
                self.has_unsaved_changes = True
            
            # PopStyle - sadece common_val False ise
            if not common_val:
                imgui.pop_style_color(1)
            
            if i % 3 != 2:
                imgui.same_line()
        
        # Eğer hiç restraint yoksa, yeni restraint oluşturmayı öner
        has_any_restraint = False
        for e in elements:
            if hasattr(e, attr) and getattr(e, attr) is not None:
                has_any_restraint = True
                break
        
        if not has_any_restraint and elements:
            imgui.text_colored("No restraints defined", 1.0, 1.0, 0.0, 1.0)
            if imgui.button("Create Restraint"):
                from domain.element import Restraint
                for e in elements:
                    e.restraint = Restraint()
                self.has_unsaved_changes = True

    def _apply_universal_delta(self, elements):
        """Buffer'daki değişiklikleri uygula - Restraint desteği ile"""
        for elem in elements:
            for attr_path, value in self._prop_edit_buffer.items():
                # Attribute path'i parse et
                if '.' in attr_path:
                    main_attr, sub_attr = attr_path.split('.', 1)
                    
                    if hasattr(elem, main_attr):
                        target = getattr(elem, main_attr)
                        
                        # Restraint nesnesi için özel işlem
                        if main_attr == 'restraint' and target is not None:
                            # Restraint'in attribute'unu güncelle
                            if hasattr(target, sub_attr):
                                setattr(target, sub_attr, value)
                                elem.mark_dirty()
                        elif isinstance(target, dict) and sub_attr in target:
                            target[sub_attr] = value
                            elem.mark_dirty()
                else:
                    if hasattr(elem, attr_path):
                        setattr(elem, attr_path, value)
                        elem.mark_dirty()
        
        # Renderer'ları güncelle
        if hasattr(self.engine, 'renderer') and self.engine.renderer:
            self.engine.renderer.update_geo(self.engine.scene)
        
        self.has_unsaved_changes = False
        self._prop_edit_buffer.clear()
        logger.info(f"[UIManager] Applied changes to {len(elements)} elements.")

    def render(self):
        """UI'yi çiz"""
        self.imgui_impl.process_inputs()
        imgui.new_frame()
        
        # Ana menü çubuğu
        if imgui.begin_main_menu_bar():
            self._render_file_menu()
            self._render_view_menu()
            self._render_light_menu()
            self._render_tools_menu()
            self._render_debug_menu()
            self._render_help_menu()
            imgui.end_main_menu_bar()
        
        # ===== TOOLBAR (YENİ) =====
        self._render_toolbar()
        
        # Pencereler
        if self.show_debug_console:
            self._render_debug_console()
        
        self.properties_window.render()

        # if self.show_restraint_editor:
        #     self._render_restraint_editor()
        
        # Command Line
        self.command_line.render()
        
        # Status bar
        self._render_status_bar()
        
        # Render
        imgui.render()
        self.imgui_impl.render(imgui.get_draw_data())
        
    def handle_key(self, key, action):
        """Klavye girdilerini işle - engine'in key callback'inden çağrılacak"""
        # Command Line açık mı?
        if self.command_line.is_open:
            return self.command_line._handle_key(key, action)
        
        # ~ tuşu ile command line aç
        if key == glfw.KEY_GRAVE_ACCENT and action == glfw.PRESS:
            self.command_line.toggle()
            return True
        
        return False
    
    def _render_toolbar(self):
        """Araç çubuğu - Eleman ekleme ve düzenleme"""
        imgui.set_next_window_position(0, 20)  # Menü çubuğunun altında
        imgui.set_next_window_size(self.width, 40)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (5, 5))
        
        imgui.begin(
            "Toolbar", 
            flags=imgui.WINDOW_NO_TITLE_BAR | 
                  imgui.WINDOW_NO_RESIZE | 
                  imgui.WINDOW_NO_MOVE | 
                  imgui.WINDOW_NO_SCROLLBAR |
                  imgui.WINDOW_NO_SAVED_SETTINGS
        )
        
        # ===== ELEMAN EKLEME =====
        imgui.text("➕ Add:")
        imgui.same_line()
        
        if imgui.button("Node"):
            self._add_node()
        imgui.same_line()
        
        if imgui.button("Frame"):
            self._add_frame()
        imgui.same_line()
        
        if imgui.button("Area"):
            self._add_area()
        imgui.same_line()
        
        if imgui.button("Link"):
            self._add_link()
        
        imgui.same_line()
        imgui.separator()
        imgui.same_line()
        
        # ===== DÜZENLEME =====
        imgui.text("✏️ Edit:")
        imgui.same_line()
        
        if imgui.button("Move"):
            self._move_selected()
        imgui.same_line()
        
        if imgui.button("Copy"):
            self._copy_selected()
        imgui.same_line()
        
        if imgui.button("Delete"):
            self._delete_selected()
        imgui.same_line()
        
        if imgui.button("Rotate"):
            self._rotate_selected()
        imgui.same_line()
        
        if imgui.button("Array"):
            self._array_selected()
        
        imgui.same_line()
        imgui.separator()
        imgui.same_line()
        
        # ===== NODE OPERASYONLARI =====
        imgui.text("⚙️ Node:")
        imgui.same_line()
        
        # Restraint butonu - seçili node varsa vurgula
        selected_nodes = [e for e in self.selection.get_selected() if isinstance(e, Node)]
        if len(selected_nodes) == 1:
            if imgui.button("🔒 Restraint##node"):
                self._node_restraint()
        else:
            if imgui.button("Restraint##node"):
                self._node_restraint()
        imgui.same_line()
        
        if imgui.button("Spring"):
            self._node_spring()
        imgui.same_line()
        
        if imgui.button("Mass"):
            self._node_mass()
        
        imgui.same_line()
        imgui.separator()
        imgui.same_line()
        
        # ===== FRAME OPERASYONLARI =====
        imgui.text("📐 Frame:")
        imgui.same_line()
        
        if imgui.button("Trim"):
            self._frame_trim()
        imgui.same_line()
        
        if imgui.button("Extend"):
            self._frame_extend()
        imgui.same_line()
        
        if imgui.button("Ray"):
            self._frame_ray()
        
        imgui.same_line()
        imgui.separator()
        imgui.same_line()
        
        # ===== AREA OPERASYONLARI =====
        imgui.text("🔲 Area:")
        imgui.same_line()
        
        if imgui.button("Section"):
            self._area_section()
        
        imgui.same_line()
        imgui.separator()
        imgui.same_line()
        
        # ===== LINK OPERASYONLARI =====
        imgui.text("🔗 Link:")
        imgui.same_line()
        
        if imgui.button("Properties"):
            self._link_properties()
        
        imgui.end()
        imgui.pop_style_var(2)
    
    # ===== ELEMAN EKLEME METODLARI =====
    
    def _add_node(self):
        """Node ekle"""
        logger.info("Add Node - not implemented")
        # TODO: Node ekleme dialog'u
    
    def _add_frame(self):
        """Frame ekle"""
        logger.info("Add Frame - not implemented")
        # TODO: Frame ekleme dialog'u
    
    def _add_area(self):
        """Area ekle"""
        logger.info("Add Area - not implemented")
        # TODO: Area ekleme dialog'u
    
    def _add_link(self):
        """Link ekle"""
        logger.info("Add Link - not implemented")
        # TODO: Link ekleme dialog'u
    
    # ===== DÜZENLEME METODLARI =====
    
    def _move_selected(self):
        """Seçili elemanları taşı"""
        selected = self.selection.get_selected()
        logger.info(f"Move {len(selected)} elements - not implemented")
        # TODO: Taşıma işlemi
    
    def _copy_selected(self):
        """Seçili elemanları kopyala"""
        selected = self.selection.get_selected()
        logger.info(f"Copy {len(selected)} elements - not implemented")
        # TODO: Kopyalama işlemi
    
    def _delete_selected(self):
        """Seçili elemanları sil"""
        selected = self.selection.get_selected()
        if selected:
            logger.info(f"Delete {len(selected)} elements")
            # TODO: Silme işlemi
            self.selection.clear()
    
    def _rotate_selected(self):
        """Seçili elemanları döndür"""
        selected = self.selection.get_selected()
        logger.info(f"Rotate {len(selected)} elements - not implemented")
        # TODO: Döndürme işlemi
    
    def _array_selected(self):
        """Seçili elemanların dizisini oluştur"""
        selected = self.selection.get_selected()
        logger.info(f"Array {len(selected)} elements - not implemented")
        # TODO: Array oluşturma dialog'u
    
    # ===== NODE OPERASYONLARI =====
    
    def _node_restraint(self):
        """Node restraint ekle"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Node)]
        logger.info(f"Set restraint for {len(selected)} nodes - not implemented")
        # TODO: Restraint dialog'u
    
    def _node_spring(self):
        """Node yay ekle"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Node)]
        logger.info(f"Set spring for {len(selected)} nodes - not implemented")
        # TODO: Spring dialog'u
    
    def _node_mass(self):
        """Node kütle ekle"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Node)]
        logger.info(f"Set mass for {len(selected)} nodes - not implemented")
        # TODO: Mass dialog'u
    
    # ===== FRAME OPERASYONLARI =====
    
    def _frame_trim(self):
        """Frame trim"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Frame)]
        logger.info(f"Trim {len(selected)} frames - not implemented")
        # TODO: Trim işlemi
    
    def _frame_extend(self):
        """Frame extend"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Frame)]
        logger.info(f"Extend {len(selected)} frames - not implemented")
        # TODO: Extend işlemi
    
    def _frame_ray(self):
        """Frame ray"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Frame)]
        logger.info(f"Ray {len(selected)} frames - not implemented")
        # TODO: Ray işlemi
    
    # ===== AREA OPERASYONLARI =====
    
    def _area_section(self):
        """Area kesit atama"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Area)]
        logger.info(f"Set section for {len(selected)} areas - not implemented")
        # TODO: Kesit atama dialog'u
    
    # ===== LINK OPERASYONLARI =====
    
    def _link_properties(self):
        """Link properties"""
        selected = [e for e in self.selection.get_selected() if isinstance(e, Link)]
        logger.info(f"Set properties for {len(selected)} links - not implemented")
        # TODO: Link properties dialog'u
    
    def _render_file_menu(self):
        """File menüsü"""
        if imgui.begin_menu("File", True):
            clicked_import, _ = imgui.menu_item("Import S2K", "Ctrl+I")
            if clicked_import:
                self.engine.import_s2k()
            
            imgui.separator()
            clicked_exit, _ = imgui.menu_item("Exit", "Alt+F4")
            if clicked_exit:
                glfw.set_window_should_close(self.window, True)
            imgui.end_menu()
    
    def _render_help_menu(self):
        """Yardım menüsü"""
        if imgui.begin_menu("Help", True):
            if imgui.menu_item("About")[0]:
                imgui.open_popup("about")
            
            if imgui.begin_popup_modal("about")[0]:
                imgui.text("CAD3 Viewer")
                imgui.text("Version 1.0")
                imgui.text("OpenGL 4.6")
                imgui.separator()
                if imgui.button("Close"):
                    imgui.close_current_popup()
                imgui.end_popup()
            
            imgui.end_menu()
        
    def _render_view_menu(self):
        """View menüsü - SADELEŞTİRİLMİŞ"""
        if imgui.begin_menu("View", True):
            
            # Kamera modu
            is_ortho = (self.engine.cam.view_mode == "ORTHO")
            clicked, _ = imgui.menu_item("Orthographic", "Ctrl+O", is_ortho)
            if clicked:
                self.engine.cam.toggle_projection()
            
            imgui.separator()
            
            # Element görünürlüğü - DOĞRUDAN renderer.show dict'ine
            if hasattr(self.engine, 'renderer'):
                sr = self.engine.renderer
                
                # Yardımcılar
                _, sr.show['grid'] = imgui.menu_item("Show Grid", None, sr.show['grid'])
                _, sr.show['axes'] = imgui.menu_item("Show Gizmo", None, sr.show['axes'])
                _, sr.animating = imgui.menu_item("Animation", None, sr.animating)
                
                imgui.separator()
                
                # Elemanlar
                _, sr.show['node'] = imgui.menu_item("Show Nodes", None, sr.show['node'])
                _, sr.show['frame'] = imgui.menu_item("Show Frames", None, sr.show['frame'])
                _, sr.show['area'] = imgui.menu_item("Show Areas", None, sr.show['area'])
                _, sr.show['link'] = imgui.menu_item("Show Links", None, sr.show['link'])
            
            imgui.separator()
            
            # Kamera komutları
            if imgui.menu_item("Reset Camera", "Ctrl+R")[0]:
                self.engine.cam.reset()
            
            if imgui.menu_item("Focus Model", "Ctrl+F")[0]:
                if hasattr(self.engine, '_focus'):
                    self.engine._focus()
            
            imgui.end_menu()
    
    def _render_light_menu(self):
        """Işık ayarları menüsü - AÇ/KAPA ve KONUM DESTEKLİ"""
        if imgui.begin_menu("Lights", True):
            
            if not hasattr(self.engine, 'renderer') or not self.engine.renderer:
                imgui.text_disabled("No scene renderer")
                imgui.end_menu()
                return
            
            lighting = self.engine.renderer.lighting
            
            # ===== ANAHTARLAR =====
            _, self.engine.renderer.use_lights = imgui.checkbox(
                "Enable Lights", self.engine.renderer.use_lights
            )
            
            imgui.separator()
            
            # ===== KÜRESEL PARAMETRELER =====
            imgui.text("Global Parameters")
            
            changed, lighting.ambient = imgui.slider_float(
                "Ambient", lighting.ambient, 0.0, 1.0, "%.2f"
            )
            
            changed, lighting.diffuse = imgui.slider_float(
                "Diffuse", lighting.diffuse, 0.0, 2.0, "%.2f"
            )
            
            changed, lighting.specular = imgui.slider_float(
                "Specular", lighting.specular, 0.0, 1.0, "%.2f"
            )
            
            changed, lighting.shininess = imgui.slider_float(
                "Shininess", lighting.shininess, 1.0, 256.0, "%.1f"
            )
            
            changed, lighting.brightness = imgui.slider_float(
                "Brightness", lighting.brightness, 0.5, 3.0, "%.2f"
            )
            
            imgui.separator()
            
            # ===== IŞIK KAYNAKLARI =====
            imgui.text("Light Sources")
            
            # Aktif ışık sayısı
            light_count = len(lighting.pos)
            changed, new_count = imgui.slider_int("Light Count", light_count, 0, 8)
            if changed and new_count != light_count:
                # Işık sayısını değiştir
                while len(lighting.pos) < new_count:
                    lighting.pos.append([5000.0, 5000.0, 5000.0])
                    lighting.colors.append([1.0, 1.0, 1.0])
                    lighting.intensities.append(1.0)
                    lighting.speeds.append(0.5)
                    lighting.enabled.append(True)  # YENİ: enabled listesi
                while len(lighting.pos) > new_count:
                    lighting.pos.pop()
                    lighting.colors.pop()
                    lighting.intensities.pop()
                    lighting.speeds.pop()
                    lighting.enabled.pop()
            
            # Her ışık için panel
            for i in range(len(lighting.pos)):
                # Aç/kapa butonu ile birlikte başlık
                enabled = lighting.enabled[i] if hasattr(lighting, 'enabled') else True
                changed, enabled = imgui.checkbox(f"##enable_{i}", enabled)
                if changed:
                    if not hasattr(lighting, 'enabled'):
                        lighting.enabled = [True] * len(lighting.pos)
                    lighting.enabled[i] = enabled
                
                imgui.same_line()
                
                # Ağaç düğümü (sadece ışık açıksa detayları göster)
                if imgui.tree_node(f"Light {i+1}##light_{i}"):
                    if enabled:
                        # Renk
                        col = lighting.colors[i][:3]
                        changed, new_col = imgui.color_edit3(f"Color##{i}", *col)
                        if changed:
                            lighting.colors[i][:3] = new_col
                        
                        # Yoğunluk
                        changed, lighting.intensities[i] = imgui.slider_float(
                            f"Intensity##{i}", lighting.intensities[i], 0.0, 2.0, "%.2f"
                        )
                        
                        # Pozisyon - DRAG ile değiştir!
                        pos = lighting.pos[i]
                        changed, x = imgui.drag_float(f"X##{i}", pos[0], 10.0, -20000, 20000, "X: %.1f")
                        changed, y = imgui.drag_float(f"Y##{i}", pos[1], 10.0, -20000, 20000, "Y: %.1f")
                        changed, z = imgui.drag_float(f"Z##{i}", pos[2], 10.0, -20000, 20000, "Z: %.1f")
                        if changed:
                            lighting.pos[i] = [x, y, z]
                        
                        # Animasyon hızı
                        changed, lighting.speeds[i] = imgui.slider_float(
                            f"Speed##{i}", lighting.speeds[i], 0.1, 2.0, "%.2f"
                        )
                        
                        # Konum sıfırlama butonu
                        if imgui.button(f"Reset Position##{i}"):
                            lighting.pos[i] = [5000.0, 5000.0, 5000.0]
                        
                        imgui.same_line()
                        
                        # Işığı kameraya kilitle
                        if imgui.button(f"Attach to Camera##{i}"):
                            cam_pos = self.engine.cam.position
                            lighting.pos[i] = [cam_pos.x, cam_pos.y, cam_pos.z]
                    
                    else:
                        imgui.text_disabled("Light disabled")
                    
                    imgui.tree_pop()
                
                imgui.separator()
            
            # ===== IŞIK MODLARI =====
            imgui.text("Light Presets")
            
            if imgui.button("Camera Follow"):
                cam_pos = self.engine.cam.position
                lighting.pos = [
                    [cam_pos.x + 2000, cam_pos.y + 1000, cam_pos.z + 2000],
                    [cam_pos.x - 2000, cam_pos.y + 500,  cam_pos.z - 2000],
                    [cam_pos.x,        cam_pos.y + 3000, cam_pos.z],
                ]
                lighting._sync_lists()
            
            imgui.same_line()
            
            if imgui.button("Model Surround") and hasattr(self.engine, 'renderer'):
                center, size = self.engine.renderer.get_scene_bounds()
                lighting.update_model_lights((center, size))
            
            imgui.same_line()
            
            if imgui.button("Reset All"):
                lighting.pos = [
                    [5000.0, 5000.0, 5000.0],
                    [-5000.0, 3000.0, 5000.0],
                    [5000.0, 3000.0, -5000.0],
                ]
                lighting.colors = [
                    [1.0, 0.8, 0.8],
                    [0.8, 1.0, 0.8],
                    [0.8, 0.8, 1.0],
                ]
                lighting.intensities = [1.0, 0.7, 0.5]
                lighting.speeds = [0.5, 0.7, 0.9]
                if hasattr(lighting, 'enabled'):
                    lighting.enabled = [True] * len(lighting.pos)
                lighting._sync_lists()
            
            imgui.end_menu()

    
    def _render_tools_menu(self):
        """Tools menüsü"""
        if imgui.begin_menu("Tools", True):
            _, self.show_debug_console = imgui.menu_item(
                "Debug Console", None, self.show_debug_console
            )
            
            imgui.separator()
            
            # Properties penceresi
            props_visible = self.properties_window.visible
            _, props_visible = imgui.menu_item("Properties", None, props_visible)
            self.properties_window.visible = props_visible
            
            imgui.separator()
            
            if imgui.menu_item("Command Line", "~")[0]:
                self.command_line.toggle()
            
            imgui.end_menu()
    
    def _render_debug_menu(self):
        """Debug menüsü"""
        if imgui.begin_menu("Debug", True):
            
            # Model istatistikleri
            if hasattr(self.engine, 'scene') and self.engine.scene:
                imgui.text(f"Frames: {len(self.engine.scene.frames)}")
                imgui.text(f"Nodes: {len(self.engine.scene.nodes)}")
                imgui.text(f"Areas: {len(self.engine.scene.areas)}")
                imgui.text(f"Links: {len(self.engine.scene.links)}")
            
            imgui.end_menu()
    
    def _render_debug_console(self):
        """Debug console penceresini çiz"""
        imgui.set_next_window_size(600, 400, imgui.ONCE)
        imgui.set_next_window_position(100, 100, imgui.ONCE)
        
        expanded, self.show_debug_console = imgui.begin(
            "Debug Console", 
            self.show_debug_console,
            imgui.WINDOW_NO_COLLAPSE
        )
        
        if expanded:
            # Toolbar
            if imgui.button("Clear"):
                self.debug_console.clear()
            
            imgui.same_line()
            _, self.console_auto_scroll = imgui.checkbox("Auto-scroll", self.console_auto_scroll)
            
            imgui.same_line()
            imgui.text("Filter:")
            imgui.same_line()
            changed, self.debug_console.filter_text = imgui.input_text(
                "##filter", 
                self.debug_console.filter_text, 
                256
            )
            
            imgui.same_line()
            imgui.text(f"({len(self.debug_console.logs)} lines)")
            
            imgui.separator()
            
            # Logları göster
            imgui.begin_child("log_region", height=-imgui.get_frame_height_with_spacing())
            
            logs = self.debug_console.get_filtered_logs()
            
            for log in logs:
                # Hata mesajlarını kırmızı göster
                if "error" in log.lower() or "exception" in log.lower() or "failed" in log.lower():
                    imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.3, 0.3, 1.0)
                    imgui.text_wrapped(log)
                    imgui.pop_style_color(1)
                # Uyarıları sarı göster
                elif "warning" in log.lower() or "warn" in log.lower():
                    imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.8, 0.2, 1.0)
                    imgui.text_wrapped(log)
                    imgui.pop_style_color(1)
                # Başarı mesajlarını yeşil göster
                elif "loaded" in log.lower() or "success" in log.lower() or "✅" in log or "✓" in log:
                    imgui.push_style_color(imgui.COLOR_TEXT, 0.3, 1.0, 0.3, 1.0)
                    imgui.text_wrapped(log)
                    imgui.pop_style_color(1)
                else:
                    imgui.text_wrapped(log)
            
            if self.console_auto_scroll and logs:
                imgui.set_scroll_y(imgui.get_scroll_max_y())
            
            imgui.end_child()
        
        imgui.end()

    def _render_status_bar(self):
        """Alt status bar'ı çiz - PROGRESS BAR DESTEKLİ"""
        display_size = imgui.get_io().display_size
        self.width, self.height = display_size.x, display_size.y
        
        imgui.set_next_window_position(0, self.height - self._STATUS_BAR_HEIGHT)
        imgui.set_next_window_size(self.width, self._STATUS_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (5, 2))
        
        imgui.begin(
            "Status", 
            flags=imgui.WINDOW_NO_TITLE_BAR | 
                imgui.WINDOW_NO_RESIZE | 
                imgui.WINDOW_NO_MOVE | 
                imgui.WINDOW_NO_SCROLLBAR | 
                imgui.WINDOW_NO_SAVED_SETTINGS |
                imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS
        )
        
        # ===== SOL TARAF: Seçim bilgisi veya PROGRESS =====
        if hasattr(self.engine, 'loading_progress') and self.engine.loading_progress < 100:
            # Progress bar göster
            progress = self.engine.loading_progress / 100.0
            imgui.text("📊 Loading...")
            imgui.same_line()
            imgui.progress_bar(progress, (150, 0), f"{self.engine.loading_progress:.0f}%")
        else:
            # Normal seçim bilgisi
            if hasattr(self.engine, 'sel_mgr') and self.engine.sel_mgr:
                selected_count = self.engine.sel_mgr.count()
                if selected_count == 1:
                    selected = self.engine.sel_mgr.get_selected()
                    if selected:
                        element = selected[0]
                        label = getattr(element, 'label', 'unknown')
                        imgui.text(f"📌 {label}")
                    else:
                        imgui.text("📌 No selection")
                elif selected_count > 1:
                    imgui.text(f"📌 {selected_count} elements")
                else:
                    imgui.text("📌 No selection")
            else:
                imgui.text("📌 No selection")
        
        imgui.same_line()
        
        # ===== ORTA: World koordinatları =====
        if hasattr(self.engine, 'input') and self.engine.input.mouse_world_valid:
            pos = self.engine.input.mouse_world_pos
            imgui.text(f"🌍 X:{pos.x:.1f} Y:{pos.y:.1f} Z:{pos.z:.1f}")
        else:
            imgui.text("🌍 ---")
        
        imgui.same_line(position=self.width - 350)
        
        # ===== SAĞ TARAF: Kamera bilgisi =====
        if hasattr(self.engine, 'camera') and self.engine.cam:
            cam_mode = "Ortho" if self.engine.cam.view_mode == "ORTHO" else "Persp"
            cam_pos = self.engine.cam.position
            imgui.text(f"| 📷 {cam_mode} | 🎯 {cam_pos.x:.1f}, {cam_pos.y:.1f}, {cam_pos.z:.1f} | 🔍 {self.engine.cam.dist:.1f}")
        
        # Debug console durumu
        if self.show_debug_console:
            imgui.same_line()
            imgui.text("| 🐞 Console")
        
        imgui.end()
        imgui.pop_style_var(2)
    
    def on_window_resize(self, width, height):
        """Pencere boyutu değiştiğinde"""
        self.width = width
        self.height = height
        imgui.get_io().display_size = (width, height)



    def _draw_type_filter(self, all_selected_elements):
        """
        Seçili elemanları tiplerine göre gruplar ve ImGui Combo Box çizer.
        Filtrelenmiş listeyi döndürür.
        """
        if not all_selected_elements:
            return []

        # Tip isimlerini kullanıcı dostu yap
        display_names = {
            'Node': 'Nodes (Noktalar)',
            'Frame': 'Frames (Çubuklar)',
            'Area': 'Areas (Alanlar)',
            'Link': 'Links (Bağlar)',
        }
        
        # Tip sayılarını hesapla
        type_counts = {}
        for e in all_selected_elements:
            t_name = type(e).__name__
            type_counts[t_name] = type_counts.get(t_name, 0) + 1

        # Combo Box başlığını hazırla
        if self.property_filter_type != "All":
            count = type_counts.get(self.property_filter_type, 0)
            display_name = display_names.get(self.property_filter_type, self.property_filter_type)
            current_label = f"{display_name} [{count}]"
        else:
            current_label = f"Show All ({len(all_selected_elements)})"

        imgui.text_disabled("SEÇİM FİLTRESİ")
        imgui.push_item_width(-1)
        
        if imgui.begin_combo("##filter_combo", current_label):
            # 'Hepsi' seçeneği
            if imgui.selectable(f"Show All ({len(all_selected_elements)})", 
                            self.property_filter_type == "All")[0]:
                self.property_filter_type = "All"
                
            imgui.separator()
            
            # Mevcut tipleri listele
            for t_name, count in type_counts.items():
                friendly_name = display_names.get(t_name, t_name)
                if imgui.selectable(f"{friendly_name} [{count}]", 
                                self.property_filter_type == t_name)[0]:
                    self.property_filter_type = t_name
                    
            imgui.end_combo()
        imgui.pop_item_width()
        imgui.spacing()

        # Listeyi filtrele
        if self.property_filter_type == "All":
            return all_selected_elements
        
        filtered = [e for e in all_selected_elements 
                    if type(e).__name__ == self.property_filter_type]
        
        # Filtrelenmiş liste boşsa All'a dön
        if not filtered and all_selected_elements:
            self.property_filter_type = "All"
            return all_selected_elements
            
        return filtered

    def draw_properties_window(self):
        """Properties penceresini çiz - SELECTION MANAGER UYUMLU"""
        if not self.show_properties: 
            return
        
        imgui.set_next_window_size(350, 500, imgui.FIRST_USE_EVER)
        
        try:
            opened, self.show_properties = imgui.begin("Properties", self.show_properties)
            if not opened:
                imgui.end()
                return

            # ===== SELECTION MANAGER'DAN SEÇİLİ ELEMANLARI AL =====
            elements = self.selection.get_selected()
            
            if not elements:
                imgui.text_disabled("No elements selected.")
                imgui.end()  # <-- 1224. satır? Burada olabilir
                return
            
            # Debug
            # logger.debug(f"[Properties] Selected elements: {[e.label for e in elements]}")

            # Elemanları unique_id'ye göre sırala
            elements = sorted(elements, key=lambda x: x.unique_id)

            # Filtreleme
            elements = self._draw_type_filter(elements)

            if not elements:
                imgui.text_disabled("No elements match filter.")
                imgui.end()  # <-- veya burada
                return
            
            # Seçim hash'ini oluştur
            current_hash = hash(tuple(e.unique_id for e in elements))
            
            # Eğer seçim değiştiyse buffer'ı temizle
            if self.editing_element_id != current_hash:
                self.editing_element_id = current_hash
                self._prop_edit_buffer = {}
                self.has_unsaved_changes = False

            # Dinamik alan çizimi
            self._draw_element_properties(elements)  # <-- Burada push/pop dengesizliği olabilir

            # Alt butonlar
            if self.has_unsaved_changes:
                imgui.separator()
                if imgui.button("Apply Changes", width=imgui.get_content_region_available_width()):
                    self._apply_universal_delta(elements)
                    self.has_unsaved_changes = False
                
                if imgui.button("Discard", width=imgui.get_content_region_available_width()):
                    self.editing_element_id = None
                    self._prop_edit_buffer = {}
                    self.has_unsaved_changes = False

            imgui.end()  # <-- 1224. satır bu değilse, burada olabilir

        except Exception as e:
            
            logger.error(f"Properties Window Error: {e}")
            traceback.print_exc()
        finally:
            imgui.end()  # Hata durumunda da end çağrılmalı

    def _set_val_recursive(self, obj, attr_path, value):
        """Standard list, NumPy array veya direkt attribute günceller"""
        try:
            if "[" in attr_path:
                # Örn: 'position[0]' -> attr_name='position', index=0
                attr_name, rest = attr_path.split("[")
                index = int(rest.replace("]", ""))
                
                target = getattr(obj, attr_name)
                
                # NumPy array veya Liste içine yazma
                if hasattr(target, "__setitem__"):
                    target[index] = value 
            else:
                # Direkt atama (color, opacity vb.)
                setattr(obj, attr_path, value)
        except Exception as e:
            logger.error(f"[UIManager] Recursive set error: {e}")

    def _apply_universal_delta(self, elements):
        """Buffer'daki değişiklikleri uygula - Restraint desteği ile"""
        for elem in elements:
            for attr_path, value in self._prop_edit_buffer.items():
                # Attribute path'i parse et
                if '.' in attr_path:
                    main_attr, sub_attr = attr_path.split('.', 1)
                    
                    if hasattr(elem, main_attr):
                        target = getattr(elem, main_attr)
                        
                        # Restraint nesnesi için özel işlem
                        if main_attr == 'restraint':
                            if target is None:
                                # Restraint yoksa yeni oluştur
                                from domain.element import Restraint
                                target = Restraint()
                                setattr(elem, main_attr, target)
                            
                            # Restraint'in attribute'unu güncelle
                            if hasattr(target, sub_attr):
                                setattr(target, sub_attr, value)
                                elem.mark_dirty()
                        elif isinstance(target, dict) and sub_attr in target:
                            target[sub_attr] = value
                            elem.mark_dirty()
                else:
                    if hasattr(elem, attr_path):
                        setattr(elem, attr_path, value)
                        elem.mark_dirty()
        
        # Renderer'ları güncelle
        if hasattr(self.engine, 'renderer') and self.engine.renderer:
            self.engine.renderer.update_geo(self.engine.scene)
            self.engine.renderer.update_sel()
        
        self.has_unsaved_changes = False
        self._prop_edit_buffer.clear()
        logger.info(f"[UIManager] Applied changes to {len(elements)} elements.")

    def _draw_element_properties(self, elements):
        """Eleman özelliklerini çiz - ÇOKLU SEÇİM DESTEKLİ"""
        if not elements:
            return
        
        # ===== TÜM ELEMENTLERDE ORTAK OLAN ATTRIBUTE'LARI BUL =====
        common_attrs = set(vars(elements[0]).keys())
        for elem in elements[1:]:
            common_attrs &= set(vars(elem).keys())
        
        # Siyah liste
        blacklist = {
            'element_id', 'unique_id', 'is_selected',  
            '_id_counter', 'needs_update', 'profile_params',
            'release_i', 'release_j', 'material', 'nodes'
        }
        
        # Ortak attribute'ları göster
        for attr in sorted(common_attrs):
            if attr in blacklist or attr.startswith('_'):
                continue
            
            # İlk elementten değeri al
            val = getattr(elements[0], attr)
            
            # ===== ÖZEL EDITÖRLER =====
            if attr == 'restraint' and all(hasattr(e, 'restraint') for e in elements):
                self._draw_restraint_editor(attr, val, elements)
            
            elif attr == 'color':
                self._draw_color_editor(attr, val, elements, f"Color##{attr}")
            
            elif attr == 'rotation_deg' and all(hasattr(e, 'rotation_deg') for e in elements):
                self._draw_rotation_editor(attr, val, elements, f"Rotation##{attr}")
            
            elif attr == 'thickness' and all(hasattr(e, 'thickness') for e in elements):
                self._draw_thickness_editor(attr, val, elements, f"Thickness##{attr}")
            
            elif attr == 'propname' and all(hasattr(e, 'propname') for e in elements):
                self._draw_propname_editor(attr, val, elements, f"Property##{attr}")
            
            elif attr in ['x', 'y', 'z'] and all(hasattr(e, attr) for e in elements):
                self._draw_coordinate_editor(attr, val, elements, f"{attr.upper()}##{attr}")
            
            elif attr == 'label':
                self._draw_label_editor(attr, val, elements, f"Label##{attr}")
            
            # ===== SAYISAL DEĞERLER =====
            elif isinstance(val, (int, float, np.number)):
                self._draw_number_editor(attr, val, elements, f"{attr.capitalize()}##{attr}")
            
            # ===== DİĞER (sadece göster) =====
            elif attr == 'section':
                imgui.text_disabled(f"Section: {val.name}")
            else:
                imgui.text(f"{attr.capitalize()}: {val}")

    def _draw_label_editor(self, attr, val, elements, label):
        """Label editörü (tüm elementler için)"""
        common_val = all(getattr(e, attr) == getattr(elements[0], attr) for e in elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, str(val))
        else:
            display_val = ""
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        changed, new_v = imgui.input_text(label, display_val, 256)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)

    def _draw_restraint_editor(self, attr, val, elements):
        """Restraint editörü - Her axis için push/pop garantili"""
        imgui.text_disabled("RESTRAINT (UX,UY,UZ,RX,RY,RZ)")
        
        axes = ['ux', 'uy', 'uz', 'rx', 'ry', 'rz']
        axis_labels = ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ']
        
        push_count = 0  # Push sayacı
        
        for i, (axis, label) in enumerate(zip(axes, axis_labels)):
            attr_path = f"{attr}.{axis}"
            
            # Ortak değer kontrolü
            first_val = False
            common_val = True
            
            if elements and hasattr(elements[0], attr):
                target = getattr(elements[0], attr)
                if target is not None:
                    first_val = getattr(target, axis, False)
            
            for e in elements[1:]:
                if hasattr(e, attr):
                    target = getattr(e, attr)
                    current_val = getattr(target, axis, False) if target is not None else False
                    if current_val != first_val:
                        common_val = False
                        break
            
            # PushStyle - sadece ortak değilse
            if not common_val:
                imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
                push_count += 1
            
            # Checkbox
            display_val = self._prop_edit_buffer.get(attr_path, first_val)
            changed, new_v = imgui.checkbox(f"{label}##{attr_path}", display_val)
            if changed:
                self._prop_edit_buffer[attr_path] = new_v
                self.has_unsaved_changes = True
            
            # PopStyle - eğer push yapıldıysa
            if not common_val and push_count > 0:
                imgui.pop_style_color()
                push_count -= 1
            
            if i % 3 != 2:
                imgui.same_line()
        
        # Kalan push'ları temizle (güvenlik)
        while push_count > 0:
            imgui.pop_style_color()
            push_count -= 1
        
        # Eğer hiç restraint yoksa
        has_any = any(hasattr(e, attr) and getattr(e, attr) is not None for e in elements)
        if not has_any and elements:
            imgui.text_colored("No restraints defined", 1.0, 1.0, 0.0, 1.0)
            if imgui.button("Create Restraint"):
                from domain.element import Restraint
                for e in elements:
                    e.restraint = Restraint()
                self.has_unsaved_changes = True

    def _draw_rotation_editor(self, attr, val, elements, label):
        """Rotation editörü (Frame için)"""
        # Ortak değer kontrolü
        common_val = all(getattr(e, attr) == getattr(elements[0], attr) for e in elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, float(val))
        else:
            display_val = 0.0
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            label = f"{label} (multiple values)"
        
        changed, new_v = imgui.input_float(label, display_val)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)

    def _draw_thickness_editor(self, attr, val, elements, label):
        """Thickness editörü (Area için)"""
        common_val = all(getattr(e, attr) == getattr(elements[0], attr) for e in elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, float(val))
        else:
            display_val = 0.0
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        changed, new_v = imgui.input_float(label, display_val)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)

    def _draw_propname_editor(self, attr, val, elements, label):
        """Propname editörü (Link için)"""
        common_val = all(getattr(e, attr) == getattr(elements[0], attr) for e in elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, str(val))
        else:
            display_val = ""
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        changed, new_v = imgui.input_text(label, display_val, 256)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)

    def _draw_coordinate_editor(self, attr, val, elements, label):
        """Koordinat editörü - SADECE AYNI TİP ELEMENTLERDE ÇALIŞIR"""
        # Sadece bu attribute'a sahip elementleri filtrele
        relevant_elements = [e for e in elements if hasattr(e, attr)]
        if not relevant_elements:
            return
        
        # Ortak değer kontrolü
        first_val = getattr(relevant_elements[0], attr)
        common_val = all(getattr(e, attr) == first_val for e in relevant_elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, float(first_val))
        else:
            display_val = 0.0
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        changed, new_v = imgui.input_float(label, display_val)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)

    def _draw_color_editor(self, attr, val, elements, label):
        """Renk editörü - push/pop garantili"""
        push_count = 0
        
        # Ortak değer kontrolü
        first_val = val if isinstance(val, (list, tuple)) else [1,1,1]
        common_val = all(getattr(e, attr) == first_val for e in elements if hasattr(e, attr))
        
        if not common_val:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            push_count += 1
        
        display_val = self._prop_edit_buffer.get(attr, first_val[:3] if hasattr(first_val, '__getitem__') else first_val)
        changed, new_val = imgui.color_edit3(label, *display_val)
        if changed:
            self._prop_edit_buffer[attr] = list(new_val)
            self.has_unsaved_changes = True
        
        while push_count > 0:
            imgui.pop_style_color()
            push_count -= 1

    def _draw_number_editor(self, attr, val, elements, label):
        """Sayısal değer editörü"""
        common_val = all(getattr(e, attr) == getattr(elements[0], attr) for e in elements)
        
        if common_val:
            display_val = self._prop_edit_buffer.get(attr, float(val))
        else:
            display_val = 0.0
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        changed, new_v = imgui.input_float(label, display_val)
        if changed:
            self._prop_edit_buffer[attr] = new_v
            self.has_unsaved_changes = True
        
        if not common_val:
            imgui.pop_style_color(1)