"""
qt_engine.py - Sağlam OpenGL 3D Viewport Motoru
"""
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False

import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent, QKeyEvent
from OpenGL.GL import *
import glm

from core.camera import Camera
from domain.scene import Scene
from domain.element import Element
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from render import shaderprogram
from tools.gridsystem import GridSystem
from tools.snapsquare import SnapSquareRenderer
from core.selection_manager import SelectionManager
from core.selection_policy import SelectionPolicy
from core.qt_marquee_selector import MarqueeSelector
from ui.inputmanager import InputManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHADER_DIR = Path(shaderprogram.__file__).resolve().parent / "shaders"


class InteractionMode:
    SELECT = "select"
    DRAW_NODE = "draw_node"
    DRAW_BEAM = "draw_beam"
    DRAW_AREA = "draw_area"
    MEASURE = "measure"
    DELETE = "delete"


class RenderEngineWidget(QOpenGLWidget):
    """
    Ana OpenGL Viewport Widget - Sadece 3D Görüntüleme ve Etkileşim Motoru
    """
    selection_changed = Signal(list)
    hover_changed = Signal(object)
    mode_changed = Signal(str)
    status_message = Signal(str)

    def __init__(self, parent=None, scene=None, **kwargs):
        super().__init__(parent)
        self._scene = scene
        
        # Pencere boyutları (DPR düzeltmesi sonrası)
        self._width = 800
        self._height = 600
        
        # Kamera
        self.camera = Camera()
        self.camera.set_aspect(self._width, self._height)
        self.camera.pitch, self.camera.yaw, self.camera.dist = 30.0, -45.0, 50.0
        self.camera._update_position()
        
        # Input
        self.input = InputManager()
        self._mode = InteractionMode.SELECT

        # Shader'lar
        self._shaders: Dict[str, Optional[ShaderProgram]] = {}
        self._shaders_loaded = False
        self._renderer: Optional[SceneRenderer] = None
        self._grid: Optional[GridSystem] = None
        self._snap: Optional[SnapSquareRenderer] = None

        # Selection
        self._selection_manager: Optional[SelectionManager] = None
        self._selection_policy: Optional[SelectionPolicy] = None
        self._marquee: Optional[MarqueeSelector] = None

        # Hover
        self._hover_id: int = 0
        self._hover_element: Optional[Element] = None
        self._hover_enabled: bool = True

        self._last_hover_x: int = -1
        self._last_hover_y: int = -1
        self._last_hover_time: float = 0.0
        self._hover_throttle: float = 0.033

        self._pending_pick: bool = False
        self._last_mouse_pos: Optional[glm.vec2] = None
        self._is_dragging: bool = False

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

        # Mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Hover için ek state'ler (uyumluluk)
        self.hover_id = 0
        self.hover_element_type = None
        self.hover_enabled = True
        self.last_hover_x = -1
        self.last_hover_y = -1
        self.last_hover_time = 0
        self.hover_throttle = 0.033
        self.pending_pick_check = False
        
        self.pick_timer = QTimer(self)
        self.pick_timer.setInterval(16)
        self.pick_timer.timeout.connect(self._check_pick_result)
        
        logger.info("RenderEngineWidget oluşturuldu")

    # ==================== OpenGL Yaşam Döngüsü ====================

    def initializeGL(self):
        """OpenGL başlatma"""
        self.makeCurrent()
        
        # OpenGL ayarları
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.92, 0.92, 0.88, 1.0)
        
        # Shader'ları yükle
        self._load_shaders()
        
        # Bileşenleri oluştur
        self._init_components()
        
        # Scene varsa yükle
        if self._scene is None:
            self._scene = Scene()
        
        self._load_scene(self._scene)
        
        # Render döngüsünü başlat
        self._timer.start(16)
        
        logger.info("OpenGL başlatıldı")

    def _load_shaders(self):
        """Shader'ları yükle"""
        shader_names = ["pick", "standard", "node", "simple", "2d_overlay"]
        loaded = 0
        
        for name in shader_names:
            v = SHADER_DIR / f"{name}.vert"
            f = SHADER_DIR / f"{name}.frag"
            try:
                self._shaders[name] = ShaderProgram(name, str(v), str(f))
                loaded += 1
            except Exception as e:
                logger.error(f"Shader {name} yüklenemedi: {e}")
                self._shaders[name] = None
        
        self._shaders_loaded = True
        logger.info(f"Shader'lar yüklendi: {loaded}/{len(shader_names)}")

    def _init_components(self):
        """Renderer ve bileşenleri oluştur"""
        pick_s = self._shaders.get("pick")
        standard_s = self._shaders.get("standard")
        node_s = self._shaders.get("node")
        simple_s = self._shaders.get("simple")
        overlay_s = self._shaders.get("2d_overlay")
        
        # Grid ve Snap
        self._grid = GridSystem(simple_s)
        self._snap = SnapSquareRenderer()
        
        # Renderer
        self._renderer = SceneRenderer(
            pick_s=pick_s,
            standard_s=standard_s,
            node_s=node_s,
            simple_s=simple_s,
            overlay_s=overlay_s,
            w=self._width,
            h=self._height
        )
        self._renderer.set_cam(self.camera)
        self._renderer.set_grid(self._grid)
        self._renderer.set_snap(self._snap)
        self._renderer.set_engine(self)
        
        # Selection
        self._selection_policy = SelectionPolicy(self.input)
        self._selection_manager = SelectionManager(self._renderer)
        self._marquee = MarqueeSelector(
            self, self._selection_manager, self._selection_policy
        )
        self._renderer.set_marquee(self._marquee)
        
        # Pick timer'ı başlat
        self.pick_timer.start()

    def paintGL(self):
        """OpenGL çizim"""
        # Pick sonucunu kontrol et
        if self.pending_pick_check:
            self._check_pick_result()
        
        # Render
        if self._renderer:
            target_fbo = self.defaultFramebufferObject()
            self._renderer.render(self.camera, target_fbo=target_fbo)
        
        # Snap overlay
        if self._snap and self.input:
            self._snap.draw(
                self,
                self.input.mouse_pos.x,
                self.input.mouse_pos.y,
                self.hover_id,
                self.hover_element_type,
                w=self.width(),
                h=self.height()
            )

    def resizeGL(self, w: int, h: int):
        """Pencere boyut değişikliği"""
        self._width = w
        self._height = h
        
        # DPR düzeltmesi
        dpr = self.devicePixelRatio()
        real_w = int(w * dpr)
        real_h = int(h * dpr)
        
        glViewport(0, 0, real_w, real_h)
        
        self.camera.set_aspect(real_w, real_h)
        if self._renderer:
            self._renderer.resize(real_w, real_h)

    # ==================== Scene Yönetimi ====================

    def set_scene(self, scene: Scene) -> bool:
        """Scene'i ayarla"""
        self._scene = scene
        if self._renderer:
            self.makeCurrent()
            self._load_scene(scene)
            self.doneCurrent()
            self.update()
            return True
        return False

    def _load_scene(self, scene: Scene):
        """Scene'i renderer'a yükle"""
        if not self._renderer:
            return
        
        self._renderer.set_scene(scene)
        self._renderer.update_geo(scene)
        
        # Selection manager'ı güncelle
        self._selection_manager = SelectionManager(self._renderer)
        
        # Bounds hesapla ve kamerayı ayarla
        try:
            center, size = scene.get_bounds()
            self.camera.update_bounds(center, size)
            self.camera.focus_on_model()
        except Exception as e:
            logger.warning(f"Bounds hesaplanamadı: {e}")
            self.camera.reset()
        
        node_count = len(scene.nodes) if hasattr(scene, 'nodes') else 0
        frame_count = len(scene.frames) if hasattr(scene, 'frames') else 0
        self.status_message.emit(f"Scene yüklendi: {node_count} node, {frame_count} frame")

    def get_scene(self) -> Optional[Scene]:
        """Mevcut scene'i döndür"""
        return self._scene

    # ==================== Kamera Kontrolleri ====================

    def reset_camera(self):
        self.camera.reset()
        self.status_message.emit("Kamera sıfırlandı")
        self.update()

    def focus_model(self):
        if self._scene:
            try:
                center, size = self._scene.get_bounds()
                self.camera.update_bounds(center, size)
                self.camera.focus_on_model()
                self.status_message.emit("Model ortalandı")
                self.update()
            except Exception as e:
                logger.warning(f"Focus hatası: {e}")

    def toggle_projection(self) -> str:
        mode = self.camera.toggle_projection()
        self.status_message.emit(f"Projeksiyon: {mode}")
        self.update()
        return mode

    def toggle_render_mode(self) -> str:
        if self._renderer and hasattr(self._renderer, 'toggle_render_mode'):
            mode = self._renderer.toggle_render_mode()
            self.status_message.emit(f"Render modu: {mode}")
            self.update()
            return mode
        return "unknown"

    # ==================== Mod Yönetimi ====================

    def set_mode(self, mode: str):
        """Etkileşim modunu değiştir"""
        if self._mode != mode:
            self._mode = mode
            self.mode_changed.emit(mode)
            self.status_message.emit(f"Mod: {mode}")

    def get_mode(self) -> str:
        return self._mode

    # ==================== Selection ====================

    def clear_selection(self):
        if self._selection_manager:
            self._selection_manager.clear()
            self.selection_changed.emit([])
            self.status_message.emit("Seçim temizlendi")

    def get_selected_elements(self) -> List[Element]:
        if self._selection_manager:
            return self._selection_manager.get_selected()
        return []

    # ==================== Görünürlük ====================

    def toggle_visibility(self, element_type: str) -> bool:
        if self._renderer and element_type in self._renderer.show:
            self._renderer.show[element_type] = not self._renderer.show[element_type]
            self.update()
            return self._renderer.show[element_type]
        return False

    # ==================== Hover ve Picking ====================

    def _start_hover_pick(self, x: int, y: int):
        """Hover pick başlat"""
        if not self.hover_enabled or not self._renderer or not self._renderer.pick_pass:
            return

        curr_time = time.time()
        if (curr_time - self.last_hover_time) < self.hover_throttle:
            return

        if x == self.last_hover_x and y == self.last_hover_y:
            return

        success = self._renderer.pick_async(x, y)
        if success:
            self.last_hover_x = x
            self.last_hover_y = y
            self.last_hover_time = curr_time
            self.pending_pick_check = True

    def _check_pick_result(self):
        """Pick sonucunu kontrol et (timer ile)"""
        if not self.pending_pick_check:
            return

        try:
            pick_id, _, _ = self._renderer.check_pick()
            if pick_id is not None:
                self.pending_pick_check = False
                self._update_hover(pick_id)
                self.update()
        except Exception as e:
            logger.error(f"Pick hatası: {e}")
            self.pending_pick_check = False

    def _update_hover(self, pick_id: int):
        """Hover durumunu güncelle"""
        if pick_id == self.hover_id:
            return

        self.hover_id = pick_id
        
        if pick_id > 0 and self._renderer:
            element = self._renderer.get_element_from_id(pick_id)
            if element is None:
                self._clear_hover()
                return

            self._hover_element = element
            element_type = self._get_element_type(element)
            priority = self._get_priority(element_type)

            if self._snap:
                self._snap.set_hover_type(priority, element_type)
            self.hover_element_type = element_type

            if element_type == 'node' and hasattr(element, 'x'):
                self.input.mouse_world_pos = glm.vec3(element.x, element.y, element.z)
                self.input.mouse_world_valid = True

            self.hover_changed.emit(element)
        else:
            self._clear_hover()

    def _clear_hover(self):
        """Hover durumunu temizle"""
        self.hover_id = 0
        self.hover_element_type = None
        self._hover_element = None
        if self._snap:
            self._snap.set_hover_type(-1, None)
        self.input.mouse_world_valid = False
        self.hover_changed.emit(None)

    def _handle_pick_from_hover(self, ctrl: bool):
        """Hover'daki elementi seç"""
        if self.hover_id > 0 and self._renderer:
            element = self._renderer.get_element_from_id(self.hover_id)
            if element and self._selection_manager:
                self._selection_manager.select(element, additive=ctrl)
                self.selection_changed.emit(self._selection_manager.get_selected())

    def _get_element_type(self, element: Element) -> Optional[str]:
        """Element tipini bul"""
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

    def _update_world_pos(self, x: float, y: float):
        """Dünya koordinatını güncelle"""
        if not self.camera or not self.input:
            return
        
        # Hover varsa ve node ise world pos zaten ayarlanmıştır
        if self.hover_id > 0 and self.hover_element_type == 'node':
            return
        
        # Ray casting
        v = self.camera.get_view_matrix()
        p = self.camera.get_projection_matrix()
        
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

    def mouseMoveEvent(self, event: QMouseEvent):
        """Mouse hareket"""
        pos = event.position()
        x = pos.x()
        y = pos.y()

        self.input.update_mouse_position(x, y)

        # Orta tuş ile kamera kontrolü
        if event.buttons() & Qt.MiddleButton:
            dx = self.input.mouse_delta.x
            dy = self.input.mouse_delta.y
            
            if event.modifiers() & Qt.ShiftModifier:
                self.camera.pan(dx, dy)
            else:
                self.camera.orbit(dx, dy)
            
            self._clear_hover()
            self.update()
        else:
            # Normal hareket - hover pick
            self._update_world_pos(x, y)
            self._start_hover_pick(int(x), int(y))
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        """Mouse basma"""
        if event.button() == Qt.LeftButton:
            pos = event.position()
            x = pos.x()
            y = pos.y()
            
            if self._marquee:
                self._marquee.start_selection(x, y)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mouse bırakma"""
        if event.button() == Qt.LeftButton:
            if self._marquee and self._marquee.is_active:
                was_drag = self._marquee.end_selection()
                if not was_drag:
                    ctrl = bool(event.modifiers() & Qt.ControlModifier)
                    self._handle_pick_from_hover(ctrl)
            self.update()

    def wheelEvent(self, event: QWheelEvent):
        """Mouse tekerlek"""
        delta = event.angleDelta().y() / 120.0
        self.camera.zoom(delta)
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        """Klavye tuşları"""
        key = event.key()
        
        if key == Qt.Key_R:
            self.reset_camera()
        elif key == Qt.Key_F:
            self.focus_model()
        elif key == Qt.Key_P:
            self.toggle_projection()
        elif key == Qt.Key_W:
            self.toggle_render_mode()
        elif key == Qt.Key_Escape:
            self.clear_selection()

    # ==================== Temizlik ====================

    def cleanup(self):
        """Kaynakları temizle"""
        self._timer.stop()
        self.pick_timer.stop()
        if self._renderer and hasattr(self._renderer, 'cleanup'):
            self._renderer.cleanup()
        logger.info("RenderEngineWidget temizlendi")

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)