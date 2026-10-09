# gui/panel_wind_config.py

from typing import Callable, Optional, Tuple
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner

from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT
from tools.wind_service import WindSceneAdapter
from structload.data.wind_data import ARAZI_KATEGORILERI
from structload.windcalc.wind_analyzer import WindAnalyzer


class WindConfigPanelContent(BoxLayout):
    def __init__(self, scene, on_analyze_callback: Optional[Callable] = None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        self.scene = scene
        self.on_analyze_callback = on_analyze_callback
        self.selected_w_dir = (1.0, 0.0, 0.0)

        # Buton Renkleri
        self.COLOR_ACTIVE = (0.2, 0.6, 0.86, 1)
        self.COLOR_INACTIVE = (0.25, 0.28, 0.3, 1)

        # 1. BAŞLIK
        self.add_widget(Label(
            text="[b]Rüzgar Analizi Konfigürasyonu (Birimler: kN, m, kN/m²)[/b]",
            markup=True, font_size=dp(12), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(24), color=(0.2, 0.8, 0.4, 1)
        ))

        # 2. RÜZGAR DOĞRULTUSU
        self.add_widget(Label(
            text="[b]Rüzgar Doğrultusu Seçimi[/b]",
            markup=True, font_size=dp(11), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(18), color=(0.8, 0.85, 0.9, 1)
        ))

        grid_dirs = GridLayout(cols=4, spacing=dp(6), size_hint_x=1.0, size_hint_y=None, height=dp(36))
        self.btn_px = Button(text="+X (0°)", font_name=FONT_DEFAULT, font_size=dp(11), size_hint=(1, 1), background_color=self.COLOR_ACTIVE)
        self.btn_nx = Button(text="-X (180°)", font_name=FONT_DEFAULT, font_size=dp(11), size_hint=(1, 1), background_color=self.COLOR_INACTIVE)
        self.btn_py = Button(text="+Y (90°)", font_name=FONT_DEFAULT, font_size=dp(11), size_hint=(1, 1), background_color=self.COLOR_INACTIVE)
        self.btn_ny = Button(text="-Y (270°)", font_name=FONT_DEFAULT, font_size=dp(11), size_hint=(1, 1), background_color=self.COLOR_INACTIVE)

        self.btn_px.bind(on_release=lambda *_: self._set_direction((1.0, 0.0, 0.0), self.btn_px))
        self.btn_nx.bind(on_release=lambda *_: self._set_direction((-1.0, 0.0, 0.0), self.btn_nx))
        self.btn_py.bind(on_release=lambda *_: self._set_direction((0.0, 1.0, 0.0), self.btn_py))
        self.btn_ny.bind(on_release=lambda *_: self._set_direction((0.0, -1.0, 0.0), self.btn_ny))

        self.dir_buttons = [self.btn_px, self.btn_nx, self.btn_py, self.btn_ny]
        for b in self.dir_buttons:
            grid_dirs.add_widget(b)
        self.add_widget(grid_dirs)

        # 3. GEOMETRİ
        self.add_widget(Label(
            text="[b]Bina Boyutları & Kritik e Uzunluğu [m][/b]",
            markup=True, font_size=dp(11), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(18), color=(0.8, 0.85, 0.9, 1)
        ))

        grid_geo = GridLayout(cols=4, spacing=dp(6), size_hint_x=1.0, size_hint_y=None, height=dp(64))
        self.input_b = TextInput(font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))
        self.input_d = TextInput(font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))
        self.input_h = TextInput(font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))
        self.input_e = TextInput(font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))

        grid_geo.add_widget(Label(text="b [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_b)
        grid_geo.add_widget(Label(text="d [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_d)
        grid_geo.add_widget(Label(text="h [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_h)
        grid_geo.add_widget(Label(text="e [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_e)
        self.add_widget(grid_geo)

        # 4. ÇEVRE PARAMETRELERİ
        self.add_widget(Label(
            text="[b]Eurocode / TS EN 1991-1-4 Çevre Parametreleri[/b]",
            markup=True, font_size=dp(11), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(18), color=(0.8, 0.85, 0.9, 1)
        ))

        grid_env = GridLayout(cols=4, spacing=dp(6), size_hint_x=1.0, size_hint_y=None, height=dp(64))
        self.input_vb0 = TextInput(text="28.0", font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))

        terrain_keys = list(ARAZI_KATEGORILERI.keys()) if ARAZI_KATEGORILERI else ["Kategori III"]
        self.spinner_terrain = Spinner(
            text="Kategori III" if "Kategori III" in terrain_keys else terrain_keys[0],
            values=terrain_keys, font_name=FONT_DEFAULT, size_hint=(1, 1)
        )
        self.spinner_terrain.bind(text=lambda *_: self._refresh_from_engine())
        self.input_vb0.bind(on_text_validate=lambda *_: self._refresh_from_engine())

        self.input_qp = TextInput(font_name=FONT_DEFAULT, multiline=False, size_hint=(1, 1))

        grid_env.add_widget(Label(text="vb0 [m/s]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.input_vb0)
        grid_env.add_widget(Label(text="Arazi Kat.:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.spinner_terrain)
        grid_env.add_widget(Label(text="q_p [kN/m²]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.input_qp)
        grid_env.add_widget(Label(text="", font_name=FONT_DEFAULT))
        grid_env.add_widget(Label(text="", font_name=FONT_DEFAULT))
        self.add_widget(grid_env)

        # 5. ONAY BUTONU
        btn_run = Button(
            text="ANALİZİ BAŞLAT VE YÜZEYLERİ (ZONE) OLUŞTUR ➔",
            font_name=FONT_DEFAULT, font_size=dp(12), bold=True,
            size_hint_x=1.0, size_hint_y=None, height=dp(42),
            background_color=(0.2, 0.65, 0.35, 1)
        )
        btn_run.bind(on_release=self._on_run_pressed)
        self.add_widget(btn_run)

        self._refresh_from_engine()

    def _set_direction(self, w_dir: Tuple[float, float, float], active_btn: Button):
        self.selected_w_dir = w_dir
        for b in self.dir_buttons:
            b.background_color = self.COLOR_ACTIVE if b == active_btn else self.COLOR_INACTIVE
        self._refresh_from_engine()

    def _refresh_from_engine(self):
        try:
            vb0 = float(self.input_vb0.text)
        except ValueError:
            vb0 = 28.0

        points, polygons = WindSceneAdapter.extract_wind_data_from_scene(self.scene)
        
        if points:
            analyzer = WindAnalyzer(
                points=points,
                polygons=polygons,
                w_dir=list(self.selected_w_dir),
                v_b0=vb0,
                terrain=self.spinner_terrain.text
            )

            geo = analyzer.engine.geometry
            self.input_b.text = str(round(geo.get("b", 0.0), 3))
            self.input_d.text = str(round(geo.get("d", 0.0), 3))
            self.input_h.text = str(round(geo.get("h", 0.0), 3))
            self.input_e.text = str(round(geo.get("e", 0.0), 3))
            self.input_qp.text = str(round(analyzer.engine.q_p, 3))

    def _on_run_pressed(self, *_):
        try:
            vb0 = float(self.input_vb0.text)
        except ValueError:
            vb0 = 28.0

        engine_kwargs = {
            "v_b0": vb0,
            "terrain": self.spinner_terrain.text
        }

        # main.py'ye seçilen rüzgar yönünü ve kwargs sözlüğünü gönderir
        if self.on_analyze_callback:
            self.on_analyze_callback(self.selected_w_dir, engine_kwargs)

class WindConfigPanel(BaseCustomPopup):
    def __init__(self, scene, on_run_analysis: Optional[Callable] = None, **kwargs):
        content = WindConfigPanelContent(scene=scene, on_analyze_callback=on_run_analysis)
        super().__init__(
            title_text="RÜZGAR ANALİZİ & GEOMETRİ KONFİGÜRASYONU",
            content_widget=content,
            size_hint=(0.75, 0.78),
            **kwargs
        )