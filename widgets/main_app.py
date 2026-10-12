# app/main_app.py
"""MainApp — sadece Kivy UI kurar ve controller'ları bağlar."""

import os
from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup

from core.engine_factory import create_cad_widget
from gui.basecustompopup import FONT_DEFAULT
from gui.prop_panel import PropertiesPanel
from domain.scene import Scene

from widgets.toolbar import build_toolbar
from widgets.file_actions import FileActions
from app.panels_controller import PanelsController
from widgets.scene_controller import SceneController

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class MainApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.cad_widget = None
        self.properties = None
        self.lbl_info = None
        self.btn_draw_mode = None
        self.loading_indicator = None
        self.scene = Scene()

        # Controllers
        self.panels = PanelsController(self)
        self.scenes = SceneController(self)
        self.actions = FileActions(
            on_scene_loaded=self._on_scene_loaded_by_actions,
            on_error=self._show_error,
            on_loading_show=self._show_loading,
            on_loading_hide=self._hide_loading,
        )
        # save_to_path için callback — actions._save_to_path'ı
        # doğrudan sahneye bağlıyoruz
        self.actions.on_save_to_path = self._save_scene_to_path

    @property
    def engine(self):
        return getattr(self.cad_widget, "engine", None)

    # ------------------------------------------------------------------
    # BUILD
    # ------------------------------------------------------------------
    def build(self):
        root = FloatLayout()

        # CAD widget
        self.cad_widget = create_cad_widget()
        self.cad_widget.size_hint = (1, 1)
        self.cad_widget.pos_hint = {'x': 0, 'y': 0}
        root.add_widget(self.cad_widget)

        self.title = "Yapısal Analiz ve CAD Paneli"

        # Toolbar
        callbacks = {
            "menu":        self.panels.open_main_menu,
            "open":        self.actions.open_project,
            "save":        self.actions.save_project,
            "draw":        self.toggle_draw_mode,
            "import_sap":  self.scenes.import_from_sap,
            "visibility":  self.panels.show_visibility,
            "wind":        self.panels.show_wind_config,
            "print":       self.print_selected_elements,
        }
        toolbar, self.lbl_info, self.btn_draw_mode = build_toolbar(callbacks)
        root.add_widget(toolbar)

        # Properties Panel
        self.properties = PropertiesPanel(pos_hint={'right': 1, 'top': 0.96})
        root.add_widget(self.properties)
        self.properties.hide()
        self.cad_widget.properties_panel = self.properties

        # Loading
        self.loading_indicator = self._make_loading_indicator()
        self.loading_indicator.opacity = 0
        self.loading_indicator.disabled = True
        root.add_widget(self.loading_indicator)

        # Periyodik güncelleme
        Clock.schedule_interval(self._update_draw_btn_ui, 0.2)

        return root

    # ------------------------------------------------------------------
    # DELEGASYONLAR (MainApp içinde kalması gereken glue)
    # ------------------------------------------------------------------
    def action_new(self, *_):
        self.scenes.new_scene()

    def _on_scene_loaded_by_actions(self, scene, path):
        self.scenes.apply_scene(scene, path)
        filename = os.path.basename(path) if path else "Bilinmeyen"
        self.lbl_info.text = f"MODEL: {filename}"

    def _save_scene_to_path(self, path):
        try:
            self.scene.save_to_json(path)
            filename = os.path.basename(path)
            self.lbl_info.text = f"MODEL: {filename}"
            self.actions.set_current_path(path)
            logger.info(f"[Action] Kaydedildi -> {path}")
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}", exc_info=True)
            self._show_error(f"Kaydedilemedi:\n{e}")

    def run_wind_analysis_ui(self, w_dir, engine_kwargs):
        self.scenes.run_wind_analysis(w_dir, engine_kwargs)

    # ------------------------------------------------------------------
    # DRAW MODE
    # ------------------------------------------------------------------
    def toggle_draw_mode(self, *_):
        eng = self.engine
        if not eng or not eng.draw_mgr:
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.close()
        else:
            eng.draw_mgr.start()
        self._update_draw_btn_ui()

    def _update_draw_btn_ui(self, *_):
        eng = self.engine
        if not eng or not hasattr(eng, "draw_mgr") or not self.btn_draw_mode:
            return
        if eng.draw_mgr.is_active:
            self.btn_draw_mode.background_color = (0.20, 0.60, 0.35, 1)
            self.btn_draw_mode.text = "✏ Çizim [AÇIK]"
        else:
            self.btn_draw_mode.background_color = (0.22, 0.28, 0.38, 1)
            self.btn_draw_mode.text = "✏ Çizim (D)"

    # ------------------------------------------------------------------
    # LOADING / ERROR
    # ------------------------------------------------------------------
    def _make_loading_indicator(self):
        box = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(dp(160), dp(36)),
            pos_hint={'right': 0.98, 'y': 0.02},
            spacing=dp(6),
            padding=(dp(8), dp(4)),
        )
        label = Label(
            text="İşlem yapılıyor...",
            font_size=dp(11), font_name=FONT_DEFAULT,
            color=(0.9, 0.9, 0.9, 1.0),
            halign='center', valign='middle',
        )
        label.bind(size=label.setter('text_size'))
        box.add_widget(label)
        box.label = label
        return box

    def _show_loading(self, text="İşlem yapılıyor..."):
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.label.text = text
            self.loading_indicator.opacity = 1
            self.loading_indicator.disabled = False

    def _hide_loading(self):
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.opacity = 0
            self.loading_indicator.disabled = True

    def _show_error(self, message):
        self._hide_loading()
        lbl = Label(
            text=str(message), font_name=FONT_DEFAULT, font_size=dp(12),
            color=(1, 0.4, 0.4, 1),
            halign="center", valign="middle",
        )
        popup = Popup(
            title_text="HATA",
            content_widget=lbl,
            size_hint=(0.7, 0.4),
        )
        popup.open()

    def print_selected_elements(self, *_):
        """Seçili elemanları analiz edip konsola ve yapıya yazar."""
        eng = self.engine
        if not eng:
            self._show_error("Yazdırma için motor bulunamadı.")
            return

        # Seçilen elemanları SelectionManager üzerinden alıyoruz
        selected_elements = eng.sel_mgr.get_selected() if hasattr(eng, "sel_mgr") else []
        if not selected_elements:
            logger.info("Seçili eleman bulunamadı.")
            return

        temp_dict = {}
        for elem in selected_elements:
            # element_type güvenli şekilde alınıyor
            elem_type = getattr(elem, "element_type", elem.__class__.__name__).lower()
            print(f"Seçili eleman ID: {getattr(elem, 'unique_id', id(elem))}, element_type: {elem_type}")
            
            if elem_type not in temp_dict:
                temp_dict[elem_type] = []
            temp_dict[elem_type].append(elem)

        # Dictionary mapping
        selected_dict = {
            "nodes": [n.to_dict() for n in temp_dict.get("node", []) if hasattr(n, "to_dict")],
            "frames": [f.to_dict() for f in temp_dict.get("frame", []) if hasattr(f, "to_dict")],
            "areas": [a.to_dict() for a in temp_dict.get("area", []) if hasattr(a, "to_dict")],
            "links": [l.to_dict() for l in temp_dict.get("link", []) if hasattr(l, "to_dict")],
            "polygons": [p.to_dict() for p in temp_dict.get("polygon", []) if hasattr(p, "to_dict")]
        }

        
        for frame in temp_dict.get("frame", []):
            # Frame nesnesinin node_i ve node_j bağlantıları üzerinden ilerleyelim
            frame_id = getattr(frame, "unique_id", id(frame))
            node_i = getattr(frame, "node_i", None)
            node_j = getattr(frame, "node_j", None)
            
            print(f"{frame_id}: [{node_i.coords if hasattr(node_i, 'coords') else str(node_i)}, {node_j.coords if hasattr(node_j, 'coords') else str(node_j)}]")
            
            
            
            

        temp_zones={}
        for poly in temp_dict.get("polygon", []):
            poly_id = getattr(poly, "unique_id", id(poly))
            node_in_polygons = []
            for node in getattr(poly, "nodes", []):
                node_in_polygons.append(node.coords if hasattr(node, "coords") else str(node))
            
            aa=poly.windplane if hasattr(poly, 'windplane') else {}
            cpe10=aa.get("cpe10",[])
            temp_zones[poly_id] = {"coords":node_in_polygons,"cpe10": cpe10}

            
            # print(f"Polygon windplane: {poly.windplane if hasattr(poly, 'windplane') else 'N/A'}")
        print("temp_zones:", temp_zones)
        # print(f"\nSeçili frameler: {selected_dict['frames']}")
        # print(f"\nNode'lar framelerde: {node_in_frames}")
        # print(f"\nSeçili polygonler: {selected_dict['polygons']}")
        # print(f"\nNode'lar polygonlerde: {node_in_polygons}")
        
        # if not selected:
        #     self._show_error("Yazdırılacak seçili eleman yok.")
        #     return
        # # Seçili elemanları yazdırmak için bir popup aç
        # text = "\n".join(str(e) for e in selected)
        # lbl = Label(
        #     text=text, font_name=FONT_DEFAULT, font_size=dp(12),
        #     color=(0.9, 0.9, 0.9, 1),
        #     halign="left", valign="top",
        # )
        # lbl.bind(size=lbl.setter("text_size"))
        # popup = Popup(
        #     title_text="Seçili Elemanlar",
        #     content_widget=lbl,
        #     size_hint=(0.8, 0.6),
        # )
        # popup.open()