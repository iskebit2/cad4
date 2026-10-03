# ui/analysis_popup.py
"""Analiz raporlarını popup olarak göster."""
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp

from logging_config import CadLogger
logger = CadLogger.get(__name__)

# Structload modülleri
from structload.loads.snow_load import SnowLoad
from structload.loads.spectrum import Spectrum
from structload.windcalc.wind_results import WindReport
from structload.utils.meta_tables import create_meta_tables
from structload.gui.report_view import ReportView, CardContainer, AutoLabel, FONT, THEME


class SectionHeader(CardContainer):
    """Bölüm başlığı."""
    def __init__(self, title_text, icon_str="■", **kwargs):
        super().__init__(bg_color=THEME["bg_card"], radius=8, padding_dp=10, **kwargs)
        self.add_widget(AutoLabel(
            text=f"{icon_str}  {title_text.upper()}",
            font_sp=FONT["section"],
            is_bold=True,
            text_color=THEME["primary"],
        ))


class AnalysisPopup(Popup):
    """Analiz raporu popup'ı."""
    
    def __init__(self, proje_data, title="Yapısal Analiz Raporu", **kwargs):
        kwargs.setdefault('title', title)
        kwargs.setdefault('size_hint', (0.85, 0.9))
        kwargs.setdefault('auto_dismiss', True)
        kwargs.setdefault('separator_height', dp(2))
        
        super().__init__(**kwargs)
        
        self.proje_data = proje_data
        
        root = BoxLayout(orientation='vertical')
        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        container = BoxLayout(
            orientation='vertical',
            spacing=dp(16),
            padding=dp(14),
            size_hint_y=None,
        )
        container.bind(minimum_height=container.setter('height'))
        
        # 1. Genel Bilgiler
        try:
            container.add_widget(SectionHeader("Genel Bilgiler", "📋"))
            for tablo in create_meta_tables(proje_data):
                container.add_widget(ReportView(tablo))
        except Exception as e:
            logger.warning(f"Meta tablo hatası: {e}")
        
        # 2. Kar Yükü
        try:
            container.add_widget(SectionHeader("Kar Yükü Hesapları", "❄"))
            snow = SnowLoad(proje_data["snow_config"])
            container.add_widget(ReportView(snow.report()))
        except Exception as e:
            logger.warning(f"Kar analizi hatası: {e}")
            container.add_widget(Label(text=f"Kar hatası: {e}", size_hint_y=None, height=dp(30)))
        
        # 3. Deprem Yükü
        try:
            container.add_widget(SectionHeader("Deprem Yükü Hesapları", "🌐"))
            eq = Spectrum(proje_data["earthquake_config"])
            eq.run()
            container.add_widget(ReportView(eq.table_parameters))
            container.add_widget(ReportView(eq.table_spectrum))
        except Exception as e:
            logger.warning(f"Deprem analizi hatası: {e}")
            container.add_widget(Label(text=f"Deprem hatası: {e}", size_hint_y=None, height=dp(30)))
        
        # 4. Rüzgar Yükü
        try:
            container.add_widget(SectionHeader("Rüzgar Yükü Hesapları", "💨"))
            
            # Polygon kontrolü
            polygons = proje_data.get("polygons", {})
            if not polygons:
                container.add_widget(self._info_label(
                    "Rüzgar analizi için polygon bulunamadı.\n"
                    "Önce Draw Polygon ile yüzey oluşturun."
                ))
            else:
                wind_report = WindReport(proje_data)
                wind_report.analyze()
                container.add_widget(ReportView(wind_report.report()))

        except Exception as e:
            logger.warning(f"Rüzgar analizi hatası: {e}")
            container.add_widget(self._error_label(f"Rüzgar: {e}"))
        
        scroll.add_widget(container)
        root.add_widget(scroll)
        self.content = root

    def _info_label(self, text):
        """Bilgi etiketi (boş veri durumu)."""
        return Label(
            text=text,
            size_hint_y=None,
            height=dp(50),
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            valign='middle',
            text_size=(400, None),
        )

if __name__ == "__main__":
    from structload.data.defaults import proje_data
    

    app = AnalysisPopup(proje_data)