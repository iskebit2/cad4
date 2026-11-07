# ui/project_settings_panel.py
from __future__ import annotations

from imgui_bundle import imgui
from ui.base_panel import BasePanel
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class ProjectSettingsPanel(BasePanel):
    """Sol tarafta ağaç menüsü, sağ tarafta seçilen config/bilgi düzenleyicisi olan merkezi panel."""

    def __init__(self):
        super().__init__(title="Proje Ayarları ve Yapılandırma", width=800, height=600, pos_first_use=(300, 100))
        self.app = None
        self.project = None
        self.scene = None
        self._selected_node = "general_info"  # Varsayılan seçili sekme

    def set_context(self, ctx: dict) -> None:
        self.scene = ctx.get("scene")
        self.project = ctx.get("project")

    def draw_content(self):
        proj = self.project or (self.app.current_project if self.app else None)
        if not proj:
            imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.4, 1.0), "Aktif proje bulunamadı.")
            return

        # Sol Sütun: Ağaç Yapısı (Tree View)
        if imgui.begin_child("settings_tree", imgui.ImVec2(220, 0), True):
            imgui.text_colored(imgui.ImVec4(0.8, 0.9, 1.0, 1.0), "Proje Yapısı")
            imgui.separator()
            imgui.spacing()

            # 1. Kategori: Proje Künyesi
            if imgui.tree_node_ex("Proje Künyesi", imgui.TreeNodeFlags_.default_open):
                if imgui.selectable("Genel Bilgiler", self._selected_node == "general_info")[0]:
                    self._selected_node = "general_info"
                if imgui.selectable("Saha Bilgileri", self._selected_node == "site_info")[0]:
                    self._selected_node = "site_info"
                if imgui.selectable("Metadata", self._selected_node == "info")[0]:
                    self._selected_node = "info"
                imgui.tree_pop()

            imgui.spacing()

            # 2. Kategori: Hesap ve Yük Yapılandırmaları (Config)
            if imgui.tree_node_ex("Yapılandırma (Config)", imgui.TreeNodeFlags_.default_open):
                if imgui.selectable("Rüzgar (TS EN 1991-1-4)", self._selected_node == "config_wind")[0]:
                    self._selected_node = "config_wind"
                if imgui.selectable("Kar (TS EN 1991-1-3)", self._selected_node == "config_snow")[0]:
                    self._selected_node = "config_snow"
                if imgui.selectable("Deprem (TBDY 2018)", self._selected_node == "config_seismic")[0]:
                    self._selected_node = "config_seismic"
                imgui.tree_pop()

            imgui.end_child()

        imgui.same_line()

        # Sağ Sütun: Seçilen Elemanın Form Düzenleyicisi
        if imgui.begin_child("settings_form", imgui.ImVec2(0, 0), True):
            if self._selected_node == "general_info":
                self._draw_general_info_form(proj.general_info)
            elif self._selected_node == "site_info":
                self._draw_site_info_form(proj.site_info)
            elif self._selected_node == "info":
                self._draw_metadata_form(proj.info)
            elif self._selected_node == "config_wind":
                self._draw_wind_config_form(proj.config.wind)
            elif self._selected_node == "config_snow":
                self._draw_snow_config_form(proj.config.snow)
            elif self._selected_node == "config_seismic":
                self._draw_seismic_config_form(proj.config.seismic)

            imgui.end_child()

    def _draw_general_info_form(self, g):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Genel Proje Bilgileri")
        imgui.separator()
        imgui.spacing()
        self._field("Firma", g, "company_name")
        self._field("Müşteri", g, "client_name")
        self._field("Proje Adı", g, "project_name")
        self._field("Proje No", g, "project_number")
        self._field("Model Adı", g, "model_name")
        self._field("Revizyon", g, "revision_number")
        self._field("Mühendis", g, "engineer")
        self._field("Kontrol", g, "checker")
        self._field("Şef", g, "supervisor")

    def _draw_site_info_form(self, s):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Saha Bilgileri")
        imgui.separator()
        imgui.spacing()
        self._field("Zemin Sınıfı", s, "soil_class")
        self._field_float("Yatak Katsayısı (kN/m³)", s, "subgrade_modulus_kn_m3", step=100.0)
        self._field_float("Hareketli Yük Kat.", s, "live_load_factor", step=0.05)
        self._field("Kadastro", s, "cadastral_info")
        self._field("Tarih", s, "date")

    def _draw_metadata_form(self, i):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Proje Metadata Bilgileri")
        imgui.separator()
        imgui.spacing()
        self._field("Proje Adı (Kısa)", i, "name")
        self._field("Yazar", i, "author")
        self._field("Açıklama", i, "description")

    def _draw_wind_config_form(self, w):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Rüzgar Yapılandırması (TS EN 1991-1-4)")
        imgui.separator()
        imgui.spacing()
        self._field_float("Temel Rüzgar Hızı vb0 (m/s)", w, "v_b0", step=1.0)
        self._combo("Arazi Kategorisi", w, "terrain", ["Kategori I", "Kategori II", "Kategori III", "Kategori IV"])
        self._field_float("Hava Yoğunluğu ρ (kg/m³)", w, "rho", step=0.05)
        self._field_float("Ct Katsayısı", w, "ct", step=0.05)
        self._field_float("kI Katsayısı", w, "kI", step=0.05)
        self._field_float("z0 (m)", w, "z0", step=0.01)
        self._field_float("z1 (m)", w, "z1", step=0.1)
        self._field_float("z2 (m)", w, "z2", step=0.1)
        self._field_float("İç Basınç Cpi (+)", w, "cpi_positive", step=0.05)
        self._field_float("İç Basınç Cpi (-)", w, "cpi_negative", step=0.05)

    def _draw_snow_config_form(self, s):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Kar Yükü Yapılandırması (TS EN 1991-1-3)")
        imgui.separator()
        imgui.spacing()
        self._field_float("Çatı Eğimi α (°)", s, "slope", step=1.0)
        self._field_int("Kar Bölgesi (1-9)", s, "snow_region", step=1)
        self._field_float("Rakım (m)", s, "altitude", step=10.0)
        self._field_float("Temel Kar Yükü sk (kN/m²)", s, "sk", step=0.05)
        self._field_float("Maruziyet Katsayısı (Ce)", s, "Ce", step=0.05)
        self._field_float("Isıl Katsayı (Ct)", s, "Ct", step=0.05)
        self._field_float("Şekil Katsayısı (μ)", s, "shape_coefficient", step=0.05)

    def _draw_seismic_config_form(self, e):
        imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), "Deprem Yapılandırması (TBDY 2018)")
        imgui.separator()
        imgui.spacing()
        self._field_float("Davranış Katsayısı (R)", e, "R", step=0.5)
        self._field_float("Dayanım Fazlalığı (D)", e, "D", step=0.5)
        self._field_float("Bina Önem Katsayısı (I)", e, "I", step=0.1)
        self._field_float("Yapı Yüksekliği Hn (m)", e, "Hn", step=0.5)
        self._combo("Zemin Sınıfı", e, "zemin_sinifi", ["ZA", "ZB", "ZC", "ZD", "ZE", "ZF"])
        
        # DD-2 Değerleri
        if hasattr(e, "dd2") and isinstance(e.dd2, dict):
            imgui.spacing()
            imgui.text_colored(imgui.ImVec4(0.9, 0.8, 0.5, 1.0), "DD-2 Deprem Yer Hareketi Düzeyi")
            self._dict_float("DD2 - Ss", e.dd2, "Ss", step=0.01)
            self._dict_float("DD2 - S1", e.dd2, "S1", step=0.01)
            self._dict_float("DD2 - Sds", e.dd2, "Sds", step=0.01)
            self._dict_float("DD2 - Sd1", e.dd2, "Sd1", step=0.01)

    def _field(self, label, obj, attr):
        val = getattr(obj, attr, "") or ""
        imgui.text(label + ":")
        imgui.same_line(220)
        imgui.push_item_width(-1)
        new_val = imgui.input_text(f"##{attr}", str(val), 256)[1]
        imgui.pop_item_width()
        if new_val != str(val):
            setattr(obj, attr, new_val)

    def _field_float(self, label, obj, attr, step=0.1):
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label + ":")
        imgui.same_line(220)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##{attr}", val, step=step, format="%.3f")[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _field_int(self, label, obj, attr, step=1):
        val = int(getattr(obj, attr, 0) or 0)
        imgui.text(label + ":")
        imgui.same_line(220)
        imgui.push_item_width(-1)
        new_val = imgui.input_int(f"##{attr}", val, step=step)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _combo(self, label, obj, attr, choices):
        cur = str(getattr(obj, attr, ""))
        idx = choices.index(cur) if cur in choices else 0
        imgui.text(label + ":")
        imgui.same_line(220)
        imgui.push_item_width(-1)
        new_idx = imgui.combo(f"##{attr}", idx, choices)[1]
        imgui.pop_item_width()
        if choices[new_idx] != cur:
            setattr(obj, attr, choices[new_idx])

    def _dict_float(self, label, d, key, step=0.01):
        val = float(d.get(key, 0.0))
        imgui.text(label + ":")
        imgui.same_line(220)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##dict_{key}", val, step=step, format="%.3f")[1]
        imgui.pop_item_width()
        if new_val != val:
            d[key] = new_val