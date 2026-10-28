"""
LoadAssignPanel — Seçili poligona uniform to frame yükü atama paneli.
"""
from imgui_bundle import imgui

from domain.definition import DistType, LoadDirection
from ui.base_panel import BasePanel


class LoadAssignPanel(BasePanel):
    def __init__(self, on_apply=None):
        super().__init__(title="Assign Area Load to Frame", width=350.0, height=280.0, pos_first_use=(400, 200))
        self.on_apply = on_apply
        
        self.load_patterns = ["DEAD", "LIVE"]  # Dinamik beslenebilir
        self.selected_pattern_idx = 0
        self.value = 2.0  # kN/m2
        
        self.directions = list(LoadDirection)
        self.selected_dir_idx = 6  # Varsayılan GRAVITY (veya uygun indeks)
        
        self.dist_types = [
                            DistType.ONE_WAY_U1,
                            DistType.ONE_WAY_U2,
                            DistType.TWO_WAY,
                        ]
        self.selected_dist_idx = 0

    def open(self, load_patterns=None):
        super().open()
        if load_patterns:
            self.load_patterns = load_patterns

    def draw_content(self):
        imgui.text("Poligon Yük Atama (Uniform to Frame)")
        imgui.separator()
        imgui.spacing()

        # 1. Load Pattern Seçimi
        if not self.load_patterns:
            self.load_patterns = ["DEFAULT"]
        
        changed_p, self.selected_pattern_idx = imgui.combo(
            "Load Pattern", 
            self.selected_pattern_idx, 
            self.load_patterns
        )
        
        # 2. Değer (Value)
        changed_v, self.value = imgui.input_float("Değer (kN/m²)", self.value, step=0.1, format="%.2f")

        # 3. Yön (Direction)
        dir_names = [d.name for d in self.directions]
        changed_d, self.selected_dir_idx = imgui.combo(
            "Yön (Direction)", 
            self.selected_dir_idx, 
            dir_names
        )

        # 4. Dağıtım Tipi (DistType: One way / Two way)
        dist_names = [dt.value for dt in self.dist_types]
        changed_dist, self.selected_dist_idx = imgui.combo(
            "Dağıtım Tipi", 
            self.selected_dist_idx, 
            dist_names
        )

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # Butonlar
        avail = imgui.get_content_region_avail().x
        btn_w = (avail - 8) * 0.5

        if imgui.button("İptal", imgui.ImVec2(btn_w, 0)):
            self.close()

        imgui.same_line()

        imgui.push_style_color(
            imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.30, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0)
        )
        try:
            if imgui.button("Uygula (Assign)", imgui.ImVec2(btn_w, 0)):
                if callable(self.on_apply):
                    pattern = self.load_patterns[self.selected_pattern_idx]
                    direction = self.directions[self.selected_dir_idx]
                    dist_type = self.dist_types[self.selected_dist_idx]
                    self.on_apply(pattern, self.value, direction, dist_type)
                self.close()
        finally:
            imgui.pop_style_color(2)