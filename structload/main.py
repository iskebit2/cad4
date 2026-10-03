# main.py
import os
import logging

os.environ["KIVY_LOG_LEVEL"] = "warning"
os.environ["KIVY_NO_ARGS"] = "1"

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from structload.data.defaults import proje_data
from structload.loads.snow_load import SnowLoad
from structload.loads.spectrum import Spectrum
from structload.windcalc.wind_results import WindReport
from structload.utils.meta_tables import create_meta_tables

from structload.gui.report_view import ReportView, CardContainer, AutoLabel, FONT, THEME


class SectionHeader(CardContainer):
    def __init__(self, title_text, icon_str="■", **kwargs):
        super().__init__(bg_color=THEME["bg_card"], radius=8, padding_dp=10, **kwargs)
        self.add_widget(
            AutoLabel(
                text=f"{icon_str}  {title_text.upper()}",
                font_sp=FONT["section"],
                is_bold=True,
                text_color=THEME["primary"],
            )
        )


class StructuralAnalysisApp(App):

    def build(self):
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*THEME["bg_card"])
            root._bg = Rectangle(pos=root.pos, size=root.size)

        root.bind(pos=lambda inst, p: setattr(inst._bg, "pos", p), size=lambda inst, s: setattr(inst._bg, "size", s))

        root_scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        container = BoxLayout(orientation="vertical", spacing=dp(16), padding=dp(14), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))
        # ============================================================
        # BÖLÜM 0: GENEL BİLGİLER
        # ============================================================
        container.add_widget(SectionHeader("Genel Bilgiler", "📋"))
        for tablo in create_meta_tables(proje_data):
            container.add_widget(ReportView(tablo))


        # ------------------------------------------------
        # 1. KAR YÜKÜ HESAPLARI
        # ------------------------------------------------
        container.add_widget(SectionHeader("Kar Yükü Hesapları"))
        snow = SnowLoad(proje_data["snow_config"])
        container.add_widget(ReportView(snow.report()))

        # ------------------------------------------------
        # 2. DEPREM YÜKÜ HESAPLARI
        # ------------------------------------------------
        container.add_widget(SectionHeader("Deprem Yükü Hesapları"))
        eq = Spectrum(proje_data["earthquake_config"])
        eq.run()
        container.add_widget(ReportView(eq.table_parameters))
        container.add_widget(ReportView(eq.table_spectrum))

        # ------------------------------------------------
        # 3. RÜZGAR YÜKÜ HESAPLARI
        # ------------------------------------------------
        container.add_widget(SectionHeader("Rüzgar Yükü Hesapları"))
        wind_report = WindReport(proje_data)
        wind_report.analyze()
        
        # Bütün rüzgar raporu dict/dataframe ne olursa olsun TEK SATIRDA basılır:
        container.add_widget(ReportView(wind_report.report()))

        root_scroll.add_widget(container)
        root.add_widget(root_scroll)
        return root


if __name__ == "__main__":
    StructuralAnalysisApp().run()