# ui/definition_panel.py
"""
DefinitionPanel — BasePanel türevi. DefinitionManager içeriğini ağaç yapısında gösterir.
"""
import imgui
from ui.base_panel import BasePanel



class DefinitionPanel(BasePanel):

    SECTIONS = [
        ("Malzemeler", "materials"),
        ("Kesitler", "sections"),
        ("Link Property'leri", "link_props"),
        ("Yük Pattern'leri", "load_patterns"),
        ("Yük Case'leri", "load_cases"),
        ("Modal Case'ler", "modal_cases"),
        ("Kombinasyonlar", "combinations"),
        ("Spektrum Fonksiyonları", "spectrum_functions"),
        ("Response Spectrum", "response_spectrum_cases"),
        ("Auto Seismic (TBDY)", "auto_seismics"),
        ("Section Cuts", "section_cuts"),
        ("Kütle Kaynağı", "mass_source_map"),   # ← YENİ
    ]

    def __init__(self):
        super().__init__(title="Proje Tanımları (Definitions)", width=420, height=600, pos_first_use=(450, 100))
        self.def_mgr = None
        self._open_groups: set = set()

    def open(self, def_mgr=None):
        super().open()
        if def_mgr is not None:
            self.def_mgr = def_mgr
        self._open_groups.clear()

    def refresh(self, def_mgr):
        self.def_mgr = def_mgr

    def draw_content(self):
        if self.def_mgr is None:
            imgui.text_colored("DefinitionManager bulunamadı", 0.5, 0.5, 0.5, 1.0)
            return

        self._draw_project_info(self.def_mgr)
        imgui.separator()

        imgui.begin_child("def_content", height=0, border=False)
        for display_name, attr_name in self.SECTIONS:
            collection = getattr(self.def_mgr, attr_name, None)
            if collection is None:
                continue
            self._draw_section(display_name, attr_name, collection)
        imgui.end_child()

    def _draw_project_info(self, def_mgr):
        info = getattr(def_mgr, "project_info", {}) or {}
        gen = info.get("gen") if isinstance(info, dict) else getattr(info, "gen", None)
        if gen is not None:
            name = getattr(gen, "project_name", "")
            if name:
                imgui.text_colored(f"Proje: {name}", 0.6, 0.9, 1.0, 1.0)

    def _draw_section(self, display_name, attr_name, collection):
        count = len(collection) if hasattr(collection, "__len__") else 0
        key = f"def_{attr_name}"
        is_open = key in self._open_groups

        arrow = self.ascii_arrow(is_open)
        label = f"{arrow}  {display_name} ({count})"

        if count == 0:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.45, 0.45, 0.45, 1.0)
            imgui.selectable(label, False)
            imgui.pop_style_color(1)
            return

        clicked = imgui.selectable(label, False)[0]
        if clicked:
            if is_open:
                self._open_groups.discard(key)
            else:
                self._open_groups.add(key)
            is_open = not is_open

        if not is_open:
            return

        imgui.indent(20)
        if isinstance(collection, dict):
            for name, obj in collection.items():
                self._draw_object_row(name, obj)
        else:
            for obj in collection:
                name = getattr(obj, "name", "?")
                self._draw_object_row(name, obj)
        imgui.unindent(20)

    def _draw_object_row(self, name, obj):
        imgui.push_id(str(name))
        detail_key = f"obj_{id(obj)}"
        is_open = detail_key in self._open_groups

        arrow = self.ascii_arrow(is_open)
        clicked = imgui.selectable(f"{arrow}  {name}", False)[0]
        if clicked:
            if is_open:
                self._open_groups.discard(detail_key)
            else:
                self._open_groups.add(detail_key)
            is_open = not is_open

        if is_open:
            imgui.indent(20)
            self._draw_object_detail(obj)
            imgui.unindent(20)

        imgui.pop_id()

    def _draw_object_detail(self, obj):
        if obj is None:
            imgui.text_colored("(yok)", 0.5, 0.5, 0.5, 1.0)
            return

        try:
            attrs = vars(obj)
        except TypeError:
            imgui.text(str(obj))
            return

        for key in sorted(attrs.keys()):
            if key.startswith("_"):
                continue
            self._draw_attribute(key, attrs[key])

    def _draw_attribute(self, key, val):
        imgui.push_id(f"attr_{key}")
        try:
            if hasattr(val, "__dataclass_fields__"):
                # dataclass → özyinele
                ...
            elif isinstance(val, dict):
                detail_key = f"attr_{key}_d"
                is_open = detail_key in self._open_groups
                arrow = self.ascii_arrow(is_open)
                imgui.text_colored(f"{key}: ", 0.6, 0.6, 0.7, 1.0)
                imgui.same_line()
                if imgui.selectable(f"{arrow} dict ({len(val)})", False)[0]:
                    if is_open: self._open_groups.discard(detail_key)
                    else: self._open_groups.add(detail_key)
                if is_open:
                    imgui.indent(20)
                    for k, v in val.items():
                        self._draw_attribute(k, v)
                    imgui.unindent(20)
            elif isinstance(val, (list, tuple)):
                # İlk 5 elemanı göster, gerisini "..." ile geç
                imgui.text_colored(f"{key}: list[{len(val)}]", 0.7, 0.7, 0.7, 1.0)
                for i, v in enumerate(val[:5]):
                    imgui.indent(20)
                    self._draw_attribute(f"[{i}]", v)
                    imgui.unindent(20)
                if len(val) > 5:
                    imgui.text_colored(f"  ... ve {len(val)-5} tane daha", 0.5, 0.5, 0.5, 1.0)
            else:
                # ilkel
                imgui.text_colored(f"{key}: {val}", 0.8, 0.8, 0.8, 1.0)
        finally:
            imgui.pop_id()