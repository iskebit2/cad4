# ui/definitions_tab.py
"""
DefinitionsTab — scene.def_mgr içeriğini ağaç yapısında gösterir.

Salt okunur. Her grup expand/collapse olabilir.
"""
import imgui


class DefinitionsTab:

    SECTIONS = [
    ("Malzemeler",           "materials"),
    ("Kesitler",             "sections"),
    ("Link Property'leri",   "link_props"),
    ("Yük Pattern'leri",     "load_patterns"),
    ("Yük Case'leri",        "load_cases"),
    ("Modal Case'ler",       "modal_cases"),
    ("Kombinasyonlar",       "combinations"),
    ("Spektrum Fonksiyonları", "spectrum_functions"),
    ("Response Spectrum",    "response_spectrum_cases"),
    ("Auto Seismic (TBDY)",  "auto_seismics"),
    ("Section Cuts",         "section_cuts"), 
]

    def __init__(self):
        self.scene = None
        self._open_groups: set = set()

    # ------------------------------------------------------------------
    def open(self, scene):
        self.scene = scene
        self._open_groups.clear()   # default: hepsi kapalı

    def refresh(self, scene):
        self.scene = scene

    # ------------------------------------------------------------------
    def draw_content(self):
        # def_mgr kontrolü
        def_mgr = getattr(self.scene, "def_mgr", None) if self.scene else None
        if def_mgr is None:
            imgui.spacing()
            imgui.spacing()
            imgui.text_colored("Sahne yok", 0.5, 0.5, 0.5, 1.0)
            return

        # Proje bilgisi — en üstte
        self._draw_project_info(def_mgr)

        imgui.separator()

        # Scrollable içerik
        imgui.begin_child("def_content", height=0, border=False)

        for display_name, attr_name in self.SECTIONS:
            collection = getattr(def_mgr, attr_name, None)
            if collection is None:
                continue
            self._draw_section(display_name, attr_name, collection)

        imgui.end_child()

    # ------------------------------------------------------------------
    def _draw_project_info(self, def_mgr):
        """Küçük bir proje bilgisi başlığı."""
        info = getattr(def_mgr, "project_info", {}) or {}
        gen = info.get("gen")
        if gen is not None:
            name = getattr(gen, "project_name", "")
            if name:
                imgui.text_colored(f"Proje: {name}", 0.6, 0.9, 1.0, 1.0)

    # ------------------------------------------------------------------
    def _draw_section(self, display_name, attr_name, collection):
        """Bir koleksiyon — başlık + içindeki öğeler."""
        count = len(collection) if hasattr(collection, "__len__") else 0

        key = f"def_{attr_name}"
        is_open = key in self._open_groups

        # Başlık — selectable toggle
        arrow = "V" if is_open else ">"
        label = f"{arrow}  {display_name} ({count})"

        if count == 0:
            # Boş gruplar gri, tıklanabilir ama içi boş
            imgui.push_style_color(imgui.COLOR_TEXT,
                                   0.45, 0.45, 0.45, 1.0)
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

        # İçerik
        imgui.indent(20)

        if isinstance(collection, dict):
            for name, obj in collection.items():
                self._draw_object_row(name, obj)
        else:
            for obj in collection:
                name = getattr(obj, "name", "?")
                self._draw_object_row(name, obj)

        imgui.unindent(20)

    # ------------------------------------------------------------------
    def _draw_object_row(self, name, obj):
        """Tek bir nesne satırı — expand edilirse detay."""
        imgui.push_id(str(name))

        # Başlık
        detail_key = f"obj_{id(obj)}"
        is_open = detail_key in self._open_groups

        arrow = ">" if not is_open else "v"

        # Basit satır: isim
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

    # ------------------------------------------------------------------
    def _draw_object_detail(self, obj):
        """Nesnenin özniteliklerini listele."""
        if obj is None:
            imgui.text_colored("(yok)", 0.5, 0.5, 0.5, 1.0)
            return

        # Dataclass ise vars(obj) ile gez
        try:
            attrs = vars(obj)
        except TypeError:
            imgui.text(str(obj))
            return

        # Anahtarları sıralı göster
        for key in sorted(attrs.keys()):
            if key.startswith("_"):
                continue
            val = attrs[key]
            self._draw_attribute(key, val)

    def _draw_attribute(self, key, val):
        imgui.push_id(f"attr_{key}")

        # --- Dataclass → expand edilebilir ---
        if hasattr(val, "__dataclass_fields__"):
            detail_key = f"attr_{key}_d"
            is_open = detail_key in self._open_groups
            arrow = "v" if is_open else ">"

            imgui.text_colored(f"{key}: ", 0.6, 0.6, 0.7, 1.0)
            imgui.same_line()
            clicked = imgui.selectable(f"{arrow} {type(val).__name__}", False)[0]
            if clicked:
                if is_open:
                    self._open_groups.discard(detail_key)
                else:
                    self._open_groups.add(detail_key)

            if is_open:
                imgui.indent(20)
                self._draw_object_detail(val)
                imgui.unindent(20)

            imgui.pop_id()
            return

        # --- Liste içinde dataclass varsa (SectionCut.quad.points gibi) ---
        if (isinstance(val, (list, tuple)) and val
                and hasattr(val[0], "__dataclass_fields__")):
            imgui.text_colored(f"{key}: ({len(val)} eleman)",
                            0.6, 0.6, 0.7, 1.0)
            imgui.indent(20)
            for i, item in enumerate(val[:10]):
                imgui.push_id(f"li_{i}")
                imgui.text(f"[{i}] {type(item).__name__}")
                self._draw_object_detail(item)
                imgui.pop_id()
            if len(val) > 10:
                imgui.text_colored(f"... +{len(val) - 10} daha",
                                0.6, 0.6, 0.6, 1.0)
            imgui.unindent(20)
            imgui.pop_id()
            return

        # --- Tuple listesi (SectionCut.quad.points: [(x,y,z), ...]) ---
        if (isinstance(val, (list, tuple)) and val
                and isinstance(val[0], (list, tuple))):
            imgui.text_colored(f"{key}: ({len(val)} nokta)",
                            0.6, 0.6, 0.7, 1.0)
            imgui.indent(20)
            for i, pt in enumerate(val[:10]):
                imgui.text(f"[{i}]  ({', '.join(f'{v:.2f}' for v in pt)})")
            if len(val) > 10:
                imgui.text_colored(f"... +{len(val) - 10} daha",
                                0.6, 0.6, 0.6, 1.0)
            imgui.unindent(20)
            imgui.pop_id()
            return

        # --- Normal değerler ---
        if val is None:
            text = "-"
        elif isinstance(val, bool):
            text = "True" if val else "False"
        elif isinstance(val, (int, float)):
            text = f"{val:.4g}" if isinstance(val, float) else str(val)
        elif isinstance(val, str):
            text = val if val else '""'
        elif isinstance(val, (list, tuple)):
            parts = []
            for v in list(val)[:4]:
                if isinstance(v, float):
                    parts.append(f"{v:.3g}")
                else:
                    parts.append(str(v))
            text = "[" + ", ".join(parts) + "]"
            if len(val) > 4:
                text += f" +{len(val) - 4}"
        elif isinstance(val, dict):
            text = f"{{...}} ({len(val)} anahtar)"
        else:
            text = getattr(val, "name", str(val))

        # Renk
        if isinstance(val, bool):
            color = (0.4, 0.9, 0.5, 1.0) if val else (0.9, 0.5, 0.5, 1.0)
        elif isinstance(val, (int, float)):
            color = (0.9, 0.85, 0.5, 1.0)
        elif val is None:
            color = (0.5, 0.5, 0.5, 1.0)
        else:
            color = (0.85, 0.85, 0.85, 1.0)

        imgui.text_colored(f"{key}: ", 0.6, 0.6, 0.7, 1.0)
        imgui.same_line()
        imgui.text_colored(str(text), *color)

        imgui.pop_id()