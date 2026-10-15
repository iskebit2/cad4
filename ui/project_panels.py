# ui/project_panels.py
"""
Projenin diğer temel bileşenleri (Info, Config, Analysis, Report) için BasePanel tabanlı paneller.
"""
import imgui
from ui.base_panel import BasePanel

class ReportPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Rapor", width=460, height=520, pos_first_use=(500, 150))
        self.log = "Report"

    def open(self, rep=None):
        super().open()
        self.log = rep
    

class ProjectInfoPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Proje Bilgileri", width=460, height=520, pos_first_use=(500, 150))
        self.info = None            # ProjectInfo (name, description, author)
        self.general_info = None    # GeneralProjectInfo
        self.site_info = None       # SiteInformation
        self.on_apply = None
        self._bufs = {}             # input buffer'ları

    def open(self, info=None, general_info=None, site_info=None, on_apply=None):
        super().open()
        self.info = info
        self.general_info = general_info
        self.site_info = site_info
        self.on_apply = on_apply
        self._bufs.clear()

    def draw_content(self):
        # --- Genel Proje Bilgileri ---
        imgui.text_colored("Genel", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.general_info:
            self._field("Firma", "company_name", self.general_info)
            self._field("Müşteri", "client_name", self.general_info)
            self._field("Proje Adı", "project_name", self.general_info)
            self._field("Proje No", "project_number", self.general_info)
            self._field("Model Adı", "model_name", self.general_info)
            self._field("Revizyon", "revision_number", self.general_info)
            self._field("Mühendis", "engineer", self.general_info)
            self._field("Kontrol", "checker", self.general_info)
            self._field("Şef", "supervisor", self.general_info)

        imgui.spacing()
        # --- Saha Bilgileri ---
        imgui.text_colored("Saha", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.site_info:
            self._field("Zemin Sınıfı", "soil_class", self.site_info)
            self._field_float("Yatak Katsayısı", "subgrade_modulus_kn_m3", self.site_info)
            self._field_float("Hareketli Yük Kat.", "live_load_factor", self.site_info)
            self._field("Kadastro", "cadastral_info", self.site_info)
            self._field("Tarih", "date", self.site_info)

        imgui.spacing()
        # --- Metadata ---
        imgui.text_colored("Metadata", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.info:
            self._field("Proje Adı (Kısa)", "name", self.info)
            self._field("Yazar", "author", self.info)
            self._field("Açıklama", "description", self.info)

        # --- Apply butonu ---
        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            if callable(self.on_apply):
                self.on_apply(self.info, self.general_info, self.site_info)

    def _field(self, label, attr, obj):
        val = getattr(obj, attr, "") or ""
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        new_val = imgui.input_text(f"##{attr}", str(val), 256)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _field_float(self, label, attr, obj):
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##{attr}", val)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

class ProjectConfigPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Proje Yapılandırması", width=420, height=520, pos_first_use=(520, 180))
        self.config = None
        self.on_apply = None

    def open(self, config=None, on_apply=None):
        super().open()
        self.config = config
        self.on_apply = on_apply

    def draw_content(self):
        if not self.config:
            imgui.text_colored("Config yok", 0.5, 0.5, 0.5, 1.0)
            return

        # --- Rüzgar ---
        if imgui.collapsing_header("Rüzgar (TS EN 1991-1-4)", True)[0]:
            w = self.config.wind
            self._float("vb0 (m/s)", w, "vb0")
            self._combo("Arazi Kat.", w, "terrain_category", ["I","II","III","IV"])
            self._float("z0", w, "z0")
            self._float("z1", w, "z1")
            self._float("z2", w, "z2")
            self._float("cpi+", w, "cpi_positive")
            self._float("cpi-", w, "cpi_negative")

        # --- Kar ---
        if imgui.collapsing_header("Kar (TS EN 1991-1-3)", True)[0]:
            s = self.config.snow
            self._float("sk (kN/m²)", s, "sk")
            self._float("Ce", s, "exposure_coefficient")
            self._float("Ct", s, "thermal_coefficient")
            self._float("μ", s, "shape_coefficient")

        # --- Deprem ---
        if imgui.collapsing_header("Deprem (TBDY 2018)", True)[0]:
            e = self.config.seismic
            self._float("Ss", e, "ss")
            self._float("S1", e, "s1")
            self._combo("Zemin", e, "soil_class", ["ZA","ZB","ZC","ZD","ZE","ZF"])
            self._float("Önem (I)", e, "importance_factor")
            self._float("R", e, "behavior_factor")
            self._float("D", e, "overstrength_factor")

        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            if callable(self.on_apply):
                self.on_apply(self.config)

    def _float(self, label, obj, attr, step=0.1):
        val = float(getattr(obj, attr, 0.0))
        imgui.text(label); imgui.same_line(180)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##{attr}", val, step=step)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _combo(self, label, obj, attr, choices):
        cur = str(getattr(obj, attr, ""))
        idx = choices.index(cur) if cur in choices else 0
        imgui.text(label); imgui.same_line(180)
        imgui.push_item_width(-1)
        new_idx = imgui.combo(f"##{attr}", idx, choices)[1]
        imgui.pop_item_width()
        if choices[new_idx] != cur:
            setattr(obj, attr, choices[new_idx])

class AnalysisManagerPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Analiz Sonuçları", width=460, height=520, pos_first_use=(550, 200))
        self.analysis = None
        self._open_dirs = set()

    def open(self, analysis=None):
        super().open()
        self.analysis = analysis

    def draw_content(self):
        if not self.analysis:
            imgui.text_colored("Analiz yok", 0.5, 0.5, 0.5, 1.0)
            return

        # --- Rüzgar ---
        wind = getattr(self.analysis, "wind", None)
        if wind:
            imgui.text_colored("Rüzgar Analizi", 0.5, 0.8, 1.0, 1.0)
            imgui.separator()

            directions = getattr(wind, "directions", {})
            if not directions:
                imgui.text_colored("  Henüz analiz yapılmadı", 0.7, 0.7, 0.7, 1.0)
            else:
                imgui.text(f"Yön sayısı: {len(directions)}")
                for key, d in directions.items():
                    is_open = key in self._open_dirs
                    arrow = "▼" if is_open else "▶"
                    if imgui.selectable(f"{arrow} {key}", False)[0]:
                        if is_open:
                            self._open_dirs.discard(key)
                        else:
                            self._open_dirs.add(key)
                    if is_open:
                        imgui.indent(20)
                        imgui.text(f"w_dir: {d.w_dir}")
                        imgui.text(f"q_p:   {d.q_p:.4f}")
                        imgui.text(f"q_b:   {d.q_b:.4f}")
                        imgui.text(f"z_ref: {d.z_ref:.2f}")
                        imgui.text(f"e:     {d.e:.4f}")
                        imgui.text(f"Bölge sayısı: {len(d.zones_data)}")
                        imgui.unindent(20)

        imgui.spacing()
        # --- Deprem ---
        seismic = getattr(self.analysis, "seismic", None)
        imgui.text_colored("Deprem Analizi", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if seismic is None:
            imgui.text_colored("  Henüz yok", 0.7, 0.7, 0.7, 1.0)
        else:
            imgui.text(f"Tip: {type(seismic).__name__}")