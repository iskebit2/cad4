# ui/report_panel.py
from __future__ import annotations

from imgui_bundle import imgui
from ui.base_panel import BasePanel
from logging_config import CadLogger

from tools.wind_scene_adapter import WindSceneAdapter
from structload.windcalc.windengine import WindEngine
from structload.windcalc.wind_results import get_parameters_report, create_cpe_summary_df, create_wind_force_df
from structload.windcalc.wind_analyzer import WindAnalyzer
from structload.loads.snow_load import SnowLoad
from structload.loads.spectrum import Spectrum
from structload.utils.meta_tables import parse_project_loads
from domain.definition import get_tsc2018_site_coefficients
import numpy as np

logger = CadLogger.get(__name__)


class ReportPanel(BasePanel):
    def __init__(self, app=None):
        super().__init__(title="Proje Raporları", width=720, height=540, pos_first_use=(450, 120))
        self.app = app
        self.log = "Report"
        self.selected_index = 0
        self.project = None
        self.scene = None

    def set_context(self, ctx: dict) -> None:
        """AppActions üzerinden gelen sahne ve proje bağlamını alır."""
        self.scene = ctx.get("scene")
        self.project = ctx.get("project")

    def open(self, rep=None):
        super().open()
        proj = self.project or (self.app.current_project if self.app else None)
        
        if rep is not None:
            if proj and hasattr(proj, "report"):
                proj.report.add_report(rep)
        
        if proj and hasattr(proj, "report") and not getattr(proj.report, "reports", []):
            self._generate_default_reports(proj)

    def _generate_default_reports(self, project) -> None:
        """Mevcut proje geometrisi ve rüzgar verilerinden WindSceneAdapter kullanarak güvenli şekilde rapor üretir."""
        if not project:
            logger.debug("[ReportPanel] Proje eksik olduğu için otomatik rapor oluşturulamadı.")
            return
        # --- 1. RÜZGAR RAPORLARI ---
        try: 
            # Doğru anahtarlama ve tip uyumu için WindSceneAdapter kullanalım
            points, polygons, wind_config = WindSceneAdapter.build_inputs(project)

            if not points or not polygons:
                logger.debug("[ReportPanel] Projede analiz edilecek düğüm veya poligon bulunamadı.")
                return

            engine = WindEngine(points=points, polygons=polygons)
            
            # 1. Parametre Raporu
            param_rep = get_parameters_report(engine)
            param_rep.custom_title = "Rüzgar Yükü Parametreleri (Genel)"
            project.report.add_report(param_rep)

            # 2. Rüzgar Yönleri Raporları
            w_list = {
                "X+ (Yön 1)": np.array([1.0, 0.0, 0.0]),
                "Y+ (Yön 2)": np.array([0.0, 1.0, 0.0]),
            }
            for w_key, w_dir in w_list.items():
                analyzer = WindAnalyzer(points, polygons, w_dir)
                zones = analyzer.analyze()
                if zones:
                    cpe_rep = create_cpe_summary_df(zones, analyzer.engine)
                    cpe_rep.custom_title = f"Dış Basınç Katsayıları - {w_key}"
                    project.report.add_report(cpe_rep)

                    force_rep = create_wind_force_df(zones, analyzer.engine)
                    force_rep.custom_title = f"Tasarım Rüzgar Yükleri - {w_key}"
                    project.report.add_report(force_rep)

            logger.debug("[ReportPanel] Varsayılan proje raporları başarıyla derlendi.")
        except Exception as e:
            logger.exception(f"[ReportPanel] Rüzgar Raporları oluşturulurken hata oluştu: {e}")


        # --- 2. KAR RAPORU (project.config.snow üzerinden) ---
        try:
            snow_cfg = project.config.snow
            snow_config = {
                "slope": getattr(snow_cfg, "slope", 0.0),
                "snow_region": getattr(snow_cfg, "snow_region", 2),
                "altitude": getattr(snow_cfg, "altitude", 0.0),
                "Ce": getattr(snow_cfg, "exposure_coefficient", 1.0),
                "Ct": getattr(snow_cfg, "thermal_coefficient", 1.0),
            }
            snow_obj = SnowLoad(snow_config)
            project.report.add_report(snow_obj.report())
        except Exception:
            logger.exception("Kar raporu oluşturulamadı")

        # --- 3. ÖLÜ VE HAREKETLİ YÜK RAPORLARI ---
        try:
            pdata = {
                "dead_loads": list(getattr(project.loads, "definitions", {}).keys()) or ["konut_dosemesi"],
                "live_loads": ["konut"],
                "duvarlar": []
            }
            reports_dict = parse_project_loads(pdata)
            for rep in reports_dict.values():
                project.report.add_report(rep)
        except Exception:
            logger.exception("Ölü/Hareketli yük raporları oluşturulamadı")

        # --- 4. DEPREM RAPORU (project.config.seismic üzerinden) ---
        try:
            seismic_cfg = project.config.seismic
            ss = getattr(seismic_cfg, "ss", 0.329)
            s1 = getattr(seismic_cfg, "s1", 0.128)
            soil_class = getattr(seismic_cfg, "soil_class", "ZC")

            fs, f1 = get_tsc2018_site_coefficients(ss, s1, soil_class)
            sds = ss * fs
            sd1 = s1 * f1

            eq_data = {
                "dd2": {"Sds": sds, "Sd1": sd1},
                "dd3": {"Sds": sds * 0.5, "Sd1": sd1 * 0.5},
                "zemin_sinifi": soil_class,
                "Hn": 10.0,
                "structure_type": "concrete_frame"
            }
            eq = Spectrum(eq_data)
            eq.run()

            if eq.table_parameters is not None and not eq.table_parameters.empty:
                project.report.add_report(eq.table_parameters)

            if eq.table_spectrum is not None and not eq.table_spectrum.empty:
                project.report.add_report(eq.table_spectrum)
        except Exception:
            logger.exception("Deprem raporu oluşturulamadı")

        logger.debug("[ReportPanel] Domain nesnelerinden proje raporları başarıyla derlendi.")
    

    def draw_content(self):
        try:
            proj = self.project or (self.app.current_project if self.app else None)
            if not proj or not hasattr(proj, "report"):
                imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.4, 1.0), "Proje veya Rapor Yöneticisi bağlı değil.")
                return

            report_mgr = proj.report
            reports = getattr(report_mgr, "reports", [])

            # Üst Araç Çubuğu
            if imgui.button("🔄 Raporları Yeniden Oluştur"):
                try:
                    report_mgr.clear()
                    self._generate_default_reports(proj)
                    self.selected_index = 0
                except Exception as e:
                    logger.exception(f"[ReportPanel] Yeniden oluşturma hatası: {e}")

            imgui.same_line()
            if imgui.button("🗑 Tüm Raporları Temizle"):
                report_mgr.clear()
                self.selected_index = 0

            imgui.spacing()
            imgui.separator()
            imgui.spacing()

            if not reports:
                imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), "Henüz oluşturulmuş veya eklenmiş bir rapor bulunmuyor.")
                imgui.text_wrapped("Yukarıdaki butona basarak mevcut projeye ait hesap raporlarını derleyebilirsiniz.")
                return

            if self.selected_index >= len(reports):
                self.selected_index = max(0, len(reports) - 1)

            # Sol Sütun: Rapor Listesi
            if imgui.begin_child("report_list_child", imgui.ImVec2(220, 0), True):
                imgui.text_colored(imgui.ImVec4(0.8, 0.9, 1.0, 1.0), "Rapor Kategorileri")
                imgui.separator()
                
                for i, rep in enumerate(reports):
                    title = getattr(rep, "custom_title", f"Rapor {i+1}")
                    is_selected = (self.selected_index == i)
                    if imgui.selectable(f"{title}##{i}", is_selected)[0]:
                        self.selected_index = i
                imgui.end_child()

            imgui.same_line()

            # Sağ Sütun: Seçilen Raporun Detayı ve Tablosu
            if imgui.begin_child("report_detail_child", imgui.ImVec2(0, 0), True):
                if 0 <= self.selected_index < len(reports):
                    rep = reports[self.selected_index]
                    
                    title = getattr(rep, "custom_title", "Rapor Detayı")
                    imgui.text_colored(imgui.ImVec4(0.3, 0.85, 0.95, 1.0), title)
                    imgui.separator()
                    
                    desc = getattr(rep, "custom_desc", "")
                    if desc:
                        imgui.text_wrapped(desc.strip())
                        imgui.spacing()
                        imgui.separator()

                    # rep zaten ReportDataFrame sınıfıdır (pandas.DataFrame)
                    df = rep if not rep.empty else None
                    if df is not None and not df.empty:
                        imgui.text("Veri Tablosu:")
                        cols = list(df.columns)
                        
                        flags = (
                            imgui.TableFlags_.borders
                            | imgui.TableFlags_.row_bg
                            | imgui.TableFlags_.resizable
                            | imgui.TableFlags_.scroll_y
                        )
                        
                        if imgui.begin_table(f"##rep_table_{self.selected_index}", len(cols), flags, imgui.ImVec2(0, 300)):
                            for col in cols:
                                imgui.table_setup_column(str(col))
                            imgui.table_headers_row()

                            for row_idx, row in df.iterrows():
                                imgui.table_next_row()
                                for col_idx, col in enumerate(cols):
                                    imgui.table_set_column_index(col_idx)
                                    val = row[col]
                                    imgui.text(str(val))
                            imgui.end_table()
                    else:
                        imgui.text_colored(imgui.ImVec4(0.8, 0.6, 0.4, 1.0), "Bu raporda gösterilecek tablo verisi bulunmuyor.")
                
                imgui.end_child()
        except Exception as e:
            logger.exception(f"[ReportPanel] Çizim sırasında hata oluştu: {e}")