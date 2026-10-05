# gui/panel_inspector.py
import os
os.environ["KIVY_LOG_LEVEL"] = "warning"

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label

from gui.basecustompopup import BaseCustomPopup, FONT_DEFAULT
from core.analysis.mass_source import compute_seismic_mass

from logging_config import CadLogger
logger = CadLogger.get(__name__)

# TEMA RENKLERİ
THEME_INSPECTOR = {
    "text": (0.88, 0.90, 0.94, 1),
    "text_dim": (0.55, 0.59, 0.66, 1),
    "accent": (0.30, 0.60, 0.95, 1),
    "selected": (0.15, 0.35, 0.65, 1),
    "row": (0.095, 0.105, 0.125, 1),
    "row_alt": (0.075, 0.085, 0.105, 1),
    "header": (0.12, 0.14, 0.18, 1),
}


class TreeNodeWidget(BoxLayout):
    """
    Derinlemesine Özyinelemeli (Recursive) Ağaç Düğümü
    Sözlük ve Koleksiyon yapılarını sol tarafta dal olarak açar/kapar.
    Class nesnesi veya değer bulunduğunda sağ paneli tetikler.
    """
    def __init__(self, key_name, value, depth=0, content_panel=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, **kwargs)
        self.bind(minimum_height=self.setter("height"))

        self.key_name = str(key_name)
        self.value = value
        self.depth = depth
        self.content_panel = content_panel
        self.is_expanded = False
        self._children_populated = False

        # Veri tipini analiz et
        self.is_container = self._check_is_container(value)

        # Girinti Hesabı (Derinlik arttıkça içeri girer)
        indent = dp(12) * depth

        # Header Satırı
        prefix = "[ + ] " if self.is_container else "  • "
        display_text = f"{prefix}{self.key_name}"
        if self.is_container:
            try:
                display_text += f" ({len(value)})"
            except Exception:
                pass

        self.btn_header = Button(
            text=display_text,
            size_hint_y=None,
            height=dp(28),
            background_normal="",
            background_color=THEME_INSPECTOR["header"] if depth == 0 else THEME_INSPECTOR["row"],
            color=THEME_INSPECTOR["accent"] if self.is_container else THEME_INSPECTOR["text"],
            font_size=dp(11),
            font_name=FONT_DEFAULT,
            bold=(depth == 0 or self.is_container),
            halign="left",
            valign="middle",
            padding=(indent + dp(6), 0)
        )
        self.btn_header.bind(size=self.btn_header.setter("text_size"))
        self.btn_header.bind(on_release=self.on_node_click)
        self.add_widget(self.btn_header)

        # Alt Düğümler Konteyneri
        self.children_container = BoxLayout(
            orientation="vertical",
            spacing=dp(1),
            size_hint_y=None,
            height=0,
            opacity=0
        )
        self.children_container.bind(minimum_height=self.children_container.setter("height"))
        self.add_widget(self.children_container)

    def _check_is_container(self, val):
        """Class nesnelerini değil, sadece sözlük ve liste/koleksiyon dallarını контейнер sayar."""
        if isinstance(val, (dict, list, tuple, set)):
            return True
        return False

    def on_node_click(self, *_):
        # 1. Tıklanan nesnenin detaylarını sağ panele bas
        if self.content_panel:
            self.content_panel.select_item(self.btn_header, self.value)

        # 2. Eğer dal bir kapsayıcı (dict/list) ise aç/kapa yap
        if self.is_container:
            self.toggle()

    def toggle(self):
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            if not self._children_populated:
                self._populate_children()
            prefix = "[ - ] "
            self.children_container.opacity = 1
            self.children_container.height = self.children_container.minimum_height
        else:
            prefix = "[ + ] "
            self.children_container.opacity = 0
            self.children_container.height = 0

        count_str = f" ({len(self.value)})" if hasattr(self.value, '__len__') else ""
        self.btn_header.text = f"{prefix}{self.key_name}{count_str}"

    def _populate_children(self):
        self._children_populated = True
        if not self.is_container:
            return

        iterator = self.value.items() if isinstance(self.value, dict) else enumerate(self.value)

        for sub_k, sub_v in iterator:
            # Düğüm ismini belirle (Class ise nesne adını al, yoksa key/index)
            if hasattr(sub_v, "name") and getattr(sub_v, "name"):
                node_label = f"{sub_k}: {sub_v.name}"
            elif hasattr(sub_v, "label") and getattr(sub_v, "label"):
                node_label = f"{sub_k}: {sub_v.label}"
            else:
                node_label = str(sub_k)

            # Alt Düğüm Ekle (Recursive)
            child_node = TreeNodeWidget(
                key_name=node_label,
                value=sub_v,
                depth=self.depth + 1,
                content_panel=self.content_panel
            )
            self.children_container.add_widget(child_node)

        if self.is_expanded:
            self.children_container.height = self.children_container.minimum_height


class ModelInspectorContent(BoxLayout):
    def __init__(self, scene=None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(6), **kwargs)
        self.scene = scene
        self.selected_btn = None

        # Üst Araç Çubuğu
        toolbar = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(36))
        btn_mass = Button(
            text="Deprem Kütlesi",
            size_hint_x=None,
            width=dp(140),
            background_normal="",
            background_color=THEME_INSPECTOR["accent"],
            color=(1, 1, 1, 1),
            font_size=dp(11),
            font_name=FONT_DEFAULT,
            bold=True
        )
        btn_mass.bind(on_release=self.run_seismic_mass)
        toolbar.add_widget(btn_mass)

        self.status_label = Label(
            text="Model Bekleniyor...",
            color=THEME_INSPECTOR["text_dim"],
            font_size=dp(11),
            font_name=FONT_DEFAULT,
            halign="right",
            valign="middle"
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        toolbar.add_widget(self.status_label)
        self.add_widget(toolbar)

        # Sol/Sağ Gövde
        content = BoxLayout(orientation="horizontal", spacing=dp(8))

        # Sol Panel (Özyinelemeli Ağaç Görünümü)
        scroll_cat = ScrollView(size_hint_x=0.4, do_scroll_x=False)
        self.cat_container = BoxLayout(
            orientation="vertical",
            spacing=dp(2),
            size_hint_y=None
        )
        self.cat_container.bind(minimum_height=self.cat_container.setter("height"))
        scroll_cat.add_widget(self.cat_container)
        content.add_widget(scroll_cat)

        # Sağ Panel (Detay/Class İçeriği)
        scroll_detail = ScrollView(size_hint_x=0.6, do_scroll_x=False)
        self.detail_container = BoxLayout(
            orientation="vertical",
            spacing=dp(2),
            size_hint_y=None
        )
        self.detail_container.bind(minimum_height=self.detail_container.setter("height"))
        scroll_detail.add_widget(self.detail_container)
        content.add_widget(scroll_detail)

        self.add_widget(content)

        if self.scene:
            self.load_scene(self.scene)

    def load_scene(self, scene):
        self.scene = scene
        self.cat_container.clear_widgets()
        self.detail_container.clear_widgets()
        self.selected_btn = None

        if not self.scene:
            self.status_label.text = "Model Bulunamadı"
            return

        units = getattr(self.scene, 'units', None) or (self.scene.get('units') if isinstance(self.scene, dict) else '-')
        self.status_label.text = f"MODEL AKTİF | Birim: {units}"

        raw_dict = {}
        if hasattr(self.scene, "__inspector_tree__"):
            raw_dict = self.scene.__inspector_tree__()
        elif hasattr(self.scene, "__dict__"):
            raw_dict = self.scene.__dict__
        elif isinstance(self.scene, dict):
            raw_dict = self.scene

        for key, value in raw_dict.items():
            if str(key).startswith("_"):
                continue

            node = TreeNodeWidget(
                key_name=key,
                value=value,
                depth=0,
                content_panel=self
            )
            self.cat_container.add_widget(node)

    def select_item(self, btn, raw_data):
        if self.selected_btn:
            self.selected_btn.background_color = THEME_INSPECTOR["header"] if self.selected_btn.bold else THEME_INSPECTOR["row"]

        self.selected_btn = btn
        btn.background_color = THEME_INSPECTOR["selected"]
        self.render_detail(raw_data)

    def render_detail(self, obj):
        """Sağ tarafa Sınıf (Class) örneklerini veya değerleri döker."""
        self.detail_container.clear_widgets()

        if hasattr(obj, "__inspector_tree__"):
            obj = obj.__inspector_tree__()

        detail_pairs = []

        # Eğer seçilen veri bir Sınıf (Class Instance) ise niteliklerini al
        if hasattr(obj, "__dict__"):
            detail_pairs = [(k, v) for k, v in obj.__dict__.items() if not str(k).startswith("_")]
        elif isinstance(obj, dict):
            # Sözlük ise içindeki temel değerleri yaz
            for k, v in obj.items():
                if not isinstance(v, (dict, list, tuple, set)) and not hasattr(v, "__dict__"):
                    detail_pairs.append((k, v))
                else:
                    detail_pairs.append((k, f"<{type(v).__name__}>"))
        else:
            detail_pairs = [("Değer", str(obj)), ("Tip", type(obj).__name__)]

        if not detail_pairs:
            detail_pairs = [("Bilgi", "İçerik boş veya sadece alt gruplardan oluşuyor.")]

        for prop, val in detail_pairs:
            row = BoxLayout(
                orientation="horizontal",
                spacing=dp(6),
                size_hint_y=None,
                height=dp(28)
            )
            lbl_prop = Label(
                text=str(prop),
                color=THEME_INSPECTOR["text_dim"],
                font_size=dp(11),
                font_name=FONT_DEFAULT,
                halign="left",
                valign="middle",
                size_hint_x=0.4
            )
            lbl_val = Label(
                text=str(val),
                color=THEME_INSPECTOR["text"],
                font_size=dp(11),
                font_name=FONT_DEFAULT,
                halign="left",
                valign="middle",
                size_hint_x=0.6,
                bold=True
            )
            lbl_prop.bind(size=lbl_prop.setter("text_size"))
            lbl_val.bind(size=lbl_val.setter("text_size"))

            row.add_widget(lbl_prop)
            row.add_widget(lbl_val)
            self.detail_container.add_widget(row)

    def run_seismic_mass(self, *_):
        if not self.scene:
            self.status_label.text = "Model Yok!"
            return
        try:
            def_mgr = getattr(self.scene, "def_mgr", None)
            project_info = getattr(def_mgr, "project_info", {}) if def_mgr else {}
            site_info = project_info.get("site") if isinstance(project_info, dict) else None
            n = getattr(site_info, "live_load_factor", 0.3) if site_info else 0.3
            result = compute_seismic_mass(self.scene, n=n)
            self.render_detail(result)
            self.status_label.text = "Kütle Hesabı Yapıldı"
        except Exception as e:
            self.status_label.text = f"Hata: {str(e)}"


class ModelInspectorPanel(BaseCustomPopup):
    def __init__(self, scene=None, **kwargs):
        self.inspector_content = ModelInspectorContent(scene=scene)
        super().__init__(
            title_text="MODEL INSPECTOR VE METRAJ",
            content_widget=self.inspector_content,
            size_hint=(0.92, 0.88),
            **kwargs
        )

    def load_scene(self, scene):
        self.inspector_content.load_scene(scene)