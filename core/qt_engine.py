"""
qt_engine.py - PyQt5 ile OpenGL 3D Görüntüleme Motoru

Sadece 3D viewport ve interaction işlevlerini içerir.
UI, model yükleme ve demo işlevleri mainQ.py'ye aittir.
"""
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False

import sys
import logging
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable
from enum import Enum

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent, QKeyEvent, QSurfaceFormat
from OpenGL.GL import *
import glm

# CAD3 imports
from core.camera import Camera
from domain.scene import Scene
from domain.element import Node, Frame, Area, Link, Element
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from render import shaderprogram
from tools.gridsystem import GridSystem
from tools.snapsquare import SnapSquareRenderer
from core.selection_manager import SelectionManager
from core.selection_policy import SelectionPolicy
from core.qt_marquee_selector import MarqueeSelector
from ui.inputmanager import InputManager

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shader dizini
SHADER_DIR = Path(shaderprogram.__file__).resolve().parent / "shaders"


class InteractionMode(Enum):
    """Etkileşim modları - mouse event'lerinin davranışını belirler"""
    SELECT = "select"           # Eleman seçme (varsayılan)
    DRAW_NODE = "draw_node"     # Node çizme
    DRAW_BEAM = "draw_beam"     # Beam çizme
    DRAW_AREA = "draw_area"     # Alan çizme
    MEASURE = "measure"         # Ölçüm
    DELETE = "delete"           # Silme modu


class RenderEngineWidget(QOpenGLWidget):
    """
    Ana OpenGL Render Widget - Sadece 3D viewport ve interaction
    
    Sorumlulukları:
    - OpenGL context yönetimi
    - Shader yükleme ve yönetimi
    - Scene render etme
    - Mouse/keyboard interaction (mod destekli)
    - Picking, hover, selection
    - Kamera kontrolü
    """
    
    # Sinyaller
    selection_changed = Signal(list)           # Seçim değiştiğinde
    hover_changed = Signal(object)             # Hover değiştiğinde (element veya None)
    mode_changed = Signal(str)                 # Interaction modu değiştiğinde
    scene_loaded = Signal(object)              # Scene yüklendiğinde
    status_message = Signal(str)               # Durum mesajları
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # === Pencere boyutları ===
        self._width = 800
        self._height = 600
        
        # === Interaction Modu (varsayılan: SELECT) ===
        self._interaction_mode = InteractionMode.SELECT
        
        # === Kamera ===
        self.cam = Camera()
        self.cam.set_aspect(self._width, self._height)
        self.cam.pitch, self.cam.yaw, self.cam.dist = 30.0, -45.0, 50.0
        self.cam._update_position()
        
        # === Input Manager ===
        self.input = InputManager()
        
        # === Shader'lar ===
        self.shaders: Dict[str, Optional[ShaderProgram]] = {}
        self._shader_loaded = False
        
        # === Renderer ===
        self.renderer: Optional[SceneRenderer] = None
        self.scene: Optional[Scene] = None
        
        # === Grid ve Snap ===
        self.grid: Optional[GridSystem] = None
        self.snap: Optional[SnapSquareRenderer] = None
        
        # === Selection ===
        self.selection_manager: Optional[SelectionManager] = None
        self.selection_policy: Optional[SelectionPolicy] = None
        self.marquee_selector: Optional[MarqueeSelector] = None
        
        # === Hover Mekanizması ===
        self._hover_id: int = 0
        self._hover_element_type: Optional[str] = None
        self._hover_enabled: bool = True
        
        # Hover throttling
        self._last_hover_x: int = -1
        self._last_hover_y: int = -1
        self._last_hover_time: float = 0
        self._hover_throttle: float = 0.033  # ~30 FPS
        
        # Async picking
        self._pending_pick_check: bool = False
        self._last_pick_x: int = -1
        self._last_pick_y: int = -1
        
        # === Mouse State ===
        self._last_mouse_pos: Optional[glm.vec2] = None
        self._is_dragging: bool = False
        
        # === Timer ===
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # ~60 FPS
        
        # Mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        logger.info("RenderEngineWidget initialized")
    
    # ==================== OpenGL Yaşam Döngüsü ====================
    
    def initializeGL(self):
        """OpenGL başlatma"""
        self.makeCurrent()
        
        # OpenGL ayarları
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.96, 0.96, 0.92, 1.0)
        
        # Shader'ları yükle
        self._load_shaders()
        
        # Bileşenleri oluştur
        self._initialize_components()
        
        logger.info("OpenGL initialized")
    
    def _load_shaders(self):
        """Shader'ları yükle"""
        shader_names = ["pick", "standard", "node", "simple", "2d_overlay"]
        loaded_count = 0
        
        for name in shader_names:
            v = SHADER_DIR / f"{name}.vert"
            f = SHADER_DIR / f"{name}.frag"
            try:
                self.shaders[name] = ShaderProgram(name, str(v), str(f))
                loaded_count += 1
                logger.debug(f"✓ {name} shader loaded")
            except Exception as e:
                logger.error(f"✗ {name} shader failed: {e}")
                self.shaders[name] = None
        
        self._shader_loaded = True
        logger.info(f"Shaders loaded: {loaded_count}/{len(shader_names)}")
    
    def _initialize_components(self):
        """Renderer ve yardımcı bileşenleri oluştur"""
        # Shader referansları
        pick_s = self.shaders.get("pick")
        standard_s = self.shaders.get("standard")
        node_s = self.shaders.get("node")
        simple_s = self.shaders.get("simple")
        overlay_s = self.shaders.get("2d_overlay")
        
        # Grid ve Snap
        self.grid = GridSystem(simple_s)
        self.snap = SnapSquareRenderer()
        
        # SceneRenderer
        self.renderer = SceneRenderer(
            pick_s=pick_s,
            standard_s=standard_s,
            node_s=node_s,
            simple_s=simple_s,
            overlay_s=overlay_s,
            w=self._width,
            h=self._height
        )
        self.renderer.set_cam(self.cam)
        self.renderer.set_grid(self.grid)
        self.renderer.set_snap(self.snap)
        self.renderer.set_engine(self)
        
        # Selection
        self.selection_policy = SelectionPolicy(self.input)
        self.selection_manager = SelectionManager(self.renderer)
        self.marquee_selector = MarqueeSelector(
            self, self.selection_manager, self.selection_policy
        )
        self.renderer.set_marquee(self.marquee_selector)
        
        # Scene null
        self.scene = None
    
    def paintGL(self):
        """OpenGL çizim"""
        # 1. Async pick sonucunu kontrol et
        if self._pending_pick_check:
            self._check_pick_result()
        
        # 2. Render
        if self.renderer:
            target_fbo = self.defaultFramebufferObject()
            self.renderer.render(self.cam, target_fbo=target_fbo)
        
        # 3. Snap overlay
        if self.snap and self.input:
            self.snap.draw(
                self,
                self.input.mouse_pos.x,
                self.input.mouse_pos.y,
                self._hover_id,
                self._hover_element_type,
                w=self.width(),
                h=self.height()
            )
    
    def resizeGL(self, w: int, h: int):
        """Pencere boyut değişikliği"""
        self._width = w
        self._height = h
        self.cam.set_aspect(w, h)
        if self.renderer:
            self.renderer.resize(w, h)
        glViewport(0, 0, w, h)
    
    # ==================== Scene Yönetimi ====================
    
    def set_scene(self, scene: Scene) -> bool:
        """
        Scene'i ayarla - S2KLoader veya diğer kaynaklardan gelen scene için
        
        Args:
            scene: Yüklenecek Scene nesnesi
            
        Returns:
            bool: Başarılı ise True
        """
        if not self.renderer:
            logger.warning("Renderer not initialized")
            return False
        
        self.makeCurrent()
        self.scene = scene
        
        # Renderer'ı güncelle
        self.renderer.set_scene(scene)
        self.renderer.update_geo(scene)
        
        # Selection manager'ı güncelle
        self.selection_manager = SelectionManager(self.renderer)
        
        # Bounds hesapla ve kamerayı ayarla
        try:
            center, size = scene.get_bounds()
            self.cam.update_bounds(center, size)
            self.cam.focus_on_model()
            logger.info(f"Scene loaded: {len(scene.nodes)} nodes, {len(scene.frames)} frames")
        except Exception as e:
            logger.warning(f"Could not calculate bounds: {e}")
            self.cam.reset()
        
        self.update()
        
        # Scene loaded sinyalini yayınla
        self.scene_loaded.emit(scene)
        self.status_message.emit(f"Scene loaded: {len(scene.nodes)} nodes")
        
        return True
    
    def get_scene(self) -> Optional[Scene]:
        """Mevcut scene'i döndür"""
        return self.scene
    
    def get_renderer(self) -> Optional[SceneRenderer]:
        """Renderer'ı döndür"""
        return self.renderer
    
    # ==================== Element Erişimi ====================
    
    def get_element_from_id(self, element_id: int) -> Optional[Element]:
        """ID'den element bul"""
        if self.renderer:
            return self.renderer.get_element_from_id(element_id)
        return None
    
    def get_selected_elements(self) -> List[Element]:
        """Seçili elemanları döndür"""
        if self.selection_manager:
            return self.selection_manager.get_selected()
        return []
    
    # ==================== Interaction Modu ====================
    
    def set_interaction_mode(self, mode: InteractionMode):
        """Etkileşim modunu değiştir"""
        if self._interaction_mode != mode:
            self._interaction_mode = mode
            self.mode_changed.emit(mode.value)
            self.status_message.emit(f"Mode: {mode.value}")
            logger.debug(f"Interaction mode changed to: {mode.value}")
    
    def get_interaction_mode(self) -> InteractionMode:
        """Mevcut etkileşim modunu döndür"""
        return self._interaction_mode
    
    # ==================== Görünürlük Kontrolleri ====================
    
    def toggle_visibility(self, element_type: str) -> bool:
        """Element tipinin görünürlüğünü toggle et"""
        if self.renderer and element_type in self.renderer.show:
            self.renderer.show[element_type] = not self.renderer.show[element_type]
            self.update()
            return self.renderer.show[element_type]
        return False
    
    def set_visibility(self, element_type: str, visible: bool):
        """Element tipinin görünürlüğünü ayarla"""
        if self.renderer and element_type in self.renderer.show:
            self.renderer.show[element_type] = visible
            self.update()
    
    def toggle_render_mode(self) -> str:
        """Render modunu değiştir (wireframe/shaded)"""
        if self.renderer:
            mode = self.renderer.toggle_render_mode()
            self.update()
            return mode
        return "unknown"
    
    # ==================== Kamera Kontrolleri ====================
    
    def reset_camera(self):
        """Kamerayı sıfırla"""
        self.cam.reset()
        self.update()
        self.status_message.emit("Camera reset")
    
    def focus_model(self):
        """Modeli merkeze al"""
        if self.renderer:
            self.renderer._update_bounds_from_nodes()
            center, size = self.renderer.get_bounds()
            self.cam.update_bounds(center, size)
            self.cam.focus_on_model()
            self.update()
            self.status_message.emit("Model focused")
    
    def toggle_projection(self) -> str:
        """Projeksiyon modunu değiştir"""
        mode = self.cam.toggle_projection()
        self.update()
        self.status_message.emit(f"Projection: {mode}")
        return mode
    
    # ==================== Hover Mekanizması ====================
    
    def _clear_hover(self):
        """Hover durumunu temizle"""
        self._hover_id = 0
        self._hover_element_type = None
        if self.snap:
            self.snap.set_hover_type(-1, None)
        self.input.mouse_world_valid = False
    
    def _update_hover(self, pick_id: int):
        """Hover durumunu güncelle"""
        if pick_id == self._hover_id:
            return
        
        self._hover_id = pick_id
        
        if pick_id > 0 and self.renderer:
            element = self.renderer.get_element_from_id(pick_id)
            if element is None:
                self._clear_hover()
                return
            
            element_type = self._get_element_type(element)
            priority = self._get_priority(element_type)
            
            if self.snap:
                self.snap.set_hover_type(priority, element_type)
            self._hover_element_type = element_type
            
            # Node için world pos güncelle
            if element_type == 'node' and hasattr(element, 'x'):
                self.input.mouse_world_pos = glm.vec3(element.x, element.y, element.z)
                self.input.mouse_world_valid = True
            
            # Hover değişti sinyali
            self.hover_changed.emit(element)
        else:
            self._clear_hover()
            self.hover_changed.emit(None)
    
    def _get_element_type(self, element: Element) -> Optional[str]:
        """Element'ten tipini bul"""
        if element is None:
            return None
        
        if hasattr(element, 'element_type'):
            return element.element_type
        
        class_name = element.__class__.__name__.lower()
        type_map = {
            'node': 'node',
            'frame': 'frame',
            'area': 'area',
            'link': 'link'
        }
        return type_map.get(class_name)
    
    def _get_priority(self, element_type: Optional[str]) -> int:
        """Element tipine göre priority"""
        if not element_type:
            return -1
        
        priority_map = {
            'node': 2,
            'frame': 1,
            'area': 0,
            'link': 0,
        }
        return priority_map.get(element_type.lower(), -1)
    
    # ==================== Picking ====================
    
    def _start_hover_pick(self, x: int, y: int):
        """Mouse move sırasında hover pick başlat"""
        if not self.renderer or not self.renderer.pick_pass or not self._hover_enabled:
            return
        
        # Viewport kontrolü
        if x < 0 or x >= self._width or y < 0 or y >= self._height:
            if self._hover_id != 0:
                self._clear_hover()
            return
        
        # Throttle
        current_time = time.time()
        if (current_time - self._last_hover_time) < self._hover_throttle:
            return
        
        if x == self._last_hover_x and y == self._last_hover_y:
            return
        
        # Async pick başlat
        success = self.renderer.pick_async(x, y)
        if success:
            self._last_hover_x = x
            self._last_hover_y = y
            self._last_hover_time = current_time
            self._pending_pick_check = True
    
    def _check_pick_result(self):
        """Pick sonucunu kontrol et"""
        if not self._pending_pick_check:
            return False
        
        try:
            pick_id, pick_x, pick_y = self.renderer.check_pick()
            if pick_id is not None:
                self._pending_pick_check = False
                self._update_hover(pick_id)
                return True
        except Exception as e:
            logger.error(f"Pick check error: {e}")
            self._pending_pick_check = False
        
        return False
    
    def _handle_select_pick(self, additive: bool):
        """Hover ID'sini kullanarak seçim yap"""
        if self._hover_id > 0 and self.renderer:
            element = self.renderer.get_element_from_id(self._hover_id)
            if element and self.selection_manager:
                self.selection_manager.select(element, additive=additive)
                self.selection_changed.emit(self.selection_manager.get_selected())
    
    def _update_world_pos(self, x: float, y: float):
        """Dünya koordinatını güncelle (ray casting)"""
        if not self.cam or not self.input:
            return
        
        # Hover varsa ve node ise, world pos zaten ayarlanmıştır
        if self._hover_id > 0 and self._hover_element_type == 'node':
            return
        
        # Ray casting
        v = self.cam.get_view_matrix()
        p = self.cam.get_projection_matrix()
        
        nx = 2 * x / self._width - 1
        ny = 1 - 2 * y / self._height
        
        inv = glm.inverse(p * v)
        
        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        
        direction = glm.normalize(far - near)
        
        if abs(direction.z) > 1e-6:
            t = -near.z / direction.z
            if t > 0:
                self.input.mouse_world_pos = near + direction * t
                self.input.mouse_world_valid = True
                return
        
        self.input.mouse_world_valid = False
    
    # ==================== Mouse Event'leri ====================
    
    def mousePressEvent(self, event: QMouseEvent):
        """Mouse basma"""
        x, y = event.position().x(), event.position().y()
        
        # InputManager güncelle
        button_map = {
            Qt.LeftButton: 0,
            Qt.MiddleButton: 2,
            Qt.RightButton: 1,
        }
        button = button_map.get(event.button(), -1)
        if button != -1:
            self.input.set_button_state(button, True)
        
        # Mod bazlı işlemler
        if event.button() == Qt.LeftButton:
            if self._interaction_mode == InteractionMode.SELECT:
                self._last_mouse_pos = glm.vec2(x, y)
                if self.marquee_selector:
                    self.marquee_selector.start_selection(x, y)
        
        elif event.button() == Qt.MiddleButton:
            self._is_dragging = True
            self._last_mouse_pos = glm.vec2(x, y)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Mouse hareket"""
        x, y = event.position().x(), event.position().y()
        
        # InputManager güncelle
        self.input.update_mouse_position(x, y)
        
        # Mod bazlı işlemler
        if self._interaction_mode == InteractionMode.SELECT:
            # Marquee aktif mi?
            if self.marquee_selector and self.marquee_selector.is_active:
                self.marquee_selector.update_selection(x, y)
                return
            
            # Orta tuş ile kamera kontrolü
            if event.buttons() & Qt.MiddleButton and self._last_mouse_pos:
                dx = x - self._last_mouse_pos.x
                dy = y - self._last_mouse_pos.y
                
                shift = event.modifiers() & Qt.ShiftModifier
                if shift:
                    self.cam.pan(dx, dy)
                else:
                    self.cam.orbit(dx, dy)
                
                self._last_mouse_pos = glm.vec2(x, y)
                
                # Orbit/pan sırasında hover temizle
                if self._hover_id != 0:
                    self._clear_hover()
                return
        
        # Hover pick (tüm modlarda çalışır)
        self._update_world_pos(x, y)
        self._start_hover_pick(int(x), int(y))
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mouse bırakma"""
        x, y = event.position().x(), event.position().y()
        
        # InputManager güncelle
        button_map = {
            Qt.LeftButton: 0,
            Qt.MiddleButton: 2,
            Qt.RightButton: 1,
        }
        button = button_map.get(event.button(), -1)
        if button != -1:
            self.input.set_button_state(button, False)
        
        # Mod bazlı işlemler
        if event.button() == Qt.LeftButton:
            if self._interaction_mode == InteractionMode.SELECT:
                if self.marquee_selector and self.marquee_selector.is_active:
                    was_drag = self.marquee_selector.end_selection()
                    if not was_drag:
                        # Tıklama - seçim yap
                        ctrl = bool(event.modifiers() & Qt.ControlModifier)
                        self._handle_select_pick(ctrl)
                else:
                    # Seçim yap (marquee başlatılmamışsa)
                    ctrl = bool(event.modifiers() & Qt.ControlModifier)
                    self._handle_select_pick(ctrl)
            
            self._last_mouse_pos = None
        
        elif event.button() == Qt.MiddleButton:
            self._is_dragging = False
            self._last_mouse_pos = None
    
    def wheelEvent(self, event: QWheelEvent):
        """Mouse tekerlek"""
        delta = event.angleDelta().y() / 120.0
        self.cam.zoom(delta)
        self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Klavye tuşları"""
        key = event.key()
        modifiers = event.modifiers()
        
        # Ctrl + tuş kombinasyonları
        if modifiers & Qt.ControlModifier:
            if key == Qt.Key_R:
                self.reset_camera()
            elif key == Qt.Key_F:
                self.focus_model()
            elif key == Qt.Key_P:
                self.toggle_projection()
            elif key == Qt.Key_Escape:
                self.clear_selection()
        else:
            # Normal tuşlar
            if key == Qt.Key_R:
                self.reset_camera()
            elif key == Qt.Key_F:
                self.focus_model()
            elif key == Qt.Key_P:
                self.toggle_projection()
            elif key == Qt.Key_Escape:
                self.clear_selection()
            elif key == Qt.Key_W:
                self.toggle_render_mode()
    
    # ==================== Seçim Yönetimi ====================
    
    def clear_selection(self):
        """Seçimi temizle"""
        if self.selection_manager:
            self.selection_manager.clear()
            self.selection_changed.emit([])
            self.status_message.emit("Selection cleared")
    
    def select_element(self, element: Element, additive: bool = False):
        """Eleman seç"""
        if self.selection_manager:
            self.selection_manager.select(element, additive=additive)
            self.selection_changed.emit(self.selection_manager.get_selected())
    
    # ==================== Temizlik ====================
    
    def cleanup(self):
        """Kaynakları temizle"""
        if self.renderer:
            self.renderer.cleanup()
        self._timer.stop()
        logger.info("RenderEngineWidget cleaned up")
    
    def closeEvent(self, event):
        """Pencere kapatıldığında"""
        self.cleanup()
        super().closeEvent(event)