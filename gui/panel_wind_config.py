# gui/panel_wind_config.py

from typing import Callable, Optional, Tuple

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock

# --- Projendeki sabitler (yoksa fallback) ---
try:
    from gui.basecustompopup import FONT_DEFAULT, THEME
except Exception:
    FONT_DEFAULT = "Roboto"
    THEME = {"text_title": (1, 1, 1, 1)}

# --- Projendeki servisler (yoksa fallback) ---
try:
    from tools.wind_service import WindSceneAdapter
    from structload.data.wind_data import ARAZI_KATEGORILERI
    from structload.windcalc.wind_analyzer import WindAnalyzer
except Exception:
    WindSceneAdapter = None
    WindAnalyzer = None
    ARAZI_KATEGORILERI = {
        "Kategori 0": {},
        "Kategori I": {},
        "Kategori II": {},
        "Kategori III": {},
        "Kategori IV": {},
    }


# ============================================================
#  ARKA PLANI OLAN MODAL VIEW (şeffaf katman sorununu çözer)
# ============================================================
class OpaqueModalView(ModalView):
    """
    ModalView'ın arka planına opak bir dikdörtgen çizer.
    Böylece arkadaki widget'lar görünmez ve touch event'ler
    net şekilde modal içeriğine gider.
    """
    def __init__(self, bg_color=(0.08, 0.09, 0.11, 1.0), **kwargs):
        kwargs.setdefault("background", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("auto_dismiss", False)
        kwargs.setdefault("size_hint", (0.9, 0.9))
        super().__init__(**kwargs)

        self._bg_color = bg_color
        with self.canvas.before:
            Color(*self._bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


# ============================================================
#  PANEL İÇERİĞİ (ScrollView içine konacak)
# ============================================================
class WindConfigPanelContent(BoxLayout):
    def __init__(self, scene, on_analyze_callback: Optional[Callable] = None, **kwargs):
        super().__init__(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
            size_hint_y=None,
            **kwargs
        )
        self.bind(minimum_height=self.setter("height"))

        self.scene = scene
        self.on_analyze_callback = on_analyze_callback
        self.selected_w_dir = (1.0, 0.0, 0.0)

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

        grid_dirs = GridLayout(
            cols=4, spacing=dp(6),
            size_hint_x=1.0, size_hint_y=None, height=dp(40)
        )
        self.btn_px = ToggleButton(text="+X (0°)", group="wdir", state="down",
                                   font_name=FONT_DEFAULT, font_size=dp(11))
        self.btn_nx = ToggleButton(text="-X (180°)", group="wdir",
                                   font_name=FONT_DEFAULT, font_size=dp(11))
        self.btn_py = ToggleButton(text="+Y (90°)", group="wdir",
                                   font_name=FONT_DEFAULT, font_size=dp(11))
        self.btn_ny = ToggleButton(text="-Y (270°)", group="wdir",
                                   font_name=FONT_DEFAULT, font_size=dp(11))

        self.btn_px.bind(on_release=lambda *_: self._update_direction((1.0, 0.0, 0.0)))
        self.btn_nx.bind(on_release=lambda *_: self._update_direction((-1.0, 0.0, 0.0)))
        self.btn_py.bind(on_release=lambda *_: self._update_direction((0.0, 1.0, 0.0)))
        self.btn_ny.bind(on_release=lambda *_: self._update_direction((0.0, -1.0, 0.0)))

        for b in (self.btn_px, self.btn_nx, self.btn_py, self.btn_ny):
            grid_dirs.add_widget(b)
        self.add_widget(grid_dirs)

        # 3. GEOMETRİ
        self.add_widget(Label(
            text="[b]Bina Boyutları & Kritik e Uzunluğu [m][/b]",
            markup=True, font_size=dp(11), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(18), color=(0.8, 0.85, 0.9, 1)
        ))

        grid_geo = GridLayout(
            cols=4, spacing=dp(6),
            size_hint_x=1.0, size_hint_y=None, height=dp(72)
        )
        self.input_b = TextInput(font_name=FONT_DEFAULT, multiline=False)
        self.input_d = TextInput(font_name=FONT_DEFAULT, multiline=False)
        self.input_h = TextInput(font_name=FONT_DEFAULT, multiline=False)
        self.input_e = TextInput(font_name=FONT_DEFAULT, multiline=False)

        grid_geo.add_widget(Label(text="b [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_b)
        grid_geo.add_widget(Label(text="d [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_d)
        grid_geo.add_widget(Label(text="h [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_h)
        grid_geo.add_widget(Label(text="e [m]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_geo.add_widget(self.input_e)
        self.add_widget(grid_geo)

        # 4. ÇEVRE KOŞULLARI
        self.add_widget(Label(
            text="[b]Eurocode / TS EN 1991-1-4 Çevre Parametreleri[/b]",
            markup=True, font_size=dp(11), font_name=FONT_DEFAULT,
            size_hint_y=None, height=dp(18), color=(0.8, 0.85, 0.9, 1)
        ))

        grid_env = GridLayout(
            cols=4, spacing=dp(6),
            size_hint_x=1.0, size_hint_y=None, height=dp(72)
        )
        self.input_vb0 = TextInput(text="28.0", font_name=FONT_DEFAULT, multiline=False)

        terrain_keys = list(ARAZI_KATEGORILERI.keys()) if ARAZI_KATEGORILERI else ["Kategori III"]
        default_terrain = "Kategori III" if "Kategori III" in terrain_keys else terrain_keys[0]
        self.spinner_terrain = Spinner(
            text=default_terrain, values=terrain_keys,
            font_name=FONT_DEFAULT
        )
        self.spinner_terrain.bind(text=lambda *_: self._refresh_from_engine())
        self.input_vb0.bind(on_text_validate=lambda *_: self._refresh_from_engine())

        self.input_qp = TextInput(font_name=FONT_DEFAULT, multiline=False)

        grid_env.add_widget(Label(text="vb0 [m/s]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.input_vb0)
        grid_env.add_widget(Label(text="Arazi Kat.:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.spinner_terrain)
        grid_env.add_widget(Label(text="q_p [kN/m²]:", font_name=FONT_DEFAULT, font_size=dp(11)))
        grid_env.add_widget(self.input_qp)
        grid_env.add_widget(Label(text="", font_name=FONT_DEFAULT))
        grid_env.add_widget(Label(text="", font_name=FONT_DEFAULT))
        self.add_widget(grid_env)

        # 5. ANALİZ BUTONU
        btn_run = Button(
            text="ANALİZİ BAŞLAT VE YÜZEYLERİ (ZONE) OLUŞTUR ➔",
            font_name=FONT_DEFAULT, font_size=dp(12), bold=True,
            size_hint_y=None, height=dp(46),
            background_normal="", background_color=(0.2, 0.65, 0.35, 1),
            color=(1, 1, 1, 1)
        )
        btn_run.bind(on_release=self._on_run_pressed)
        self.add_widget(btn_run)

        # İlk hesap (engine varsa)
        Clock.schedule_once(lambda dt: self._refresh_from_engine(), 0)

    # --------------------------------------------------------
    def _update_direction(self, w_dir: Tuple[float, float, float]):
        self.selected_w_dir = w_dir
        self._refresh_from_engine()

    def _refresh_from_engine(self):
        if WindAnalyzer is None or WindSceneAdapter is None:
            return
        try:
            vb0 = float(self.input_vb0.text)
        except ValueError:
            vb0 = 28.0

        try:
            points, polygons = WindSceneAdapter.extract_wind_data_from_scene(self.scene)
        except Exception:
            return
        if not points:
            return

        try:
            analyzer = WindAnalyzer(
                points=points, polygons=polygons,
                w_dir=list(self.selected_w_dir),
                v_b0=vb0,
                terrain=self.spinner_terrain.text,
            )
            geo = analyzer.engine.geometry
            self.input_b.text = str(round(geo.get("b", 0.0), 3))
            self.input_d.text = str(round(geo.get("d", 0.0), 3))
            self.input_h.text = str(round(geo.get("h", 0.0), 3))
            self.input_e.text = str(round(geo.get("e", 0.0), 3))
            self.input_qp.text = str(round(analyzer.engine.q_p, 3))
        except Exception:
            pass

    def _on_run_pressed(self, *_):
        try:
            vb0 = float(self.input_vb0.text)
        except ValueError:
            vb0 = 28.0

        engine_kwargs = {
            "v_b0": vb0,
            "terrain": self.spinner_terrain.text,
        }

        if WindSceneAdapter is not None:
            try:
                WindSceneAdapter.run_wind_analysis_and_update_scene(
                    scene=self.scene,
                    w_dir=self.selected_w_dir,
                    engine_kwargs=engine_kwargs,
                )
            except TypeError:
                # Eski imza: wind_config yerine engine_kwargs kabul etmiyor olabilir
                WindSceneAdapter.run_wind_analysis_and_update_scene(
                    scene=self.scene,
                    w_dir=self.selected_w_dir,
                )

        if self.on_analyze_callback:
            self.on_analyze_callback()


# ============================================================
#  PANEL (ModalView tabanlı)
# ============================================================
class WindConfigPanel(OpaqueModalView):
    def __init__(self, scene, on_analyze_callback: Optional[Callable] = None, **kwargs):
        kwargs.setdefault("size_hint", (0.92, 0.92))
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)

        # Dış çerçeve
        root = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            padding=dp(8),
        )

        # Başlık
        title = Label(
            text="RÜZGAR ANALİZİ & GEOMETRİ KONFİGÜRASYONU",
            font_name=FONT_DEFAULT,
            font_size=dp(14),
            bold=True,
            color=THEME.get("text_title", (1, 1, 1, 1)),
            size_hint_y=None,
            height=dp(30),
        )
        root.add_widget(title)

        # ScrollView içine içerik
        scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=dp(6),
        )
        content = WindConfigPanelContent(
            scene=scene,
            on_analyze_callback=on_analyze_callback,
        )
        scroll.add_widget(content)
        root.add_widget(scroll)

        # Kapat butonu
        close_btn = Button(
            text="KAPAT",
            size_hint_y=None,
            height=dp(42),
            font_name=FONT_DEFAULT,
            font_size=dp(12),
            bold=True,
            background_normal="",
            background_color=(0.40, 0.20, 0.20, 1),
            color=(1, 1, 1, 1),
        )
        close_btn.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close_btn)

        self.add_widget(root)


# ============================================================
#  BAĞIMSIZ TEST
# ============================================================
if __name__ == "__main__":
    from kivy.app import App
    from kivy.uix.floatlayout import FloatLayout

    class _MockScene:
        """WindSceneAdapter çağrılarına karşı dayanıklı sahte sahne."""
        def __init__(self):
            self.nodes = []
            self.elements = []
            self.polygons = []

    class TestApp(App):
        def build(self):
            self.title = "WindConfigPanel - Bağımsız Test"
            root = FloatLayout()

            # Arka planda tıklanabilir bir buton: modal açıkken tıklanmamalı
            bg_btn = Button(
                text="ARKA PLAN BUTONU\n(Modal açıkken tıklanamamalı)",
                size_hint=(0.4, 0.2),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                background_normal="",
                background_color=(0.2, 0.4, 0.6, 1),
                font_name=FONT_DEFAULT,
                font_size=dp(13),
            )
            bg_btn.bind(on_release=lambda *_: print("[TEST] Arka plan butonuna TIKLANDI (istenmeyen durum)"))
            root.add_widget(bg_btn)

            open_btn = Button(
                text="PANELİ AÇ",
                size_hint=(0.3, 0.1),
                pos_hint={"center_x": 0.5, "y": 0.05},
                background_normal="",
                background_color=(0.2, 0.65, 0.35, 1),
                font_name=FONT_DEFAULT,
                font_size=dp(14),
                bold=True,
            )
            open_btn.bind(on_release=lambda *_: self.open_panel())
            root.add_widget(open_btn)

            # Uygulama açılır açılmaz paneli otomatik göster
            Clock.schedule_once(lambda dt: self.open_panel(), 0.3)

            return root

        def open_panel(self):
            def on_done():
                print("[TEST] Analiz callback'i çağrıldı.")

            panel = WindConfigPanel(
                scene=_MockScene(),
                on_analyze_callback=on_done,
            )
            panel.bind(on_dismiss=lambda *_: print("[TEST] Panel kapatıldı."))
            panel.open()

    TestApp().run()