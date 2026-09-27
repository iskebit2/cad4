# core/engine.py

from OpenGL.GL import *
import glm
from typing import Optional
from pathlib import Path
import imgui
from imgui.integrations.glfw Renderer
import numpy as np
import threading
import time

from render import shaderprogram
from domain.scene import Scene
from core.camera import Camera
from render.pickpass import PickPass
from render.scenerenderer import SceneRenderer
from render.shaderprogram import ShaderProgram
from tools.gridsystem import GridSystem
from tools.loader import ModelLoader
from tools.snapsquare import SnapSquareRenderer
from ui.inputmanager import InputManager
from ui.uimanager import UIManager
from core.selection_manager import SelectionManager
from core.marquee_selector import MarqueeSelector
from core.selection_policy import SelectionPolicy
import logging
logger = logging.getLogger(__name__)

SHADER_DIR = Path(shaderprogram.__file__).resolve().parent / "shaders"
W, H, TITLE = 1200, 800, "3D CAD"

class RenderEngine:
    def __init__(self):
        self.window = None
        self.w, self.h = W, H
        self.pending_anim = False
        self.load_prog, self.load_done = 100, None
        
        self.cam = self.input = self.imgui = None
        self.pick_s = self.standard_s = self.node_s = self.simple_s = self.overlay_s = None
        self.shaders = {}
        
        self.scene = self.renderer = None
        self.grid = self.snap = None
        self.sel_mgr = self.sel_policy = self.marquee = None
        self.loader = self.ui = None
        self.pick_pass = None
        
        self.hover_id = 0  # Şu an hover edilen element ID'si
        self.hover_element_type = None  # 'node', 'frame', 'area', 'link'
        self.hover_enabled = True
        # Hover throttle için
        self.last_hover_x = -1
        self.last_hover_y = -1
        self.last_hover_time = 0
        self.hover_throttle = 0.033  # 30 FPS (saniyede 30 pick)

        self.pending_pick_check = False  # Pick sonucu bekleniyor mu?
        self.last_pick_x = -1
        self.last_pick_y = -1
    
    def init(self) -> bool:
        if not self._init_glfw(): return False
        self._init_gl()
        self._init_comps()
        self._setup_cbs()
        return True
    
    def _init_glfw(self):
        if not glfw.init(): return False
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 6)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        self.window = glfw.create_window(W, H, TITLE, None, None)
        if not self.window: glfw.terminate(); return False
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        return True
    
    def _init_gl(self):
        shader_list = ["pick", "standard", "node", "simple", "2d_overlay"]
        loaded_count = 0
        
        for name in shader_list:
            v, f = SHADER_DIR/f"{name}.vert", SHADER_DIR/f"{name}.frag"
            logger.debug(f"v= {v}, f={f}")
            try:
                self.shaders[name] = ShaderProgram(name, str(v), str(f))
                loaded_count += 1
                logger.debug(f"✓ {name} shader yüklendi")
            except Exception as e:
                logger.debug(f"✗ {name} shader yüklenemedi: {e}")
                self.shaders[name] = None
        
        self.pick_s = self.shaders.get("pick")
        self.standard_s = self.shaders.get("standard")
        self.node_s = self.shaders.get("node")
        self.simple_s = self.shaders.get("simple")
        self.overlay_s = self.shaders.get("2d_overlay")
        
        # KONTROL: Tüm shader'lar yüklendi mi?
        missing = [name for name, s in [("pick", self.pick_s), ("standard", self.standard_s), 
                                        ("node", self.node_s), ("simple", self.simple_s),
                                        ("2d_overlay", self.overlay_s)] if s is None]
        if missing:
            logger.debug(f"⚠️ UYARI: Şu shader'lar yüklenemedi: {missing}")
        else:
            logger.debug(f"✅ Tüm shader'lar başarıyla yüklendi ({loaded_count}/{len(shader_list)})")
    
    def _init_comps(self):
        imgui.create_context()
        self.imgui = GlfwRenderer(self.window)
        
        self.cam = Camera()
        self.cam.set_aspect(self.w, self.h)
        self.cam.pitch, self.cam.yaw, self.cam.dist = 30.0, -45.0, 50.0
        self.cam._update_position()
        
        
        self.scene = Scene()
        self.input = InputManager()
        self.sel_policy = SelectionPolicy(self.input)
        self.grid = GridSystem(self.simple_s)  # simple shader
        self.snap = SnapSquareRenderer()
        
        if None in [self.pick_s, self.standard_s, self.node_s, self.simple_s, self.overlay_s]:
            missing = []
            if self.pick_s is None: missing.append("pick")
            if self.standard_s is None: missing.append("standard")
            if self.node_s is None: missing.append("node")
            if self.simple_s is None: missing.append("simple")
            if self.overlay_s is None: missing.append("2d_overlay")
            raise RuntimeError(f"Kritik shader'lar yüklenemedi: {missing}")
        
        self.renderer = SceneRenderer(
            pick_s=self.pick_s,
            standard_s=self.standard_s,
            node_s=self.node_s,
            simple_s=self.simple_s,
            overlay_s=self.overlay_s,
            w=self.w, h=self.h
        )
        self.renderer.set_cam(self.cam)
        self.renderer.set_grid(self.grid)
        self.renderer.set_snap(self.snap)
        self.renderer.set_engine(self)
        
        self.pick_pass = self.renderer.pick_pass
        
        self.sel_mgr = SelectionManager(self.renderer)
        self.marquee = MarqueeSelector(self, self.sel_mgr, self.sel_policy)
        self.renderer.set_marquee(self.marquee)
        
        self.loader = ModelLoader(self)
        self.ui = UIManager(self.window, self, self.imgui, self.sel_mgr, self.scene.def_mgr)
    
    def _setup_cbs(self):
        for cb in ["cursor_pos","mouse_button","scroll","key","window_size"]:
            getattr(glfw, f"set_{cb}_callback")(self.window, getattr(self, f"_{cb}_cb"))
    
    def _scroll_cb(self, w, xo, yo): self.cam.zoom(yo)
    
    def _handle_hover(self, x, y):
        """
        Mouse pozisyonundaki elementi tespit et ve snap square tipini güncelle
        """
        if not self.hover_enabled:
            return
            
        if not self.cam or not self.renderer or not self.renderer.pick_pass:
            return
        
        # Viewport dışında mı?
        if x < 0 or x >= self.w or y < 0 or y >= self.h:
            if self.hover_id != 0:
                self.hover_id = 0
                self.hover_element_type = None
                self.snap.set_hover_type(None)  # Snap square'i güncelle
            return
        
        # Kamera matrislerini al
        view = self.cam.get_view_matrix()
        projection = self.cam.get_projection_matrix()
        mvp = projection * view * self.renderer.model_mat
        
        # Picking pass ile ID'yi oku
        try:
            pid = self.renderer.pick_pass.pick(x, y, mvp, self.renderer._render_pick)
        except Exception as e:
            logger.error(f"Hover picking hatası: {e}")
            return
        
        # Hover ID değişti mi?
        if pid != self.hover_id:
            self.hover_id = pid
            self.hover_element_type = self._get_element_type_from_id(pid)
            
            # Snap square'i güncelle - element tipine göre priority değeri
            priority = self._get_priority_from_type(self.hover_element_type)
            self.snap.set_hover_type(priority, self.hover_element_type)
            
            # Debug log
            if pid > 0:
                element = self.renderer.pick_pass.get(pid)
                if element:
                    pass
                    # logger.debug(f"Hover: {element.label if hasattr(element, 'label') else 'Element'} (Tip: {self.hover_element_type}, Priority: {priority})")
            else:
                pass
                # logger.debug("Hover: boş")
    
    def _get_element_type_from_id(self, pid):
        """Pick ID'den element tipini bul"""
        if pid <= 0:
            return None
        
        element = self.renderer.pick_pass.get(pid)
        if not element:
            return None
        
        # Element'in tipini belirle
        if hasattr(element, 'element_type'):  # Eğer element_type attribute'u varsa
            return element.element_type
        
        # Class ismine göre belirle
        class_name = element.__class__.__name__.lower()
        if 'node' in class_name:
            return 'node'
        elif 'frame' in class_name:
            return 'frame'
        elif 'area' in class_name:
            return 'area'
        elif 'link' in class_name:
            return 'link'
        
        return None
    
    def _get_priority_from_type(self, element_type):
        """
        Element tipine göre snap square priority değerini döndür
        """
        if element_type is None or not isinstance(element_type, str):
            return -1
        
        priority_map = {
            'node': 2,    # Sarı
            'frame': 1,   # Kırmızı
            'area': 0,    # Mavi
            'link': 0,    # Mavi
        }
        
        priority = priority_map.get(element_type.lower(), -1)
        #logger.debug(f"_get_priority_from_type: {element_type} -> {priority}")
        return priority
    
    def _mouse_button_cb(self, w, b, a, m):
        x, y = glfw.get_cursor_pos(w)
        
        if imgui.get_io().want_capture_mouse:
            self.input.set_button_state(b, a == glfw.PRESS)
            return
        
        self.input.set_button_state(b, a == glfw.PRESS)
        ctrl = m & glfw.MOD_CONTROL
        
        if b == glfw.MOUSE_BUTTON_LEFT:
            if a == glfw.PRESS:
                self.marquee.start_selection(x, y)
                
            elif a == glfw.RELEASE:
                if self.marquee.is_active:
                    was_drag = self.marquee.end_selection()
                    
                    if not was_drag:
                        # Tıklama anında pick sonucunu bekleme
                        # Doğrudan hover_id'yi kullan
                        self._handle_pick_from_hover(ctrl)
    
    def _handle_pick_from_hover(self, ctrl):
        """Hover ID'sini kullanarak seçim yap"""
        if self.hover_id > 0 and self.renderer and self.renderer.pick_pass:
            element = self.renderer.get_element_from_id(self.hover_id)
            if element:
                #logger.debug(f"Seçim: {element.label if hasattr(element, 'label') else '?'} (ID: {self.hover_id})")
                self.sel_mgr.select(element, additive=ctrl)
    
    def enable_hover(self, enabled=True):
        """Hover özelliğini aç/kapa"""
        self.hover_enabled = enabled
        if not enabled and self.hover_id != 0:
            self.hover_id = 0
            self.hover_element_type = None
            self.snap.set_hover_type(-1, None)
        #logger.debug(f"Hover {'açıldı' if enabled else 'kapatıldı'}")
    
    def _key_cb(self, w, k, s, a, m):
        # Önce UI'a sor (Command Line açık mı?)
        if self.ui and self.ui.handle_key(k, a):
            return  # Command Line tuşu işledi, normal işleme yapma
        
        self.input.set_key_state(k, a in (glfw.PRESS, glfw.REPEAT))
        if a==glfw.PRESS:
            if m & glfw.MOD_CONTROL: self._ctrl_cmd(k)
            else: self._normal_cmd(k)
    
    def _window_size_cb(self, w, ww, hh):
        self.w, self.h = ww, hh
        if self.cam: self.cam.set_aspect(ww, hh)
        if self.ui: self.ui.on_window_resize(ww, hh)
        if self.renderer: self.renderer.resize(ww, hh)
        if self.pick_pass: self.pick_pass.set_viewport(ww, hh)
    
    def _ctrl_cmd(self, k):
        cmds = {
            glfw.KEY_I: self.import_s2k,
            glfw.KEY_E: self.import_e2k,
            glfw.KEY_R: lambda: self.cam.reset(),
            glfw.KEY_F: self._focus,
            glfw.KEY_N: self.test_model,
            glfw.KEY_O: self.cam.toggle_projection,
            glfw.KEY_T: lambda: self.renderer.start_anim(),
            glfw.KEY_P: lambda: setattr(self.ui.properties_window, 'visible', 
                                     not self.ui.properties_window.visible)  # Lambda içinde toggle
        }
        if k in cmds: cmds[k]()
    
    def _normal_cmd(self, k):
        if k==glfw.KEY_ESCAPE: self.sel_mgr.clear(); self.renderer.update_sel()
    
    def _focus(self):
        if not self.renderer: return
        self.renderer._update_bounds_from_nodes()
        c,s = self.renderer.get_bounds()
        self.cam.update_bounds(c, s)
        self.cam.focus_on_model()
    
    def _get_element_type_from_element(self, element):
        """Element'ten tipini bul"""
        if element is None:
            return None
        
        if hasattr(element, 'element_type'):
            return element.element_type
        
        class_name = element.__class__.__name__.lower()
        if 'node' in class_name:
            return 'node'
        elif 'frame' in class_name:
            return 'frame'
        elif 'area' in class_name:
            return 'area'
        elif 'link' in class_name:
            return 'link'
        
        return None
        
    def load_model(self, b):
        self.scene = b.scene
        # UIManager'ı güncelle!
        if hasattr(self, 'ui_manager'):
            self.ui_manager.update_def_mgr(self.scene.def_mgr)

        logger.debug(f"Scene def_mgr sections: {list(self.scene.def_mgr.sections.keys())}")
        self.renderer.update_geo(self.scene)
        self._focus()
    
    def test_model(self):
        from geometry.scenebuilder import SceneBuilder
        from tests.test_model import TestModelBuilder
        b = SceneBuilder()
        TestModelBuilder.build(b)
        self.load_model(b)
        
    
    def clear_scene(self):
        self.scene = Scene()
        self.renderer.set_scene(self.scene)
        for r in [self.renderer.frame_r, self.renderer.node_r, self.renderer.area_r, self.renderer.link_r]:
            r.elements = []
        #if self.renderer.pick_pass: self.renderer.pick_pass.clear()
    
    def import_s2k(self, _=None):
        import threading
        self.clear_scene()
        self.load_prog, self.load_done = 0, False
        def load():
            from tools.s2kloader import S2KLoader
            self.load_prog = 20
            self.scene = S2KLoader().load()
            self.load_prog = 30
            # UIManager'ı güncelle!
            if hasattr(self, 'ui_manager'):
                self.ui_manager.update_def_mgr(self.scene.def_mgr)
            self.load_done = True
        threading.Thread(target=load).start()
        self._focus()

    def import_e2k(self, _=None):
        import threading
        self.clear_scene()
        self.load_prog, self.load_done = 0, False
        def load():
            from tools.e2kloader import E2KLoader
            self.load_prog = 20
            self.scene = E2KLoader().load()
            self.load_prog = 30
            # UIManager'ı güncelle!
            if hasattr(self, 'ui_manager'):
                self.ui_manager.update_def_mgr(self.scene.def_mgr)
            self.load_done = True
        threading.Thread(target=load).start()
        self._focus()
    
    def cleanup(self):
        if self.imgui: self.imgui.shutdown()
        for obj in [self.renderer, self.snap, self.grid] + list(self.shaders.values()):
            if obj and hasattr(obj,'cleanup'): obj.cleanup()
        if self.window: glfw.destroy_window(self.window)
        glfw.terminate()
    
    def _cursor_pos_cb(self, w, x, y):
        self.input.update_mouse_position(x, y)
        
        if self.marquee and self.marquee.is_active:
            self.marquee.update_selection(x, y)
            return
        
        if self.input.buttons.get(glfw.MOUSE_BUTTON_MIDDLE, False):
            shift = self.input.keys.get(glfw.KEY_LEFT_SHIFT, False)
            
            if shift:
                self.cam.orbit(self.input.mouse_delta.x, self.input.mouse_delta.y)
            else:
                self.cam.pan(self.input.mouse_delta.x, self.input.mouse_delta.y)
            
            # Orbit/pan sırasında hover'ı temizle
            if self.hover_id != 0:
                self._clear_hover()
        else:
            # Normal mouse move
            self._update_world_pos(x, y)
            self._start_hover_pick(int(x), int(y))
    
    def _update_hover(self, pick_id):
        """Hover durumunu güncelle - pick_id = 0 gelirse temizle"""
        
        # Aynı ID ise güncelleme (performans için)
        if pick_id == self.hover_id:
            return
        
        self.hover_id = pick_id
        # logger.debug(f"_update_hover: pick_id={pick_id}, old_hover={self.hover_id}")
        
        if pick_id > 0:
            # Element var
            element = self.renderer.get_element_from_id(pick_id)
            if element is None:
                # Element bulunamadıysa temizle
                self._clear_hover()
                return
                
            element_type = self._get_element_type_from_element(element)
            priority = self._get_priority_from_type(element_type)
            
            self.snap.set_hover_type(priority, element_type)
            self.hover_element_type = element_type
            
            if element_type == 'node' and hasattr(element, 'x'):
                self.input.mouse_world_pos = glm.vec3(element.x, element.y, element.z)
                self.input.mouse_world_valid = True
                #logger.debug(f"Node hover: {element.label}")
        else:
            # pick_id = 0 - boşluk
            self._clear_hover()

    def _clear_hover(self):
        """Hover durumunu temizle"""
        self.hover_id = 0
        self.hover_element_type = None
        self.snap.set_hover_type(-1, None)  # Gri
        self.input.mouse_world_valid = False
        #logger.debug("Hover temizlendi (boşluk)")
    
    def _check_pick_result(self):
        """Pick sonucunu kontrol et - pick_id = 0 dahil HER ZAMAN güncelle"""
        if not self.pending_pick_check:
            return False
        
        try:
            pick_id, pick_x, pick_y = self.renderer.check_pick()
            
            if pick_id is not None:  # Sonuç geldi (0 olabilir!)
                self.pending_pick_check = False
                
                # ÖNEMLİ: pick_id = 0 olsa bile güncelle
                # Çünkü boşluktayız ve hover'ı temizlemeliyiz
                self._update_hover(pick_id)
                
                return True
        except Exception as e:
            logger.error(f"Pick kontrolü hatası: {e}")
            self.pending_pick_check = False
        
        return False
    
    def _start_hover_pick(self, x, y):
        """Mouse move sırasında pick başlat - snap square güncellemesi YOK"""
        import time
        success= False
        if not self.renderer or not self.renderer.pick_pass:
            return
        
        current_time = time.time()
        if (current_time - self.last_hover_time) < self.hover_throttle:
            return
        
        if x == self.last_hover_x and y == self.last_hover_y:
            return
        
        success = self.renderer.pick_async(x, y)
        
        if success:
            self.last_hover_x = x
            self.last_hover_y = y
            self.last_hover_time = current_time
            self.pending_pick_check = True
            # Burada snap square GÜNCELLENMEZ
        # logger.debug(f"_start_hover_pick---> succes: {success}")
    
    def _update_world_pos(self, x, y):
        """Dünya koordinatını güncelle - hover yoksa normal ray casting"""
        if not self.cam or not self.input:
            return
        
        # Eğer hover varsa ve node ise, world pos zaten ayarlanmıştır
        if self.hover_id > 0 and self.hover_element_type == 'node':
            return
        
        # Normal ray casting ile düzlem üzerinde pozisyon bul
        v = self.cam.get_view_matrix()
        p = self.cam.get_projection_matrix()
        
        nx = 2 * x / self.w - 1
        ny = 1 - 2 * y / self.h
        
        inv = glm.inverse(p * v)
        
        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        
        direction = glm.normalize(far - near)
        
        # Z=0 düzlemi ile kesişim
        if abs(direction.z) > 1e-6:
            t = -near.z / direction.z
            if t > 0:
                self.input.mouse_world_pos = near + direction * t
                self.input.mouse_world_valid = True
                return
        
        self.input.mouse_world_valid = False
    
    def run(self):
        lt = time.time()
        fc = 0
        
        while not glfw.window_should_close(self.window):
            ct = time.time()
            dt = ct - lt
            lt = ct
            fc += 1
            
            glfw.poll_events()
            
            # Pick sonucunu kontrol et - SADECE BURADA hover güncellenir
            if self.pending_pick_check:
                self._check_pick_result()
            
            # Animasyon ve loading...
            if self.pending_anim:
                self.renderer.start_anim(4)
                self.pending_anim = False
            self.renderer.set_dt(dt)
            
            if self.load_done:
                self.load_prog = 80
                self.renderer.set_scene(self.scene)
                self.renderer.update_geo(self.scene)
                self.load_prog = 90
                c, s = self.renderer.get_bounds()
                self.cam.update_bounds(c, s)
                self.cam.focus_on_model()
                self.renderer._update_grid()
                self.load_prog, self.load_done = 100, False
                self.pending_anim = True
            
            # Render
            glViewport(0, 0, self.w, self.h)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.renderer.render(self.cam)
            
            self.snap.draw(
                    self.window, 
                    self.input.mouse_pos.x, 
                    self.input.mouse_pos.y,
                    self.hover_id,
                    self.hover_element_type  # Yeni parametre
                )
            
            self.ui.render()
            glfw.swap_buffers(self.window)
            
            if fc % 60 == 0:
                fps = 1.0 / dt if dt else 1
                glfw.set_window_title(self.window, f"{TITLE} - FPS: {fps:.1f}")