# ui/panels/slab_analysis_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from app.settings.categories import Category
from core.design.timber_check import TimberFloorEvaluator
from core.units import UnitSystem
from domain.definition import TimberFloorSpec
from ui.base.panel_base import PanelBase


class SlabAnalysisPanel(PanelBase):
    panel_name = "slab_analysis"
    title = "Döşeme Analizi (Ahşap / OSB)"
    category = Category.TOOLS
    menu_label = "Döşeme Analizi"
    icon = "grid"
    uses_draft = False
    show_apply_bar = False
    width = 980
    height = 740
    pos_first_use = (200, 100)
    context = ("app",)

    def __init__(self, app=None, **overrides):
        self._selected_index: int = 0
        self._stress_rows: list[dict] = []
        self._vib_rows: list[dict] = []
        self._status_msg: str = ""
        super().__init__(app=app, **overrides)

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _evaluate_spec(self, project, spec: TimberFloorSpec) -> None:
        unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)
        evaluator = TimberFloorEvaluator(spec=spec, unit_system=unit_system)
        stress_df, vib_df = evaluator.evaluate()
        self._stress_rows = stress_df.to_dict(orient="records")
        self._vib_rows = vib_df.to_dict(orient="records")

        chk_bend = next((r["Değer"] for r in self._stress_rows if r["Sembol"] == "chk"), "-")
        chk_fire = next((r["Değer"] for r in self._stress_rows if r["Sembol"] == "chk_fi"), "Devre Dışı")
        chk_vib = next((r["Değer"] for r in self._vib_rows if r["Tanım"] == "Titreşim Kontrolü"), "-")
        chk_defl = next((r["Değer"] for r in self._vib_rows if r["Tanım"] == "Sehim Kontrolü (q)"), "-")
        self._status_msg = f"Eğilme: {chk_bend} | Yangın: {chk_fire} | Titreşim: {chk_vib} | Sehim: {chk_defl}"

    def draw_content(self):
        project = self._project()
        if project is None:
            imgui.text("Aktif proje yok.")
            return

        floors: list[TimberFloorSpec] = project.timber_floors
        if not floors:
            floors.append(TimberFloorSpec(name="Döşeme 1"))

        if self._selected_index >= len(floors):
            self._selected_index = len(floors) - 1
        if self._selected_index < 0:
            self._selected_index = 0

        self._draw_toolbar(project, floors)
        imgui.separator()

        avail = imgui.get_content_region_avail()
        imgui.begin_child("##slab_inputs", imgui.ImVec2(370.0, avail.y - 32.0), imgui.ChildFlags_.borders)
        self._draw_spec_editor(floors[self._selected_index])
        imgui.end_child()

        imgui.same_line()

        imgui.begin_child("##slab_results", imgui.ImVec2(0.0, avail.y - 32.0), imgui.ChildFlags_.borders)
        self._draw_results_tables(project, floors[self._selected_index])
        imgui.end_child()

        if self._status_msg:
            imgui.text_colored(imgui.ImVec4(0.6, 0.95, 0.6, 1.0), self._status_msg)

    def _draw_toolbar(self, project, floors: list[TimberFloorSpec]) -> None:
        names = [f"{i + 1}. {f.name}" for i, f in enumerate(floors)]
        imgui.push_item_width(220)
        ch, idx = imgui.combo("Döşeme", self._selected_index, names)
        if ch:
            self._selected_index = idx
            self._evaluate_spec(project, floors[self._selected_index])
        imgui.pop_item_width()

        imgui.same_line()
        if imgui.button("+ Yeni Döşeme", imgui.ImVec2(120, 28)):
            new_spec = TimberFloorSpec(name=f"Döşeme {len(floors) + 1}")
            project.add_timber_floor(new_spec)
            self._selected_index = len(floors) - 1
            self._evaluate_spec(project, new_spec)

        imgui.same_line()
        if imgui.button("Sil", imgui.ImVec2(60, 28)) and len(floors) > 1:
            project.remove_timber_floor(self._selected_index)
            self._selected_index = max(0, self._selected_index - 1)
            self._evaluate_spec(project, floors[self._selected_index])

        imgui.same_line()
        if imgui.button("Hesapla ve Raporla", imgui.ImVec2(160, 28)):
            self._evaluate_spec(project, floors[self._selected_index])

    def _draw_spec_editor(self, spec: TimberFloorSpec) -> None:
        imgui.push_item_width(145)
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Kimlik ve Malzeme")
        _, spec.name = imgui.input_text("Döşeme Adı", spec.name)
        _, spec.wood_grade = imgui.input_text("Ahşap Sınıfı", spec.wood_grade)
        _, spec.osb_grade = imgui.input_text("OSB Sınıfı", spec.osb_grade)

        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Geometri")
        _, spec.h_k = imgui.input_float("Kiriş Yüksekliği h_k", spec.h_k, step=10.0, format="%.1f")
        _, spec.b_k = imgui.input_float("Kiriş Genişliği b_k", spec.b_k, step=5.0, format="%.1f")
        _, spec.t_osb = imgui.input_float("OSB Kalınlığı t_osb", spec.t_osb, step=1.0, format="%.1f")
        _, spec.b_s = imgui.input_float("Aks Aralığı b_s", spec.b_s, step=20.0, format="%.1f")
        _, spec.span = imgui.input_float("Açıklık L", spec.span, step=100.0, format="%.1f")

        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Yükler ve Katsayılar")
        _, spec.dead_load_knm2 = imgui.input_float("Kaplama Sabit Yük", spec.dead_load_knm2, step=0.05, format="%.2f")
        _, spec.live_load_knm2 = imgui.input_float("Hareketli Yük Q", spec.live_load_knm2, step=0.25, format="%.2f")
        _, spec.ULS_g = imgui.input_float("ULS γ_G", spec.ULS_g, step=0.05, format="%.2f")
        _, spec.ULS_q = imgui.input_float("ULS γ_Q", spec.ULS_q, step=0.05, format="%.2f")
        _, spec.CN = imgui.input_float("CN", spec.CN, step=0.05, format="%.2f")
        _, spec.CY = imgui.input_float("CY", spec.CY, step=0.05, format="%.2f")
        _, spec.CB = imgui.input_float("CB", spec.CB, step=0.05, format="%.2f")
        _, spec.OMEGA = imgui.input_float("Ω", spec.OMEGA, step=0.05, format="%.2f")
        _, spec.damping_ratio = imgui.input_float("Sönüm Oranı ξ", spec.damping_ratio, step=0.005, format="%.3f")

        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Yangın Tahkiki (EN 1995-1-2)")
        _, spec.fire_enabled = imgui.checkbox("Yangın Kontrolü Aktif", spec.fire_enabled)
        if spec.fire_enabled:
            _, spec.t_fire_min = imgui.input_float("Yangın Süresi (dk)", spec.t_fire_min, step=15.0, format="%.0f")
            _, spec.beta_n_mm_per_min = imgui.input_float("β_n (mm/dk)", spec.beta_n_mm_per_min, step=0.05, format="%.2f")
            exposures = ["3-sides", "4-sides"]
            cur_e = exposures.index(spec.exposure) if spec.exposure in exposures else 0
            ch_e, idx_e = imgui.combo("Yangın Yüzeyi", cur_e, exposures)
            if ch_e:
                spec.exposure = exposures[idx_e]
            _, spec.CY20 = imgui.input_float("CY20", spec.CY20, step=0.05, format="%.2f")
        imgui.pop_item_width()

    def _draw_results_tables(self, project, spec: TimberFloorSpec) -> None:
        if not self._stress_rows and not self._vib_rows:
            self._evaluate_spec(project, spec)

        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Eğilme ve Yangın Tahkiki")
        self._draw_kv_table("##slab_stress_tbl", self._stress_rows, height=340.0)

        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Titreşim ve Sehim Analizi (EN 1995-1-1)")
        self._draw_kv_table("##slab_vib_tbl", self._vib_rows, height=0.0)

    def _draw_kv_table(self, table_id: str, rows: list[dict], height: float) -> None:
        cols = ["Tanım", "Formül", "Sembol", "Değer", "Birim"]
        if imgui.begin_table(
            table_id,
            len(cols),
            imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y,
            imgui.ImVec2(0.0, height),
        ):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for r in rows:
                imgui.table_next_row()
                val_str = str(r.get("Değer", ""))
                for j, k in enumerate(cols):
                    imgui.table_set_column_index(j)
                    txt = str(r.get(k, ""))
                    if k == "Değer" and val_str in ("✔️", "❌"):
                        col = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if val_str == "✔️" else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
                        imgui.text_colored(col, "OK" if val_str == "✔️" else "YETERSİZ")
                    else:
                        imgui.text(txt)
            imgui.end_table()