# tests/gui_test.py
"""
S2K Loader test GUI.

Ana CAD'e dokunmadan, yükleyicinin çıkardığı veriyi görselleştirir.

Kullanım:
    python -m tests.gui_test
"""
import os
os.environ["KIVY_LOG_LEVEL"] = "warning"

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.treeview import TreeView, TreeViewLabel, TreeViewNode
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from kivy.clock import Clock

from logging_config import CadLogger
logger = CadLogger.get(__name__)

from tools.s2kloader import S2KLoader
from domain.scene import Scene


# ============================================================
# RENKLER
# ============================================================

COLOR_BG        = (0.10, 0.12, 0.16, 1.0)
COLOR_PANEL     = (0.14, 0.16, 0.20, 1.0)
COLOR_TREE      = (0.12, 0.14, 0.18, 1.0)
COLOR_TEXT      = (0.9, 0.9, 0.9, 1.0)
COLOR_HEADER    = (0.5, 0.8, 1.0, 1.0)


# ============================================================
# YARDIMCI WIDGET'LAR
# ============================================================

class Panel(BoxLayout):
    """Arka planı olan panel."""
    
    def __init__(self, bg_color=COLOR_PANEL, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=lambda *a: setattr(self._rect, 'pos', self.pos),
            size=lambda *a: setattr(self._rect, 'size', self.size),
        )


class HeaderLabel(Label):
    """Başlık etiketi."""
    
    def __init__(self, text, **kwargs):
        kwargs.setdefault('font_size', dp(14))
        kwargs.setdefault('bold', True)
        kwargs.setdefault('color', COLOR_HEADER)
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(30))
        super().__init__(text=text, **kwargs)


# ============================================================
# ANA UYGULAMA
# ============================================================

class S2KTestApp(App):
    """S2K Loader test arayüzü."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scene = None
        self.tree_nodes = {}  # (category, id) → treeview node
    
    # ---------------------------------------------------------
    # BUILD
    # ---------------------------------------------------------
    
    def build(self):
        Window.size = (1200, 750)
        Window.clearcolor = COLOR_BG
        
        root = BoxLayout(orientation='vertical', spacing=dp(2), padding=dp(4))
        
        # ---- Üst bar (butonlar) ----
        root.add_widget(self._build_toolbar())
        
        # ---- Ana içerik ----
        content = BoxLayout(orientation='horizontal', spacing=dp(4))
        tree = self._build_tree_panel()
        tree.size_hint_x = 0.35
        content.add_widget(tree)

        detail = self._build_detail_panel()
        detail.size_hint_x = 0.65
        content.add_widget(detail)
        
        root.add_widget(content)
        
        return root
    
    def _build_toolbar(self):
        """Buton bar."""
        toolbar = Panel(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),
            padding=dp(6),
            bg_color=(0.18, 0.20, 0.26, 1.0),
        )
        
        toolbar.add_widget(self._btn("📂 S2K Aç", self.load_s2k))
        toolbar.add_widget(self._btn("⚖ Metraj", self.run_takeoff))
        toolbar.add_widget(self._btn("🌐 Deprem Kütlesi", self.run_seismic_mass))
        toolbar.add_widget(self._btn("🗑 Temizle", self.clear))
        
        # Boşluk
        toolbar.add_widget(Label(size_hint_x=1))

        self.units_label = Label(
            text="Birim: -",
            font_size=dp(12),
            color=(0.6, 0.8, 1.0, 1.0),   # mavi
            size_hint_x=None,
            width=dp(160),
            halign='center',
            valign='middle',
        )
        self.units_label.bind(size=self.units_label.setter('text_size'))
        toolbar.add_widget(self.units_label)
        
        self.status_label = Label(
            text="Hazır",
            font_size=dp(12),
            color=(0.6, 0.8, 0.6, 1.0),
            size_hint_x=0.4,
            halign='right',
            valign='middle',
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        toolbar.add_widget(self.status_label)
        
        return toolbar
    
    def _btn(self, text, callback):
        btn = Button(
            text=text,
            size_hint_x=None,
            width=dp(140),
            font_size=dp(13),
            background_color=(0.25, 0.30, 0.38, 1.0),
            background_normal='',
        )
        btn.bind(on_release=callback)
        return btn
    
    def _build_tree_panel(self):
        """Sol panel — ağaç."""
        panel = Panel(orientation='vertical', spacing=dp(2), padding=dp(4))
        
        panel.add_widget(HeaderLabel("  📋 Model Yapısı"))
        
        # Tree view
        scroll = ScrollView(do_scroll_x=False)
        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(16),
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter('height'))
        scroll.add_widget(self.tree)
        panel.add_widget(scroll)
        
        return panel
    
    def _build_detail_panel(self):
        """Sağ panel — detay tablosu."""
        panel = Panel(orientation='vertical', spacing=dp(2), padding=dp(4))
        
        self.detail_title = HeaderLabel("  Detay (seçim yapın)")
        panel.add_widget(self.detail_title)
        
        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        
        self.detail_grid = GridLayout(
            cols=2,
            spacing=dp(2),
            padding=dp(4),
            size_hint_y=None,
        )
        self.detail_grid.bind(minimum_height=self.detail_grid.setter('height'))
        
        scroll.add_widget(self.detail_grid)
        panel.add_widget(scroll)
        
        return panel
    
    # ---------------------------------------------------------
    # AĞAÇ OLUŞTURMA
    # ---------------------------------------------------------
    
    def _populate_tree(self):
        """Scene'den ağacı doldur."""
        parent = self.tree.parent
        parent.remove_widget(self.tree)
        
        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(16),
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter('height'))
        parent.add_widget(self.tree)
        
        self.tree_nodes.clear()
        
        if not self.scene:
            return

        scene_node = self.tree.add_node(
                                        TreeViewLabel(text="[b]📦 Model[/b]", markup=True)
                                    )
        self._add_info_node(scene_node, "Birim", getattr(self.scene, 'units', '-'))
        self._add_info_node(scene_node, "Node", len(self.scene.nodes))
        self._add_info_node(scene_node, "Frame", len(self.scene.frames))
        self._add_info_node(scene_node, "Area", len(self.scene.areas))
        self._add_info_node(scene_node, "Link", len(self.scene.links))
        self._add_info_node(scene_node, "Polygon", len(self.scene.polygons))
        
        # Kategoriler
        self._add_category("Malzemeler", list(self.scene.def_mgr.materials.values()),
                           "material")
        self._add_category("Kesitler", list(self.scene.def_mgr.sections.values()),
                           "section")
        self._add_category("Link Prop", list(self.scene.def_mgr.link_props.values()),
                           "link_prop")
        self._add_category("Load Pattern", list(self.scene.def_mgr.load_patterns.values()),
                           "load_pattern")
        self._add_category("Load Case", list(self.scene.def_mgr.load_cases.values()),
                           "load_case")
        self._add_category("Kombinasyon", list(self.scene.def_mgr.combinations.values()),
                           "combination")

        # MASS SOURCE
        mass_source = getattr(self.scene.def_mgr, 'mass_source_map', {})
        if mass_source:
            node = self.tree.add_node(
                TreeViewLabel(
                    text=f"[b]MASS SOURCE[/b]  ({len(mass_source)})",
                    markup=True,
                )
            )
            for pattern, mult in mass_source.items():
                child = TreeViewLabel(text=f"  {pattern}  × {mult}")
                self.tree.add_node(child, node)
                
        # Node/Frame/Area/Link/Polygon
        self._add_category("Node", list(self.scene.nodes.values()), "node")
        self._add_category("Frame", list(self.scene.frames.values()), "frame")
        self._add_category("Area", list(self.scene.areas.values()), "area")
        self._add_category("Link", list(self.scene.links.values()), "link")
        self._add_category("Polygon", list(self.scene.polygons.values()), "polygon")

        if self.scene:
            units_str = getattr(self.scene, 'units', '-')
            self.detail_title.text = f"  Detay (seçim yapın)  |  Birim: {units_str}"

    def _add_info_node(self, parent, key, value):
        """Basit bilgi node'u."""
        text = f"  {key}: {value}"
        node = TreeViewLabel(text=text)
        self.tree.add_node(node, parent)
        
    def _add_category(self, title, items, kind):
        """Kategori node'u ve çocuklarını ekle."""
        if not items:
            return
        
        # Kategori başlığı
        cat_text = f"[b]{title}[/b]  ({len(items)})"
        cat_node = self.tree.add_node(
            TreeViewLabel(text=cat_text, markup=True)
        )
        
        # İlk 100 eleman (performans için)
        for item in items[:100]:
            label = getattr(item, 'label', '') or getattr(item, 'name', '?')
            
            # Boş label ise default
            if not label:
                label = getattr(item, 'name', f"ID:{item.unique_id}")
            
            node_label = TreeViewLabel(text=f"  {label}")
            tree_node = self.tree.add_node(node_label, cat_node)
            
            # Seçilebilir yap
            self.tree_nodes[id(tree_node)] = (kind, item)
            
            # Tıklama eventi
            tree_node.bind(
                on_touch_down=lambda inst, touch, item=item, kind=kind:
                    self._on_tree_click(inst, touch, kind, item)
            )
        
        if len(items) > 100:
            extra = TreeViewLabel(text=f"  ... (+{len(items) - 100} daha)")
            self.tree.add_node(extra, cat_node)
    
    def _on_tree_click(self, node, touch, kind, item):
        """Ağaç elemanına tıklama."""
        if not node.collide_point(*touch.pos):
            return False
        
        # Seçim yaptıysa detayı göster
        self._show_detail(kind, item)
        return False
    
    # ---------------------------------------------------------
    # DETAY GÖSTERİMİ
    # ---------------------------------------------------------
    
    def _show_detail(self, kind, item):
        """Seçili elemanın detaylarını göster."""
        self.detail_grid.clear_widgets()
        
        title_text = {
            'material': 'Malzeme',
            'section': 'Kesit',
            'link_prop': 'Link Property',
            'load_pattern': 'Load Pattern',
            'load_case': 'Load Case',
            'combination': 'Kombinasyon',
            'node': 'Node',
            'frame': 'Frame',
            'area': 'Area',
            'link': 'Link',
            'polygon': 'Polygon',
        }.get(kind, '?')
        
        name = getattr(item, 'name', '') or getattr(item, 'label', '?')
        self.detail_title.text = f"  📌 {title_text}: {name}"
        
        # Alanları göster
        if kind == 'material':
            self._detail_material(item)
        elif kind == 'section':
            self._detail_section(item)
        elif kind == 'node':
            self._detail_node(item)
        elif kind == 'frame':
            self._detail_frame(item)
        elif kind == 'area':
            self._detail_area(item)
        elif kind == 'link':
            self._detail_link(item)
        elif kind == 'polygon':
            self._detail_polygon(item)
        elif kind == 'load_pattern':
            self._detail_load_pattern(item)
        elif kind == 'load_case':
            self._detail_load_case(item)
        elif kind == 'combination':
            self._detail_combination(item)
        else:
            self._add_field("Tip", kind)
            self._add_field("Repr", repr(item))
    
    def _add_field(self, key, value, color=None):
        """Detay grid'e bir satır ekle."""
        k = Label(
            text=f"  {key}",
            size_hint_y=None,
            height=dp(24),
            font_size=dp(12),
            color=(0.7, 0.7, 0.7, 1.0),
            halign='left',
            valign='middle',
        )
        k.bind(size=k.setter('text_size'))
        
        v = Label(
            text=str(value),
            size_hint_y=None,
            height=dp(24),
            font_size=dp(12),
            color=color or COLOR_TEXT,
            halign='left',
            valign='middle',
        )
        v.bind(size=v.setter('text_size'))
        
        self.detail_grid.add_widget(k)
        self.detail_grid.add_widget(v)
    
    def _add_subheader(self, text):
        """Detay grid'e alt başlık ekle."""
        lbl = Label(
            text=f"[b]— {text} —[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(28),
            font_size=dp(12),
            color=(0.5, 0.8, 1.0, 1.0),
        )
        self.detail_grid.add_widget(lbl)
        self.detail_grid.add_widget(Label(size_hint_y=None, height=dp(28)))
    
    # ---------------------------------------------------------
    # DETAY — TİP BAZLI
    # ---------------------------------------------------------
    
    def _detail_material(self, mat):
        self._add_field("Ad", mat.name)
        self._add_field("Tip", mat.mat_type.name)
        self._add_field("E1 (MPa)", f"{mat.E1:.2f}")
        self._add_field("E2 (MPa)", f"{mat.E2:.2f}")
        self._add_field("G12 (MPa)", f"{mat.G12:.2f}")
        self._add_field("nu12", f"{mat.nu12:.3f}")
        self._add_field("Yoğunluk", f"{mat.density:.3e}")
        self._add_field("Renk", f"({mat.color[0]:.2f}, {mat.color[1]:.2f}, {mat.color[2]:.2f})")
    
    def _detail_section(self, sec):
        self._add_field("Ad", sec.name)
        self._add_field("Tip", str(sec.profile_type))
        
        if sec.material:
            self._add_field("Malzeme", sec.material.name)
        
        self._add_subheader("Profil Parametreleri")
        for k, v in sec.profile_params.items():
            if isinstance(v, (int, float)):
                if abs(v) > 1e6 or (abs(v) < 1e-3 and v != 0):
                    self._add_field(k, f"{v:.3e}")
                else:
                    self._add_field(k, f"{v:.4f}")
            else:
                self._add_field(k, str(v))
    
    def _detail_node(self, node):
        self._add_field("Label", node.label)
        self._add_field("X", f"{node.x:.3f}")
        self._add_field("Y", f"{node.y:.3f}")
        self._add_field("Z", f"{node.z:.3f}")
        
        if node.restraint:
            fixed = [n.upper() for n in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')
                     if getattr(node.restraint, n, False)]
            self._add_field("Restraint", ", ".join(fixed) if fixed else "Yok")
        else:
            self._add_field("Restraint", "Yok")
        
        # Bağlantılar
        if node.connected:
            self._add_subheader(f"Bağlı ({len(node.connected)})")
            for obj_type, elem_id in node.connected[:10]:
                self._add_field(obj_type.name, elem_id[:8])
        
        # Yükler
        if node.loads:
            self._add_subheader(f"Yükler ({len(node.loads)})")
            for load in node.loads:
                self._add_field(
                    load.pattern_name,
                    f"Fx={load.fx:.1f}, Fy={load.fy:.1f}, Fz={load.fz:.1f}",
                )
    
    def _detail_frame(self, frame):
        self._add_field("Label", frame.label)
        self._add_field("Node I", frame.node_i.label)
        self._add_field("Node J", frame.node_j.label)
        self._add_field("Uzunluk", f"{frame.get_length():.3f}")
        self._add_field("Rotation", f"{frame.rotation_deg:.2f}°")
        
        if frame.section:
            self._add_field("Kesit", frame.section.name)
        
        # Release
        if getattr(frame, 'release_i', None) or getattr(frame, 'release_j', None):
            self._add_subheader("Release")
            for end, rel in [("I", frame.release_i), ("J", frame.release_j)]:
                if rel:
                    active = [k for k, v in rel.items() if v]
                    if active:
                        self._add_field(f"Uç {end}", ", ".join(active))
        
        # Yükler
        total_loads = (len(frame.dist_loads) + len(frame.gravity_loads) +
                       len(frame.point_loads) + len(frame.temp_loads))
        if total_loads > 0:
            self._add_subheader(f"Yükler ({total_loads})")
            
            for l in frame.gravity_loads:
                self._add_field(l.pattern_name, f"Gravity (x{l.multiplier_x:.2f}, y{l.multiplier_y:.2f}, z{l.multiplier_z:.2f})")
            
            for l in frame.dist_loads:
                self._add_field(l.pattern_name, f"Dist p1={l.p1:.3f}, p2={l.p2:.3f}")
    
    def _detail_area(self, area):
        self._add_field("Label", area.label)
        self._add_field("Kalınlık", f"{area.thickness:.3f}")
        self._add_field("Köşe sayısı", len(area.nodes))
        if getattr(area, 'material', None):
            self._add_field("Malzeme", area.material.name)
        else:
            self._add_field("Malzeme", "(tanımsız)")
        self._add_subheader("Köşeler")
        for i, n in enumerate(area.nodes):
            self._add_field(f"Köşe {i+1}", n.label)
        
        # Yükler
        total = (len(area.uniform_loads) + len(area.uniform_to_frame_loads) +
                 len(area.gravity_loads) + len(area.wind_pressures))
        if total > 0:
            self._add_subheader(f"Yükler ({total})")
            
            for l in area.uniform_loads:
                self._add_field(l.pattern_name, f"Uniform {l.value:.3e}")
            for l in area.uniform_to_frame_loads:
                self._add_field(l.pattern_name, f"→ Frame {l.value:.3e}")
            for l in area.wind_pressures:
                self._add_field(l.pattern_name, f"Wind Cp={l.cp:.2f}")
    
    def _detail_link(self, link):
        self._add_field("Label", link.label)
        self._add_field("Node I", link.node_i.label)
        self._add_field("Node J", link.node_j.label)
        self._add_field("Prop", link.propname)
    
    def _detail_polygon(self, poly):
        self._add_field("Label", poly.label)
        self._add_field("Köşe sayısı", len(poly.nodes))
        self._add_subheader("Köşeler")
        for i, n in enumerate(poly.nodes):
            self._add_field(f"Köşe {i+1}", n.label)
    
    def _detail_load_pattern(self, pat):
        self._add_field("Ad", pat.name)
        self._add_field("Design Type", pat.design_type)
        self._add_field("Self Weight Mult", f"{pat.self_wt_mult:.3f}")
        self._add_field("GUID", pat.guid or "-")
    
    def _detail_load_case(self, case):
        self._add_field("Ad", case.name)
        self._add_field("Tip", case.case_type)
        self._add_field("Initial", case.initial_cond)
        self._add_field("Design Type", case.design_type)
        self._add_field("Run", str(case.run_case))
        
        if case.static_assignments:
            self._add_subheader(f"Yük Atamaları ({len(case.static_assignments)})")
            for a in case.static_assignments:
                self._add_field(a.load_name, f"×{a.load_sf:.3f}")
    
    def _detail_combination(self, combo):
        self._add_field("Ad", combo.name)
        self._add_field("Tip", combo.combo_type)
        self._add_field("Auto Design", str(combo.auto_design))
        
        if combo.items:
            self._add_subheader(f"Elemanlar ({len(combo.items)})")
            for item in combo.items:
                self._add_field(item.case_or_pattern_name,
                                f"×{item.scale_factor:.3f}")
    
    # ---------------------------------------------------------
    # AKSİYONLAR
    # ---------------------------------------------------------
    
    def load_s2k(self, *_):
        """S2K dosyası yükle."""
        self._set_status("S2K dosyası seçin...", (0.9, 0.9, 0.5, 1.0))
        
        # Dialog aç (senkron)
        Clock.schedule_once(self._do_load_s2k, 0.1)
    
    def _do_load_s2k(self, dt):
        try:
            loader = S2KLoader()
            if not loader.file_path:
                self._set_status("İptal edildi", (0.9, 0.5, 0.5, 1.0))
                return
            
            scene = loader.load()
            self.scene = scene
            
            # ← YENİ: Units'i göster
            units_str = getattr(scene, 'units', str(loader.units) if loader.units else '-')
            self.units_label.text = f"Birim: {units_str}"
            
            self._populate_tree()
            self._set_status(
                f"✓ Yüklendi: {len(scene.nodes)} node, "
                f"{len(scene.frames)} frame, {len(scene.areas)} area",
                (0.5, 0.9, 0.5, 1.0),
            )
        except Exception as e:
            logger.error(f"S2K yükleme hatası: {e}", exc_info=True)
            self._set_status(f"✗ Hata: {e}", (0.9, 0.3, 0.3, 1.0))
    
    def clear(self, *_):
        """Temizle."""
        self.scene = None
        self.tree.clear_widgets()
        self.detail_grid.clear_widgets()
        self.detail_title.text = "  Detay (seçim yapın)"
        self.units_label.text = "Birim: -"
        self._set_status("Temizlendi", (0.7, 0.7, 0.7, 1.0))
    
    def _set_status(self, text, color=None):
        """Status bar güncelle."""
        self.status_label.text = text
        if color:
            self.status_label.color = color

    def run_takeoff(self, *_):
        """Metraj hesapla."""
        if not self.scene:
            self._set_status("Önce model yükleyin", (0.9, 0.5, 0.5, 1.0))
            return
        
        try:
            from core.analysis.material_takeoff import (
                compute_takeoff, takeoff_to_dataframes,
            )
            
            result = compute_takeoff(self.scene)
            summary_df, by_material_df, elements_df = takeoff_to_dataframes(result)
            
            # Detay panelde göster
            self._show_takeoff(result, summary_df, by_material_df, elements_df)
            
            self._set_status(
                f"✓ Metraj: {result.total_mass:.3f} ton, "
                f"{len(result.elements)} eleman",
                (0.5, 0.9, 0.5, 1.0),
            )
        except Exception as e:
            logger.error(f"Metraj hatası: {e}", exc_info=True)
            self._set_status(f"✗ {e}", (0.9, 0.3, 0.3, 1.0))


    def _show_takeoff(self, result, summary_df, by_material_df, elements_df):
        """Metraj sonuçlarını göster."""
        self.detail_grid.clear_widgets()
        self.detail_title.text = "  ⚖ Malzeme Metrajı"
        
        # Genel özet
        self._add_subheader("Genel Özet")
        for _, row in summary_df.iterrows():
            for col in summary_df.columns:
                self._add_field(col, row[col])
        
        # Malzeme bazlı
        self._add_subheader("Malzeme Bazlı Özet")
        for _, row in by_material_df.iterrows():
            self._add_field(
                row['Malzeme'],
                f"{row['Kütle (kg)']:.1f} kg  |  "
                f"{row['Eleman Sayısı']} adet",
            )
        
        # Tip bazlı
        self._add_subheader("Tip Bazlı")
        for tip, d in result.by_type.items():
            self._add_field(
                tip,
                f"{d['count']} adet, {d['mass']*1000:.1f} kg",
            )

    def run_seismic_mass(self, *_):
        """Deprem kütlesi hesapla."""
        if not self.scene:
            self._set_status("Önce model yükleyin", (0.9, 0.5, 0.5, 1.0))
            return
        
        try:
            from core.analysis.mass_source import compute_seismic_mass
            
            # n katsayısı — ProjectInfo'dan veya varsayılan
            n = 0.3
            info = getattr(self.scene.def_mgr, 'project_info', None)
            if info is not None:
                n = getattr(info, 'live_load_factor', 0.3)
            
            result = compute_seismic_mass(self.scene, n=n)
            self._show_seismic_mass(result)
        except:
            return


    def _show_seismic_mass(self, result):
        """Deprem kütlesini göster."""
        self.detail_grid.clear_widgets()
        self.detail_title.text = "  🌐 Deprem Kütlesi"
        
        self._add_subheader("Formül")
        self._add_field("m", f"G + {result.n} × Q")
        
        self._add_subheader("G — Sabit Yükler")
        self._add_field("Self Weight", f"{result.self_weight:.3f} ton")
        for name, m in result.dead_patterns.items():
            self._add_field(f"  {name}", f"{m:.3f} ton")
        self._add_field("G TOPLAM", f"{result.G:.3f} ton", (1, 0.8, 0.4, 1))
        
        self._add_subheader("Q — Hareketli Yükler")
        for name, m in result.live_patterns.items():
            self._add_field(f"  {name}", f"{m:.3f} ton")
        self._add_field("Q TOPLAM", f"{result.Q:.3f} ton", (0.5, 0.8, 1, 1))
        
        self._add_subheader("Sonuç")
        self._add_field("n", str(result.n))
        self._add_field("n × Q", f"{result.n * result.Q:.3f} ton")
        self._add_field("m = G + n·Q", f"{result.total:.3f} ton", (0.4, 1, 0.4, 1))
        self._add_field("m (kg)", f"{result.total_kg:.0f} kg")
        self._add_field("m (kN)", f"{result.total_weight_kn:.2f} kN")

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    S2KTestApp().run()