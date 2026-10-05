# ui/analysis_popup.py
"""Analiz raporlarını BaseCustomPopup altyapısıyla gösterir."""

import sys
from pathlib import Path

# --- PYDROID HİYERARŞİ DÜZELTİCİ ---
FILE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FILE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ------------------------------------

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp

from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT

# Logger güvenli içe aktarım
try:
    from logging_config import CadLogger
    logger = CadLogger.get(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Structload modülleri
try:
    from structload.loads.snow_load import SnowLoad
    from structload.loads.spectrum import Spectrum
    from structload.windcalc.wind_results import WindReport
    from structload.utils.meta_tables import create_meta_tables
    from structload.gui.report_view import ReportView, CardContainer, AutoLabel, FONT, THEME
except ImportError as e:
    logger.warning(f"Structload modül yükleme uyarısı: {e}")


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


class AnalysisReportContent(BoxLayout):
    """Analiz raporunun dinamik ScrollView içeriği."""
    
    def __init__(self, proje_data, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.proje_data = proje_data

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        container = BoxLayout(
            orientation='vertical',
            spacing=dp(16),
            padding=dp(10),
            size_hint_y=None,
        )
        container.bind(minimum_height=container.setter('height'))

        # Veriyi dict veya attribute olarak güvenle okuyan yardımcı
        def get_val(key, default=None):
            if isinstance(proje_data, dict):
                return proje_data.get(key, default)
            return getattr(proje_data, key, default)

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
            snow_cfg = get_val("snow_config", {})
            snow = SnowLoad(snow_cfg)
            container.add_widget(ReportView(snow.report()))
        except Exception as e:
            logger.warning(f"Kar analizi hatası: {e}")
            container.add_widget(Label(text=f"Kar hatası: {e}", size_hint_y=None, height=dp(30)))

        # 3. Deprem Yükü
        try:
            container.add_widget(SectionHeader("Deprem Yükü Hesapları", "🌐"))
            eq_cfg = get_val("earthquake_config", {})
            eq = Spectrum(eq_cfg)
            eq.run()
            container.add_widget(ReportView(eq.table_parameters))
            container.add_widget(ReportView(eq.table_spectrum))
        except Exception as e:
            logger.warning(f"Deprem analizi hatası: {e}")
            container.add_widget(Label(text=f"Deprem hatası: {e}", size_hint_y=None, height=dp(30)))

        # 4. Rüzgar Yükü
        try:
            container.add_widget(SectionHeader("Rüzgar Yükü Hesapları", "💨"))
            polygons = get_val("polygons", {})
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
            container.add_widget(self._info_label(f"Rüzgar Hatası: {e}"))

        scroll.add_widget(container)
        self.add_widget(scroll)

    def _info_label(self, text):
        """Bilgi/Uyarı etiketi."""
        lbl = Label(
            text=text,
            size_hint_y=None,
            height=dp(50),
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            valign='middle',
            font_name=FONT_DEFAULT
        )
        lbl.bind(size=lbl.setter('text_size'))
        return lbl


class AnalysisPopup(BaseCustomPopup):
    """
    BaseCustomPopup mimarisine oturtulmuş Analiz Raporu Paneli.
    """
    def __init__(self, proje_data, title_text="YAPISAL ANALİZ RAPORU", **kwargs):
        report_content = AnalysisReportContent(proje_data=proje_data)
        super().__init__(
            title_text=title_text,
            content_widget=report_content,
            size_hint=(0.92, 0.90),
            **kwargs
        )


# ============================================================
# BAĞIMSIZ PYDROID TEST UYGULAMASI
# ============================================================
if __name__ == "__main__":
    class AnalysisTestApp(App):
        def build(self):
            btn = Button(
                text="ANALİZ RAPORUNU AÇ",
                size_hint=(None, None),
                size=(dp(220), dp(50)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            )
            btn.bind(on_release=self.show_popup)
            return btn

        def show_popup(self, *_):
            try:
                from structload.data.defaults import proje_data
            except ImportError:
                # Test için varsayılan dummy veri
                proje_data = {
                    "snow_config": {},
                    "earthquake_config": {},
                    "polygons": {}
                }

            popup = AnalysisPopup(proje_data=proje_data)
            popup.open()

    AnalysisTestApp().run()