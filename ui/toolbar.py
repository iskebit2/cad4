"""
ImGui Toolbar — PyImGui Uyumlu İkon Destekli Üst Şerit.
"""
import base64
from io import BytesIO
from typing import Callable, Dict
from PIL import Image
import OpenGL.GL as gl
import imgui

from data.enums import UnitSystem
from assets.icons_base64 import ICON_DATA


class IconManager:
    """Base64 PNG verilerini OpenGL dokusuna çevirir ve önbellekler."""
    def __init__(self):
        self._textures = {}

    def get_texture(self, icon_name: str):
        if icon_name in self._textures:
            return self._textures[icon_name]

        if icon_name not in ICON_DATA:
            return None

        # Base64 çöz ve PIL Image yap
        img_data = base64.b64decode(ICON_DATA[icon_name])
        img = Image.open(BytesIO(img_data)).convert('RGBA')
        width, height = img.size
        raw_data = img.tobytes("raw", "RGBA")

        # OpenGL dokusu oluştur
        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
            0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_data
        )
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

        self._textures[icon_name] = (tex_id, width, height)
        return self._textures[icon_name]


class Toolbar:
    HEIGHT = 32.0

    def __init__(self, commands: Dict[str, Callable], panel_states: Dict[str, Callable] = None):
        self.commands = commands or {}
        self.panel_states = panel_states or {}
        self.current_unit = None
        self.icon_mgr = IconManager()

    def draw(self, model_text: str = "MODEL: YENİ SAHNE", draw_active: bool = False, current_unit=None):
        self.current_unit = current_unit
        
        # PyImGui ana menü / üst şerit yapısı
        if imgui.begin_main_menu_bar():
            self._draw_content(model_text, draw_active)
            imgui.end_main_menu_bar()

    def _draw_content(self, model_text: str, draw_active: bool):
        # --- 1. Dosya (File) Menüsü ---
        if imgui.begin_menu("Dosya"):
            if imgui.menu_item("Yeni (Ctrl+N)")[0]:
                self._fire("new_project")
            if imgui.menu_item("Aç (Ctrl+O)")[0]:
                self._fire("open")
            if imgui.menu_item("Kaydet (Ctrl+S)")[0]:
                self._fire("save")
            if imgui.menu_item("Farklı Kaydet (Shift+Ctrl+S)")[0]:
                self._fire("save_as")
            
            imgui.separator()
            if imgui.menu_item("İçe Aktar (S2K Import - F11)")[0]:
                self._fire("s2k_import")
            if imgui.menu_item("Dışa Aktar (Export)...", enabled=False)[0]:
                self._fire("export")
            
            imgui.separator()
            if imgui.menu_item("Çıkış")[0]:
                self._fire("close_app")
            imgui.end_menu()

        imgui.separator()

        # --- Hızlı Dosya İkon Butonları ---
        if self._icon_button("btn_tb_new", "file-plus", size=(16, 16), tooltip="Yeni Proje (Ctrl+N)"):
            self._fire("new_project")

        if self._icon_button("btn_tb_open", "folder", size=(16, 16), tooltip="Aç (Ctrl+O)"):
            self._fire("open")

        if self._icon_button("btn_tb_save", "save", size=(16, 16), tooltip="Kaydet (Ctrl+S)"):
            self._fire("save")

        imgui.separator()

        # --- 2. Çizim Modları ---
        poly_color = (0.20, 0.60, 0.35, 1.00) if draw_active else (0.22, 0.28, 0.38, 1.00)
        self._styled_icon_button("btn_draw_poly", "edit", "Poly (D)", poly_color, lambda: self._fire("draw"))

        pdm_active = self._get_panel_state("plane_draw_active")
        plane_color = (0.80, 0.45, 0.15, 1.00) if pdm_active else (0.28, 0.28, 0.38, 1.00)
        self._styled_icon_button("btn_draw_plane", "grid", "Plane Çiz (Shift+W)", plane_color, lambda: self._fire("plane_draw"))

        imgui.separator()

        # --- 3. Atama & Yükler Menüsü ---
        if imgui.begin_menu("Atama & Yükler"):
            if imgui.menu_item("Alan Yükü Atama (Area Load)...", selected=self._get_panel_state("assign_area_load"))[0]:
                self._fire("assign_area_load")
            if imgui.menu_item("Çubuk Yayılı Yükü (Frame Load)...", selected=self._get_panel_state("assign_frame_distributed_load"))[0]:
                self._fire("assign_frame_distributed_load")
            imgui.separator()
            if imgui.menu_item("Yük Görüntüleme Paneli", selected=self._get_panel_state("load_display_panel"))[0]:
                self._fire("load_display_panel")
            if imgui.menu_item("Yük Görünürlüğü (L)", selected=self._get_panel_state("show_loads"))[0]:
                self._fire("toggle_loads_vis")
            imgui.end_menu()

        # --- 4. Görünüm & Araçlar Menüsü ---
        if imgui.begin_menu("Görünüm & Araçlar"):
            if imgui.menu_item("Inspector / Özellikler (Ctrl+P)", selected=self._get_panel_state("inspector"))[0]:
                self._fire("inspector")
            if imgui.menu_item("Plane Manager (F12)", selected=self._get_panel_state("plane_manager"))[0]:
                self._fire("plane_manager")
            if imgui.menu_item("Grid Ayarları (Ctrl+G)", selected=self._get_panel_state("grid"))[0]:
                self._fire("grid")
            if imgui.menu_item("Görünüm Filtresi (F6)", selected=self._get_panel_state("view_filter"))[0]:
                self._fire("view_filter")
            if imgui.menu_item("Görünürlük Paneli", selected=self._get_panel_state("visibility"))[0]:
                self._fire("visibility")
            
            imgui.separator()
            if imgui.menu_item("Render Modu Değiştir (F3)")[0]:
                self._fire("render_mode")
            if imgui.menu_item("S2K İçe Aktar (F11)")[0]:
                self._fire("s2k_import")

            imgui.separator()
            axes_on = self._get_panel_state("local_axes")
            if imgui.menu_item("Yerel Eksenleri Göster (Local Axes)", selected=axes_on)[0]:
                self._fire("local_axes")

            imgui.end_menu()

        # --- 5. Yönetim & Tanımlar Menüsü ---
        if imgui.begin_menu("Yönetim"):
            if imgui.menu_item("Tanımlar (Definitions - Ctrl+R)", selected=self._get_panel_state("definitions"))[0]:
                self._fire("definitions")
            if imgui.menu_item("Proje Bilgileri", selected=self._get_panel_state("project_info"))[0]:
                self._fire("project_info")
            if imgui.menu_item("Proje Yapılandırması", selected=self._get_panel_state("project_config"))[0]:
                self._fire("project_config")
            if imgui.menu_item("Analiz Yöneticisi", selected=self._get_panel_state("analysis"))[0]:
                self._fire("analysis")
            if imgui.menu_item("Raporlar", selected=self._get_panel_state("report"))[0]:
                self._fire("report")
            imgui.end_menu()

        # --- 6. Hızlı İkonlu Butonlar ---
        if self._icon_button("btn_tb_settings", "settings", size=(16, 16), tooltip="Ayarlar"):
            self._fire("project_config")

        self._styled_button("Zones", (0.15, 0.45, 0.60, 1.00), lambda: self._fire("wind"))

        # --- Birim Seçici ---
        unit_label = f"Birim: {self.current_unit.name}" if self.current_unit else "Birim: N-mm"
        if imgui.begin_menu(unit_label):
            for unit in UnitSystem:
                is_selected = (self.current_unit == unit)
                if imgui.menu_item(f"{unit.name} ({unit.force_unit}, {unit.length_unit})", selected=is_selected)[0]:
                    self._fire_unit(unit)
            imgui.end_menu()

        # Model İsmi Göstergesi (Sağa yakın hizalama için boşluk bırakılabilir veya doğrudan yazdırılabilir)
        imgui.text_colored(model_text, 0.60, 0.65, 0.72, 1.00)

    def _get_panel_state(self, key: str) -> bool:
        fn = self.panel_states.get(key)
        return bool(fn()) if callable(fn) else False

    def _icon_button(self, str_id: str, icon_name: str, size=(16, 16), tooltip: str = "") -> bool:
        """PyImGui imza uyumlu image_button sarmalayıcısı (uv0 ve uv1 parametreleri eklendi)."""
        tex_info = self.icon_mgr.get_texture(icon_name)
        clicked = False
        if tex_info:
            tex_id, _, _ = tex_info
            # PyImGui image_button fonksiyonu texture_id, width, height, uv0, uv1 alır
            clicked = imgui.image_button(tex_id, size[0], size[1], (0, 0), (1, 1))
        else:
            clicked = imgui.button(str_id)

        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)

        return clicked

    def _styled_icon_button(self, str_id: str, icon_name: str, label: str, base_color, on_click):
        hovered = tuple(min(c + 0.08, 1.0) for c in base_color[:3]) + (1.0,)
        active = tuple(min(c + 0.15, 1.0) for c in base_color[:3]) + (1.0,)

        imgui.push_style_color(imgui.COLOR_BUTTON, *base_color)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hovered)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *active)
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 4.0)

        tex_info = self.icon_mgr.get_texture(icon_name)
        clicked = False
        if tex_info:
            tex_id, _, _ = tex_info
            if imgui.image_button(tex_id, 14, 14, (0, 0), (1, 1)):
                clicked = True
            imgui.same_line(spacing=2)
            if imgui.button(f"{label}##{str_id}"):
                clicked = True
        else:
            clicked = imgui.button(f"{label}##{str_id}")

        imgui.pop_style_var(1)
        imgui.pop_style_color(3)

        if clicked and callable(on_click):
            on_click()

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
        fn = self.commands.get(key)
        if callable(fn):
            fn()

    def _fire_unit(self, unit):
        fn = self.commands.get("on_unit_change")
        if callable(fn):
            fn(unit)