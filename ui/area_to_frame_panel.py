# ui/area_to_frame_panel.py
"""Area to Frame paneli — imgui UI katmanı. İş mantığı tools/area_to_frame.py'de."""
from __future__ import annotations

from imgui_bundle import imgui

from domain.element import Frame
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame, AssocDraft, AssocPreview, TransferResult
from ui.base_panel import BasePanel
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class AreaToFramePanel(BasePanel):

    def __init__(self, on_transfer_complete=None):
        super().__init__(
            title="Area to Frame",
            width=520,
            height=620,
            pos_first_use=(420, 140),
        )
        self.project = None
        self.service: AreaToFrame | None = None
        self.on_transfer_complete = on_transfer_complete

        # UI state
        self._selected_polygon_id: int | None = None
        self._draft: AssocDraft | None = None
        self._status: str = ""
        self._show_all_frames: bool = False
        self._step_buffer: float | None = None
        self._bins_buffer: int | None = None

        # Wind zone UI tercihleri
        self._selected_wind_zone: tuple[str, int] | None = None
        self._wind_cpe_index = 0
        self._cpi_positive = 0.2
        self._cpi_negative = -0.3

        # Renderer preview
        self._preview_active: bool = False

    # ------------------------------------------------------------------
    # Yaşam döngüsü — preview'i kapat
    # ------------------------------------------------------------------
    def open(self, **kwargs):
        super().open(**kwargs)

    def close(self):
        self._clear_preview()
        super().close()

    # ------------------------------------------------------------------
    def set_context(self, ctx: dict):
        super().set_context(ctx)
        project = ctx.get("project")
        self.project = project
        self.service = AreaToFrame(project) if project is not None else None

        polygons = self.service.list_polygons() if self.service else []
        available_ids = {int(p.unique_id) for p in polygons}
        if self._selected_polygon_id not in available_ids:
            self._selected_polygon_id = (
                int(polygons[0].unique_id) if polygons else None
            )
            self._draft = None
            self._step_buffer = None
            self._bins_buffer = None
            self._clear_preview()

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.service is None:
            imgui.text_colored(
                imgui.ImVec4(0.95, 0.55, 0.4, 1.0),
                "Proje bağlı değil.",
            )
            self._clear_preview()
            return
        polygons = self.service.list_polygons()
        if not polygons:
            imgui.text("Sahnede polygon yok.")
            self._clear_preview()
            return

        selected = self._ensure_selected(polygons)
        if selected is None:
            self._clear_preview()
            return

        self._draw_toolbar(selected)
        imgui.separator()

        self._draw_polygon_selector(polygons, selected)
        self._draw_summary(selected)
        imgui.separator()

        self._draw_assoc_list(selected)
        imgui.separator()

        self._draw_wind_zone_section(selected)
        imgui.separator()

        self._draw_grid_section()
        imgui.separator()

        self._draw_transfer_button(selected)

        if self._status:
            imgui.spacing()
            imgui.text_wrapped(self._status)

    # ------------------------------------------------------------------
    def _ensure_selected(self, polygons: list[Polygon]) -> Polygon | None:
        selected = self.service.get_polygon(self._selected_polygon_id)
        if selected is None:
            selected = polygons[0]
            self._selected_polygon_id = int(selected.unique_id)
        if self._draft is None or self._draft.polygon_id != int(selected.unique_id):
            self._draft = self.service.new_draft(selected)
            self._sync_preview()
        return selected

    # ------------------------------------------------------------------
    def _draw_toolbar(self, polygon: Polygon):
        draft = self._draft
        has_draft_changes = draft is not None and draft.dirty

        if not has_draft_changes:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0),
            )
        if imgui.button("Apply##af_apply", imgui.ImVec2(80, 0)) and has_draft_changes:
            info = self.service.apply(polygon, draft)
            self._status = (
                f"{info['associated']} frame assoc uygulandı, "
                f"{info['excluded']} hariç."
            )
            self._sync_preview()
        if not has_draft_changes:
            imgui.pop_style_color(1)
        imgui.same_line()

        if imgui.button("Cancel##af_cancel", imgui.ImVec2(70, 0)):
            if draft is not None:
                self.service.cancel(polygon, draft)
            self._status = "Draft iptal edildi."
            self._sync_preview()
        imgui.same_line()

        if imgui.button("Auto Assoc##af_auto", imgui.ImVec2(110, 0)):
            if draft is not None:
                info = self.service.auto_assoc(polygon, draft, keep_excluded=True)
                self._status = (
                    f"Auto assoc: {info['added']} aday, "
                    f"{info['excluded']} hariç."
                )
                self._sync_preview()
        imgui.same_line()

        if imgui.button("Clear##af_clear", imgui.ImVec2(60, 0)):
            if draft is not None:
                self.service.clear_draft(draft)
            self._status = "Draft temizlendi."
            self._sync_preview()
        imgui.same_line()

        selected_frames = self._selected_frames_from_scene()
        can_add = bool(selected_frames) and draft is not None
        if not can_add:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0),
            )
        if imgui.button("Seçilileri Ekle##af_addsel", imgui.ImVec2(120, 0)) and can_add:
            ids = [int(f.unique_id) for f in selected_frames]
            info = self.service.add_selected_frames(polygon, draft, ids)
            self._status = f"{info['added']} seçili frame eklendi."
            self._sync_preview()
        if not can_add:
            imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    def _draw_polygon_selector(self, polygons: list[Polygon], selected: Polygon):
        current_label = self._polygon_label(selected)
        if imgui.begin_combo("Polygon##af_poly", current_label):
            for p in polygons:
                is_sel = int(p.unique_id) == int(selected.unique_id)
                if imgui.selectable(self._polygon_label(p), is_sel)[1]:
                    self._selected_polygon_id = int(p.unique_id)
                    self._draft = None
                    self._status = ""
            imgui.end_combo()

        imgui.same_line()
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
            f"Tip: {selected.poly_type.name}   Yön: {selected.dist_type.value}",
        )

    def _draw_summary(self, polygon: Polygon):
        summary = self.service.polygon_loads_summary(polygon)
        unit = self.service.area_load_unit()
        imgui.text(
            f"Atanmış alan yükü: {len(summary['assigned_loads'])}"
        )
        for load in summary["assigned_loads"]:
            imgui.bullet_text(
                f"{load.pattern_name} | {load.value:.3f} {unit}"
            )
        for item in summary["wind_transfers"]:
            imgui.bullet_text(
                f"Rüzgar {item.get('direction_key')} / "
                f"{item.get('zone_label')} / {item.get('cpe_kind')}"
            )
        if (not summary["assigned_loads"]
                and not summary["wind_transfers"]):
            imgui.text_disabled(
                "Bu polygon üzerinde Load Manager'a aktarılmış yük yok."
            )
        if summary["transferred_frame_ids"]:
            imgui.text_disabled(
                "Son aktarım frame ID'leri: "
                + ", ".join(str(i) for i in summary["transferred_frame_ids"])
            )

    # ------------------------------------------------------------------
    def _draw_assoc_list(self, polygon: Polygon):
        draft = self._draft
        if draft is None:
            return

        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            f"Hedef Frame'ler  (assoc: {len(draft.associated)} | "
            f"hariç: {len(draft.excluded)})",
        )
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.7, 0.6, 1.0),
            "Renk: yeşil=assoc, kırmızı=hariç, gri=ilgisiz, sarı=seçili",
        )

        frames = self.service.list_frames()
        if not frames:
            imgui.text_disabled("Sahnede frame yok.")
            return

        imgui.checkbox("Tümünü göster##af_all", self._show_all_frames)
        if self._show_all_frames:
            visible_ids = sorted(frames.keys())
        else:
            visible_ids = sorted(draft.associated | draft.excluded)

        imgui.begin_child(
            "##af_assoc_list", imgui.ImVec2(0, 220),
            imgui.ChildFlags_.borders,
        )
        if not visible_ids:
            imgui.text_disabled(
                "Liste boş — 'Auto Assoc' veya 'Seçilileri Ekle' kullanın."
            )
        for uid in visible_ids:
            fr = frames.get(uid)
            if fr is None:
                continue
            on = uid in draft.associated
            label = fr.label or f"Frame {uid}"
            changed, new_on = imgui.checkbox(
                f"{label}  (id={uid})##af_{uid}", on,
            )
            if changed:
                self.service.toggle(draft, uid, bool(new_on))
                self._sync_preview()
        imgui.end_child()

    # ------------------------------------------------------------------
    def _draw_wind_zone_section(self, polygon: Polygon):
        entries = self.service.list_wind_zones(polygon)
        imgui.text("Rüzgar zone aktarımı")
        if not entries:
            imgui.text_disabled("Bu polygon için wind zone yok.")
            return

        entry_keys = [(k, i) for k, i, _ in entries]
        if self._selected_wind_zone not in entry_keys:
            self._selected_wind_zone = entry_keys[0]
        sel = next(
            e for e in entries if (e[0], e[1]) == self._selected_wind_zone
        )
        direction_key, zone_index, zone = sel

        label = f"{direction_key} | {zone.label} ({zone_index + 1})"
        if imgui.begin_combo("Wind zone##af_wz", label):
            for key, idx, item in entries:
                is_sel = (key, idx) == self._selected_wind_zone
                text = f"{key} | {item.label} ({idx + 1})"
                if imgui.selectable(text, is_sel)[1]:
                    self._selected_wind_zone = (key, idx)
            imgui.end_combo()

        _, self._wind_cpe_index = imgui.combo(
            "Cpe türü##af_cpe", self._wind_cpe_index, ["Cpe10", "Cpe1"],
        )
        _, self._cpi_positive = imgui.input_float(
            "Cpi (+)##af_cpip", self._cpi_positive,
        )
        _, self._cpi_negative = imgui.input_float(
            "Cpi (-)##af_cpim", self._cpi_negative,
        )
        if imgui.button("Rüzgar zone aktar##af_wind_transfer"):
            cpe_kind = "cpe10" if self._wind_cpe_index == 0 else "cpe1"
            result = self.service.transfer_wind_zone(
                polygon, direction_key, zone_index, zone,
                cpe_kind=cpe_kind,
                cpi_pos=self._cpi_positive,
                cpi_neg=self._cpi_negative,
            )
            self._handle_result(result)

    # ------------------------------------------------------------------
    def _draw_grid_section(self):
        step, bins = self.service.get_grid_settings()
        if self._step_buffer is None:
            self._step_buffer = step
        if self._bins_buffer is None:
            self._bins_buffer = bins

        imgui.text(f"Grid adımı ({self.service.length_unit()})")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._step_buffer = imgui.input_float(
            "##af_step", self._step_buffer, 1.0, 10.0,
        )
        imgui.pop_item_width()

        imgui.text("Bin sayısı")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._bins_buffer = imgui.input_int("##af_bins", self._bins_buffer)
        imgui.pop_item_width()

        if imgui.button("Grid ayarını uygula##af_grid_apply"):
            self.service.set_grid_settings(self._step_buffer, self._bins_buffer)
            self._status = "Grid ayarları kaydedildi."

    # ------------------------------------------------------------------
    def _draw_transfer_button(self, polygon: Polygon):
        summary = self.service.polygon_loads_summary(polygon)
        enabled = bool(summary["assigned_loads"])
        if not enabled:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.25, 0.25, 0.25, 1.0),
            )
        if imgui.button(
            "Seçili frame'lere aktar##af_transfer", imgui.ImVec2(-1, 0),
        ) and enabled:
            result = self.service.transfer_area_loads(polygon)
            self._handle_result(result)
        if not enabled:
            imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    def _handle_result(self, result: TransferResult):
        self._status = result.status
        if result.ok and result.touched_frames and callable(self.on_transfer_complete):
            self.on_transfer_complete(result.touched_frames)

    # ------------------------------------------------------------------
    # Renderer preview
    # ------------------------------------------------------------------
    def _engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    def _sync_preview(self):
        eng = self._engine()
        renderer = getattr(eng, "renderer", None) if eng else None
        if renderer is None:
            self._preview_active = False
            return
        draft = self._draft
        if draft is None:
            renderer.set_assoc_preview(None)
            self._preview_active = False
            return
        preview = AssocPreview(
            polygon_id=draft.polygon_id,
            associated=set(draft.associated),
            excluded=set(draft.excluded),
            active=True,
        )
        renderer.set_assoc_preview(preview)
        self._preview_active = True

    def _clear_preview(self):
        eng = self._engine()
        renderer = getattr(eng, "renderer", None) if eng else None
        if renderer is not None:
            renderer.set_assoc_preview(None)
        self._preview_active = False

    # ------------------------------------------------------------------
    def _selected_frames_from_scene(self) -> list[Frame]:
        if self.project is None or self.project.math_model is None:
            return []
        try:
            return [
                el for el in self.project.math_model.get_selected()
                if isinstance(el, Frame)
            ]
        except Exception:
            return []

    @staticmethod
    def _polygon_label(p: Polygon) -> str:
        return p.label or f"Polygon {p.unique_id}"