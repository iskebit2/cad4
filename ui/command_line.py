# ui/command_line.py

import imgui
import numpy as np
import glm
from typing import Optional, List, Dict, Any, Callable
import logging
import shlex
import traceback

logger = logging.getLogger(__name__)

class CommandLine:
    """
    CAD3 için komut satırı arayüzü
    - "node 100 200 300" gibi komutlar
    - Tab completion
    - Komut geçmişi
    """
    
    def __init__(self, engine):
        self.engine = engine
        self.is_open = False
        self.input_buffer = ""
        self.history: List[str] = []
        self.history_index = -1
        self.suggestions: List[str] = []
        self.selected_suggestion = -1
        self.message = ""
        self.message_color = (0.8, 0.8, 0.8, 1.0)
        self.message_timeout = 0
        
        # Komut kayıtları
        self.commands: Dict[str, Dict[str, Any]] = {}
        self._register_default_commands()
        
        # Geçici durum (çok adımlı komutlar için)
        self.waiting_for_input = False
        self.current_command = None
        self.current_step = 0
        self.step_data = {}
    
    def _register_default_commands(self):
        """Varsayılan komutları kaydet"""
        
        # ===== ELEMAN EKLEME =====
        self.register_command(
            "node", self._cmd_node,
            help="Node ekle: node x y z [label]",
            usage="node <x> <y> <z> [label]"
        )
        
        self.register_command(
            "frame", self._cmd_frame,
            help="Frame ekle: frame node1 node2 section [rotation]",
            usage="frame <node1_id> <node2_id> <section_name> [rotation]"
        )
        
        self.register_command(
            "area", self._cmd_area,
            help="Area ekle: area node1 node2 node3 ... thickness",
            usage="area <node_ids...> <thickness>"
        )
        
        self.register_command(
            "link", self._cmd_link,
            help="Link ekle: link node1 node2 propname",
            usage="link <node1_id> <node2_id> <propname>"
        )
        
        # ===== KAMERA =====
        self.register_command(
            "camera", self._cmd_camera,
            help="Kamera ayarları: camera [pos|target|dist|reset]",
            usage="camera <pos x y z|target x y z|dist d|reset>"
        )
        
        self.register_command(
            "view", self._cmd_view,
            help="Görünüm: view [persp|ortho|top|front|right]",
            usage="view <mode>"
        )
        
        # ===== SEÇİM =====
        self.register_command(
            "select", self._cmd_select,
            help="Seçim: select [all|none|bytype|id]",
            usage="select <all|none|bytype type|id id>"
        )
        
        self.register_command(
            "delete", self._cmd_delete,
            help="Seçili elemanları sil: delete",
            usage="delete"
        )
        
        # ===== DOSYA =====
        self.register_command(
            "import", self._cmd_import,
            help="Dosya import: import <path>",
            usage="import <s2k_file>"
        )
        
        self.register_command(
            "export", self._cmd_export,
            help="Dosya export: export <path>",
            usage="export <s2k_file>"
        )
        
        # ===== YARDIM =====
        self.register_command(
            "help", self._cmd_help,
            help="Komut listesini göster: help [command]",
            usage="help [command]"
        )
        
        self.register_command(
            "clear", self._cmd_clear,
            help="Ekranı temizle",
            usage="clear"
        )
        
        self.register_command(
            "exit", self._cmd_exit,
            help="Komut satırını kapat",
            usage="exit"
        )
    
    def register_command(self, name: str, func: Callable, help: str = "", usage: str = ""):
        """Yeni komut kaydet"""
        self.commands[name] = {
            'func': func,
            'help': help,
            'usage': usage
        }
    
    def toggle(self):
        """Komut satırını aç/kapa"""
        self.is_open = not self.is_open
        if self.is_open:
            self.input_buffer = ""
            self.history_index = -1
            self.suggestions = []
            self.message = "CAD3 Command Line - Type 'help' for commands"
            self.message_color = (0.3, 0.8, 0.3, 1.0)
    
    def show_message(self, msg: str, color=(0.8, 0.8, 0.8, 1.0), timeout=3.0):
        """Mesaj göster"""
        self.message = msg
        self.message_color = color
        self.message_timeout = timeout
    
    def _update_suggestions(self):
        """Otomatik tamamlama önerileri"""
        if not self.input_buffer:
            self.suggestions = list(self.commands.keys())
            return
        
        # Komut adı tamamlama
        parts = self.input_buffer.split()
        if len(parts) == 1:
            # İlk kelime - komut adı tamamlama
            self.suggestions = [
                cmd for cmd in self.commands.keys()
                if cmd.startswith(parts[0])
            ]
        else:
            # Alt komut tamamlama (komuta özel)
            cmd_name = parts[0]
            if cmd_name in self.commands:
                # TODO: Komuta özel tamamlama eklenebilir
                self.suggestions = []
            else:
                self.suggestions = []
    
    def _complete_suggestion(self):
        """Seçili öneriyi tamamla"""
        if self.suggestions and 0 <= self.selected_suggestion < len(self.suggestions):
            parts = self.input_buffer.split()
            if len(parts) == 1:
                # Komut adını tamamla
                self.input_buffer = self.suggestions[self.selected_suggestion]
            self.suggestions = []
            self.selected_suggestion = -1
    
    def _execute_command(self):
        """Komutu çalıştır"""
        if not self.input_buffer.strip():
            return
        
        command_line = self.input_buffer.strip()
        self.history.append(command_line)
        self.history_index = -1
        
        try:
            # Komutu parse et
            parts = shlex.split(command_line)
            cmd_name = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd_name in self.commands:
                # Komutu çalıştır
                self.commands[cmd_name]['func'](args)
            else:
                self.show_message(f"Unknown command: {cmd_name}", (1.0, 0.3, 0.3, 1.0))
        
        except Exception as e:
            self.show_message(f"Error: {str(e)}", (1.0, 0.3, 0.3, 1.0))
            logger.error(traceback.format_exc())
        
        self.input_buffer = ""
    
    def _handle_key(self, key, action):
        """Klavye girdilerini işle"""
        if not self.is_open:
            return False
        
        if action != glfw.PRESS and action != glfw.REPEAT:
            return True
        
        # ESC: komut satırını kapat
        if key == glfw.KEY_ESCAPE:
            self.toggle()
            return True
        
        # ENTER: komutu çalıştır
        if key == glfw.KEY_ENTER:
            self._execute_command()
            return True
        
        # TAB: otomatik tamamlama
        if key == glfw.KEY_TAB:
            if not self.suggestions:
                self._update_suggestions()
                self.selected_suggestion = 0 if self.suggestions else -1
            else:
                # Sonraki öneri
                self.selected_suggestion = (self.selected_suggestion + 1) % len(self.suggestions)
            return True
        
        # UP: önceki komut
        if key == glfw.KEY_UP:
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.input_buffer = self.history[-(self.history_index + 1)]
            return True
        
        # DOWN: sonraki komut
        if key == glfw.KEY_DOWN:
            if self.history_index >= 0:
                self.history_index -= 1
                if self.history_index >= 0:
                    self.input_buffer = self.history[-(self.history_index + 1)]
                else:
                    self.input_buffer = ""
            return True
        
        return False
    
    def render(self):
        """ImGui ile komut satırını çiz"""
        if not self.is_open:
            return
        
        display_size = imgui.get_io().display_size
        width = display_size.x * 0.7
        height = 120
        x = (display_size.x - width) / 2
        y = display_size.y - 150
        
        imgui.set_next_window_position(x, y)
        imgui.set_next_window_size(width, height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 8.0)
        imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, 0.1, 0.1, 0.1, 0.95)
        
        flags = imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_MOVE
        expanded, self.is_open = imgui.begin("Command Line", self.is_open, flags)
        
        if expanded:
            # Mesaj alanı
            if self.message:
                imgui.push_style_color(imgui.COLOR_TEXT, *self.message_color)
                imgui.text_wrapped(f"> {self.message}")
                imgui.pop_style_color(1)
                imgui.separator()
            
            # Girdi alanı
            imgui.push_item_width(-1)
            
            # DÜZELTME: callback flag'ini kaldır, basit input_text kullan
            changed, self.input_buffer = imgui.input_text(
                "##cmd_input", 
                self.input_buffer, 
                256,
                imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
            )
            
            if changed:
                # Her değişiklikte önerileri güncelle
                self._update_suggestions()
                self.selected_suggestion = -1
            
            # Enter basıldı mı kontrol et (INPUT_TEXT_ENTER_RETURNS_TRUE ile)
            # input_text zaten enter basıldığında True döner, buffer'ı değiştirmez
            # Bu yüzden ayrıca kontrol etmeye gerek yok
            
            imgui.pop_item_width()
            
            # Otomatik tamamlama önerileri
            if self.suggestions:
                imgui.separator()
                for i, sugg in enumerate(self.suggestions):
                    if i == self.selected_suggestion:
                        imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.5, 0.8, 0.8)
                    
                    if imgui.small_button(sugg):
                        self.input_buffer = sugg
                        self.suggestions = []
                        self.selected_suggestion = -1
                    
                    if i == self.selected_suggestion:
                        imgui.pop_style_color(1)
                    
                    if i < len(self.suggestions) - 1:
                        imgui.same_line()
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(1)
        
        # Mesaj timeout
        if self.message_timeout > 0:
            self.message_timeout -= imgui.get_io().delta_time
            if self.message_timeout <= 0:
                self.message = ""
    
    # ===== KOMUT İMPLEMENTASYONLARI =====
    
    def _cmd_node(self, args):
        """Node ekle: node x y z [label]"""
        if len(args) < 3:
            self.show_message("Usage: node <x> <y> <z> [label]", (1.0, 0.8, 0.3, 1.0))
            return
        
        try:
            x, y, z = float(args[0]), float(args[1]), float(args[2])
            label = args[3] if len(args) > 3 else f"N{len(self.engine.scene.nodes)+1}"
            
            from domain.element import Node
            node = Node(x, y, z, label)
            self.engine.scene.add_node(node)
            
            self.show_message(f"Node {label} created at ({x}, {y}, {z})", (0.3, 1.0, 0.3, 1.0))
            self.engine.renderer.update_geo(self.engine.scene)
            
        except ValueError:
            self.show_message("Invalid coordinates", (1.0, 0.3, 0.3, 1.0))
    
    def _cmd_frame(self, args):
        """Frame ekle"""
        self.show_message("Frame command - not fully implemented", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_area(self, args):
        """Area ekle"""
        self.show_message("Area command - not fully implemented", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_link(self, args):
        """Link ekle"""
        self.show_message("Link command - not fully implemented", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_camera(self, args):
        """Kamera ayarları"""
        if not args:
            cam = self.engine.cam
            self.show_message(
                f"Camera: pos({cam.position.x:.1f}, {cam.position.y:.1f}, {cam.position.z:.1f}) "
                f"target({cam.target.x:.1f}, {cam.target.y:.1f}, {cam.target.z:.1f}) "
                f"dist={cam.dist:.1f} mode={cam.view_mode}",
                (0.8, 0.8, 0.8, 1.0)
            )
            return
        
        cmd = args[0].lower()
        
        if cmd == "pos" and len(args) >= 4:
            try:
                x, y, z = float(args[1]), float(args[2]), float(args[3])
                self.engine.cam.position = glm.vec3(x, y, z)
                self.show_message(f"Camera position set to ({x}, {y}, {z})")
            except ValueError:
                self.show_message("Invalid position", (1.0, 0.3, 0.3, 1.0))
        
        elif cmd == "target" and len(args) >= 4:
            try:
                x, y, z = float(args[1]), float(args[2]), float(args[3])
                self.engine.cam.target = glm.vec3(x, y, z)
                self.engine.cam._update_position()
                self.show_message(f"Camera target set to ({x}, {y}, {z})")
            except ValueError:
                self.show_message("Invalid target", (1.0, 0.3, 0.3, 1.0))
        
        elif cmd == "dist" and len(args) >= 2:
            try:
                d = float(args[1])
                self.engine.cam.dist = d
                self.engine.cam._update_position()
                self.show_message(f"Camera distance set to {d}")
            except ValueError:
                self.show_message("Invalid distance", (1.0, 0.3, 0.3, 1.0))
        
        elif cmd == "reset":
            self.engine.cam.reset()
            self.show_message("Camera reset")
        
        else:
            self.show_message("Usage: camera [pos x y z|target x y z|dist d|reset]", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_view(self, args):
        """Görünüm modları"""
        if not args:
            self.show_message(f"Current view: {self.engine.cam.view_mode}", (0.8, 0.8, 0.8, 1.0))
            return
        
        mode = args[0].lower()
        
        if mode in ["persp", "perspective"]:
            if self.engine.cam.view_mode != "PERSPECTIVE":
                self.engine.cam.toggle_projection()
            self.show_message("Perspective view")
        
        elif mode in ["ortho", "orthographic"]:
            if self.engine.cam.view_mode != "ORTHO":
                self.engine.cam.toggle_projection()
            self.show_message("Orthographic view")
        
        elif mode == "top":
            self.engine.cam.pitch = 90.0
            self.engine.cam.yaw = 0.0
            self.engine.cam._update_position()
            self.show_message("Top view")
        
        elif mode == "front":
            self.engine.cam.pitch = 0.0
            self.engine.cam.yaw = 0.0
            self.engine.cam._update_position()
            self.show_message("Front view")
        
        elif mode == "right":
            self.engine.cam.pitch = 0.0
            self.engine.cam.yaw = 90.0
            self.engine.cam._update_position()
            self.show_message("Right view")
        
        else:
            self.show_message("Usage: view [persp|ortho|top|front|right]", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_select(self, args):
        """Seçim komutları"""
        if not args:
            selected = self.engine.sel_mgr.get_selected()
            self.show_message(f"Selected: {len(selected)} elements", (0.8, 0.8, 0.8, 1.0))
            return
        
        cmd = args[0].lower()
        
        if cmd == "all":
            # Tüm elemanları seç
            for e in self.engine.scene.all_elements.values():
                e.is_selected = True
                self.engine.sel_mgr.selected.add(e.unique_id)
            self.engine.renderer.update_sel()
            self.show_message(f"Selected all elements")
        
        elif cmd == "none":
            self.engine.sel_mgr.clear()
            self.show_message("Cleared selection")
        
        elif cmd == "bytype" and len(args) >= 2:
            # Tip bazlı seçim
            type_name = args[1].lower()
            count = 0
            self.engine.sel_mgr.clear()
            
            for e in self.engine.scene.all_elements.values():
                if type(e).__name__.lower() == type_name:
                    e.is_selected = True
                    self.engine.sel_mgr.selected.add(e.unique_id)
                    count += 1
            
            self.engine.renderer.update_sel()
            self.show_message(f"Selected {count} {type_name} elements")
        
        elif cmd == "id" and len(args) >= 2:
            try:
                uid = int(args[1])
                e = self.engine.scene.get_element_by_unique_id(uid)
                if e:
                    self.engine.sel_mgr.clear()
                    e.is_selected = True
                    self.engine.sel_mgr.selected.add(e.unique_id)
                    self.engine.renderer.update_sel()
                    self.show_message(f"Selected element {uid}: {e.label}")
                else:
                    self.show_message(f"Element {uid} not found", (1.0, 0.3, 0.3, 1.0))
            except ValueError:
                self.show_message("Invalid ID", (1.0, 0.3, 0.3, 1.0))
        
        else:
            self.show_message("Usage: select [all|none|bytype type|id id]", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_delete(self, args):
        """Seçili elemanları sil"""
        selected = self.engine.sel_mgr.get_selected()
        count = len(selected)
        
        if count == 0:
            self.show_message("No elements selected", (1.0, 0.8, 0.3, 1.0))
            return
        
        # TODO: Gerçek silme işlemi
        self.show_message(f"Deleted {count} elements (simulated)", (0.3, 1.0, 0.3, 1.0))
        self.engine.sel_mgr.clear()
    
    def _cmd_import(self, args):
        """Dosya import"""
        if not args:
            self.show_message("Usage: import <path>", (1.0, 0.8, 0.3, 1.0))
            return
        
        path = args[0]
        self.show_message(f"Importing {path}...", (0.8, 0.8, 0.8, 1.0))
        
        # engine.import_s2k(path) - TODO: implement
    
    def _cmd_export(self, args):
        """Dosya export"""
        if not args:
            self.show_message("Usage: export <path>", (1.0, 0.8, 0.3, 1.0))
            return
        
        self.show_message(f"Export command - not implemented", (1.0, 0.8, 0.3, 1.0))
    
    def _cmd_help(self, args):
        """Yardım"""
        if not args:
            # Tüm komutları listele
            self.show_message("Available commands:", (0.3, 0.8, 1.0, 1.0))
            for name, cmd in sorted(self.commands.items()):
                self.show_message(f"  {name:12} - {cmd['help']}", (0.8, 0.8, 0.8, 1.0))
        else:
            # Belirli bir komut için yardım
            cmd_name = args[0].lower()
            if cmd_name in self.commands:
                cmd = self.commands[cmd_name]
                self.show_message(f"Command: {cmd_name}", (0.3, 0.8, 1.0, 1.0))
                self.show_message(f"  Help: {cmd['help']}", (0.8, 0.8, 0.8, 1.0))
                self.show_message(f"  Usage: {cmd['usage']}", (0.8, 0.8, 0.8, 1.0))
            else:
                self.show_message(f"Unknown command: {cmd_name}", (1.0, 0.3, 0.3, 1.0))
    
    def _cmd_clear(self, args):
        """Ekranı temizle"""
        self.message = ""
    
    def _cmd_exit(self, args):
        """Komut satırını kapat"""
        self.toggle()