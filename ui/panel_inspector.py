import os
os.environ["KIVY_LOG_LEVEL"] = "warning"

from dataclasses import asdict, is_dataclass

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.widget import Widget
from core.analysis.mass_source import compute_seismic_mass, MassBreakdown

from tools.s2kloader import S2KLoader


# ============================================================
# TEMA
# ============================================================

THEME = {
    "bg": (0.055, 0.065, 0.080, 1),
    "panel": (0.085, 0.095, 0.115, 1),
    "panel2": (0.105, 0.115, 0.140, 1),
    "header": (0.075, 0.085, 0.105, 1),
    "border": (0.18, 0.20, 0.24, 1),

    "text": (0.88, 0.90, 0.94, 1),
    "text_dim": (0.55, 0.59, 0.66, 1),
    "accent": (0.30, 0.60, 0.95, 1),
    "success": (0.35, 0.75, 0.50, 1),

    "row": (0.095, 0.105, 0.125, 1),
    "row_alt": (0.075, 0.085, 0.105, 1),
}


# ============================================================
# YARDIMCI WIDGET'LAR
# ============================================================

class Card(BoxLayout):
    """Yuvarlatılmış panel."""

    def __init__(self, bg_color=None, **kwargs):
        super().__init__(**kwargs)

        color = bg_color or THEME["panel"]

        with self.canvas.before:
            Color(*color)
            self._bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(8)]
            )

            Color(*THEME["border"])
            self._border = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    dp(8)
                ),
                width=0.8
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas
        )

    def _update_canvas(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

        self._border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(8)
        )


class SectionTitle(BoxLayout):

    def __init__(self, text, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            padding=(dp(12), 0),
            **kwargs
        )

        with self.canvas.before:
            Color(*THEME["header"])
            self._bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(8)]
            )

        self.bind(pos=self._update, size=self._update)

        label = Label(
            text=text.upper(),
            color=THEME["text"],
            bold=True,
            font_size=dp(12),
            halign="left",
            valign="middle",
        )

        label.bind(size=label.setter("text_size"))

        self.add_widget(label)

    def _update(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class PropertyLabel(Label):

    def __init__(self, **kwargs):
        super().__init__(
            color=THEME["text_dim"],
            font_size=dp(12),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(30),
            **kwargs
        )

        self.bind(size=self._update_text)

    def _update_text(self, *_):
        self.text_size = (self.width - dp(12), None)


class ValueLabel(Label):

    def __init__(self, **kwargs):
        super().__init__(
            color=THEME["text"],
            font_size=dp(12),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(30),
            **kwargs
        )

        self.bind(size=self._update_text)

    def _update_text(self, *_):
        self.text_size = (self.width - dp(12), None)


# ============================================================
# TREE LABEL
# ============================================================

class InspectorTreeLabel(TreeViewLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.color = THEME["text"]
        self.font_size = dp(12)
        self.size_hint_y = None
        self.height = dp(30)

        self.padding = (dp(8), 0)

        with self.canvas.before:
            Color(*THEME["row"])
            self._bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(4)]
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas
        )

    def _update_canvas(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


# ============================================================
# DİNAMİK INSPECTOR
# ============================================================

class ModelInspectorPanel(BoxLayout):

    def __init__(self, scene=None, **kwargs):

        super().__init__(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
            **kwargs
        )

        # ----------------------------------------------------
        # ANA ARKA PLAN
        # ----------------------------------------------------

        with self.canvas.before:
            Color(*THEME["bg"])
            self._background = RoundedRectangle(
                pos=self.pos,
                size=self.size
            )

        self.bind(
            pos=self._update_background,
            size=self._update_background
        )

        self.scene = scene
        
        # ====================================================
        # TOOLBAR
        # ====================================================

        toolbar = Card(
            orientation="horizontal",
            spacing=dp(8),
            padding=(dp(8), dp(5)),
            size_hint_y=None,
            height=dp(48),
            bg_color=THEME["header"]
        )

        # btn_open = Button(
        #     text="OPEN S2K",
        #     size_hint_x=None,
        #     width=dp(120),
        #     background_normal="",
        #     background_color=THEME["accent"],
        #     color=(1, 1, 1, 1),
        #     font_size=dp(12),
        #     bold=True
        # )

        # btn_open.bind(
        #     on_release=self._on_file_select_click
        # )

        # toolbar.add_widget(btn_open)

        btn_mass = Button(
                    text="Mass",
                    size_hint_x=None,
                    width=dp(120),
                    background_normal="",
                    background_color=THEME["accent"],
                    color=(1, 1, 1, 1),
                    font_size=dp(12),
                    bold=True
                )
        
        btn_mass.bind(
            on_release=self.run_seismic_mass
        )

        toolbar.add_widget(btn_mass)

        title = Label(
            text="MODEL INSPECTOR",
            color=THEME["text"],
            font_size=dp(13),
            bold=True,
            halign="left",
            valign="middle"
        )

        title.bind(
            size=title.setter("text_size")
        )

        toolbar.add_widget(title)

        self.status_label = Label(
            text="No model loaded",
            color=THEME["text_dim"],
            font_size=dp(11),
            halign="right",
            valign="middle"
        )

        self.status_label.bind(
            size=self.status_label.setter("text_size")
        )

        toolbar.add_widget(self.status_label)

        self.add_widget(toolbar)

        # ====================================================
        # ANA İÇERİK
        # ====================================================

        content = BoxLayout(
            orientation="horizontal",
            spacing=dp(8)
        )

        # ====================================================
        # SOL PANEL
        # ====================================================

        left_panel = Card(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(6),
            size_hint_x=0.38
        )

        left_panel.add_widget(
            SectionTitle("MODEL STRUCTURE")
        )

        self.tree_scroll = ScrollView(
            bar_width=dp(5),
            scroll_type=["bars", "content"]
        )

        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(18),
            size_hint_y=None
        )

        self.tree.bind(
            minimum_height=self.tree.setter("height")
        )

        self.tree_scroll.add_widget(self.tree)

        left_panel.add_widget(
            self.tree_scroll
        )

        content.add_widget(left_panel)

        # ====================================================
        # SAĞ PANEL
        # ====================================================

        right_panel = Card(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(6),
            size_hint_x=0.62
        )

        self.detail_title = SectionTitle(
            "PROPERTY DETAILS"
        )

        right_panel.add_widget(
            self.detail_title
        )

        # ----------------------------------------------------
        # PROPERTY HEADER
        # ----------------------------------------------------

        header = GridLayout(
            cols=2,
            size_hint_y=None,
            height=dp(30)
        )

        header.add_widget(
            Label(
                text="PROPERTY",
                color=THEME["text_dim"],
                font_size=dp(10),
                bold=True,
                halign="left",
                valign="middle"
            )
        )

        header.add_widget(
            Label(
                text="VALUE",
                color=THEME["text_dim"],
                font_size=dp(10),
                bold=True,
                halign="left",
                valign="middle"
            )
        )

        right_panel.add_widget(header)

        # ----------------------------------------------------
        # DETAIL GRID
        # ----------------------------------------------------

        self.detail_scroll = ScrollView(
            bar_width=dp(5),
            scroll_type=["bars", "content"]
        )

        self.detail_grid = GridLayout(
            cols=2,
            spacing=dp(1),
            size_hint_y=None
        )

        self.detail_grid.bind(
            minimum_height=self.detail_grid.setter("height")
        )

        self.detail_scroll.add_widget(
            self.detail_grid
        )

        right_panel.add_widget(
            self.detail_scroll
        )

        content.add_widget(right_panel)

        self.add_widget(content)

        # ----------------------------------------------------
        # BAŞLANGIÇ
        # ----------------------------------------------------

        if scene:
            self.load_scene(scene)

    # ========================================================
    # CANVAS
    # ========================================================

    def _update_background(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    # ========================================================
    # SCENE
    # ========================================================

    def load_scene(self, scene):

        self.scene = scene

        self.tree.clear_widgets()
        self.detail_grid.clear_widgets()

        if not self.scene:
            self.status_label.text = "No model loaded"
            return

        units = getattr(
            self.scene,
            "units",
            "-"
        )

        self.status_label.text = (
            f"MODEL LOADED   |   Units: {units}"
        )

        root_node = self.tree.add_node(
            InspectorTreeLabel(
                text="[b]MODEL[/b]",
                markup=True
            )
        )

        self._build_tree_recursive(
            self.scene,
            root_node
        )

    # ========================================================
    # TREE
    # ========================================================

    def _build_tree_recursive(
        self,
        obj,
        parent_node
    ):

        if hasattr(obj, "__inspector_tree__"):
            items = obj.__inspector_tree__().items()

        elif is_dataclass(obj):
            items = asdict(obj).items()

        elif isinstance(obj, dict):
            items = obj.items()

        elif hasattr(obj, "__dict__"):
            items = obj.__dict__.items()

        else:
            return

        for key, value in items:

            if str(key).startswith("_"):
                continue

            label_text = str(key)

            is_container = isinstance(
                value,
                (dict, list, tuple)
            )

            is_custom_obj = (
                hasattr(value, "__inspector_tree__")
                or is_dataclass(value)
            )

            if is_container or is_custom_obj:

                count_str = (
                    f"  [{len(value)}]"
                    if is_container
                    else ""
                )

                cat_node = self.tree.add_node(
                    InspectorTreeLabel(
                        text=f"{label_text}{count_str}"
                    ),
                    parent_node
                )

                if is_container and len(value) == 0:
                    continue

                if is_custom_obj:

                    self._build_tree_recursive(
                        value,
                        cat_node
                    )

                elif isinstance(value, dict):

                    for sub_k, sub_v in value.items():

                        elem_name = (
                            getattr(sub_v, "name", None)
                            or getattr(sub_v, "label", None)
                            or str(sub_k)
                        )

                        node_item = InspectorTreeLabel(
                            text=str(elem_name)
                        )

                        self.tree.add_node(
                            node_item,
                            cat_node
                        )

                        node_item.bind(
                            on_touch_down=
                            self._create_click_callback(
                                node_item,
                                sub_v
                            )
                        )

                elif isinstance(value, (list, tuple)):

                    for idx, sub_v in enumerate(value):

                        elem_name = (
                            getattr(sub_v, "name", None)
                            or getattr(sub_v, "label", None)
                            or f"[{idx}]"
                        )

                        node_item = InspectorTreeLabel(
                            text=str(elem_name)
                        )

                        self.tree.add_node(
                            node_item,
                            cat_node
                        )

                        node_item.bind(
                            on_touch_down=
                            self._create_click_callback(
                                node_item,
                                sub_v
                            )
                        )

            else:

                node_item = InspectorTreeLabel(
                    text=f"{key}: {value}"
                )

                self.tree.add_node(
                    node_item,
                    parent_node
                )

    # ========================================================
    # SELECTION
    # ========================================================

    def _create_click_callback(
        self,
        node_widget,
        data_object
    ):

        def on_click(instance, touch):

            if node_widget.collide_point(
                *touch.pos
            ):

                self._render_detail(
                    data_object
                )

                return True

            return False

        return on_click

    # ========================================================
    # DETAIL
    # ========================================================
    def _render_tree_data(self, data, level=0):
        for key, value in data.items():

            if isinstance(value, dict):
                self.detail_container.add_widget(
                    SectionTitle(text=str(key))
                )
                self._render_tree_data(value, level + 1)

            else:
                row = BoxLayout(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(32),
                    spacing=dp(10),
                )

                row.add_widget(
                    PropertyLabel(text=str(key))
                )

                row.add_widget(
                    ValueLabel(text=str(value))
                )

                self.detail_container.add_widget(row)
                
    def _render_detail(self, obj):
        self.detail_grid.clear_widgets()
        if hasattr(obj, "__inspector_tree__"):
            data = obj.__inspector_tree__()
            for section, values in data.items():
                # Bölüm başlığı
                self.detail_grid.add_widget(
                    SectionTitle(text=str(section))
                )

                if isinstance(values, dict):
                    for attr, val in values.items():
                        self.detail_grid.add_widget(
                            PropertyLabel(text=str(attr))
                        )

                        self.detail_grid.add_widget(
                            ValueLabel(text=str(val))
                        )

                else:
                    self.detail_grid.add_widget(
                        ValueLabel(text=str(values))
                    )

            return

        if hasattr(obj, "get_inspector_widget"):
            self.detail_grid.add_widget(
                obj.get_inspector_widget()
            )
            return

        if hasattr(obj, "__dict__"):
            data = obj.__dict__

        elif isinstance(obj, dict):
            data = obj

        else:
            data = {"Value": obj}

        for attr, val in data.items():

            if str(attr).startswith("_"):
                continue

            self.detail_grid.add_widget(
                PropertyLabel(text=str(attr))
            )

            self.detail_grid.add_widget(
                ValueLabel(text=str(val))
            )

    # ========================================================
    # FILE
    # ========================================================

    def _on_file_select_click(self, *_):

        self.status_label.text = "Opening file..."

        Clock.schedule_once(
            self._load_s2k_file,
            0.1
        )

    def _load_s2k_file(self, dt):

        try:

            loader = S2KLoader()

            if loader.file_path:

                loaded_scene = loader.load()

                self.load_scene(
                    loaded_scene
                )

            else:

                self.status_label.text = "Cancelled"

        except Exception as e:

            self.status_label.text = (
                f"ERROR: {e}"
            )

    def _set_status(self, text, color=None):
        """Status bar güncelle."""
        self.status_label.text = text
        if color:
            self.status_label.color = color
            
    def run_seismic_mass(self, *_):
        """Deprem kütlesi hesapla."""
        if not self.scene:
            self._set_status("Önce model yükleyin", (0.9, 0.5, 0.5, 1.0))
            return
        
        try:
            
            
            # n katsayısı — ProjectInfo'dan veya varsayılan
            project_info = getattr(self.scene.def_mgr, "project_info", {})

            site_info = project_info.get("site")
            n = getattr(site_info, "live_load_factor", 0.3)

            result = compute_seismic_mass(self.scene, n=n)
            
            self._render_detail(result)
            
        except:
            return