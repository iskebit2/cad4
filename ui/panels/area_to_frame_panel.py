# ui/panels/area_to_frame_panel.py
"""Area to Frame paneli — standart layout + collapsing sections."""
from __future__ import annotations

from imgui_bundle import imgui

from domain.element import Frame
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame, AssocDraft, AssocPreview, TransferResult
from logging_config import CadLogger
from ui.base.panel_base import PanelBase, Category

logger = CadLogger.get(__name__)


class AreaToFramePanel(PanelBase):
    __abstract__ = False
    panel_name = "area_to_frame"
    title = "Area to Frame"
    category = Category.LOADS
    quick = False
    context = ("project", "engine")
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True

    width = 620
    height = 760
    pos_first_use = (420.0, 140.0)

    def __init__(self, app=None, on_transfer_complete=None, **overrides):
        super().__init__(app=app, **overrides)
        self.project = None
        self.service: AreaToFrame | None = None
        self.on_transfer_complete = on_transfer_complete

        self._selected_polygon_id: int | None = None
        self._draft: AssocDraft | None = None
        self._status: str = ""
        self._show_all_frames: bool = False
        self._step_buffer: float | None = None
        self._bins_buffer: int | None = None

        self._selected_wind_zone: tuple[str, int] | None = None
        self._wind_cpe_index = 0
        self._cpi_positive = 0.2
        self._cpi_negative = -0.3

        self._preview_active: bool = False

    # ------------------------------------------------------------------
    def _on_context_ready(self) -> None:
        project = getattr(self, "project", None)
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

    def close(self) -> None:
        self._clear_preview()
        super().close()

    # ------------------------------------------------------------------
    # 1. HEADER
    # ------------------------------------------------------------------
    def draw_header(self) -> None:
        if self.service is None:
            imgui.text_colored(imgui.ImVec4(0.95, 0.55, 0.4, 1.0), "Proje bağlı değil.")
            return

        polygons = self.service.list_polygons()
        if not polygons:
            imgui.text_disabled("Sahnede polygon yok.")
            return

        selected = self._ensure_selected(polygons)
        if selected is None:
            return

        self.section_label("Polygon:")
        imgui.same_line()
        imgui.push_item_width(320)
        if imgui.begin_combo("##af_poly", self._polygon_label(selected)):
            for p in polygons:
                is_sel = int(p.unique_id) == int(selected.unique_id)
                if imgui.selectable(self._polygon_label(p), is_sel)[1]:
                    self._selected_polygon_id = int(p.unique_id)
                    self._draft = None
                    self._status = ""
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.same_line()
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.85, 0.7, 1.0),
            f"Tip: {selected.poly_type.name}   Yön: {selected.dist_type.value}",
        )

        self._draw_summary(selected)

    def _draw_summary(self, polygon: Polygon) -> None:
        summary = self.service.polygon_loads_summary(polygon)
        unit = self.service.area_load_unit()
        imgui.text_disabled(
            f"Atanmış alan yükü: {len(summary['assigned_loads'])} | "
            f"Rüzgar transferi: {len(summary['wind_transfers'])}"
        )
        if self._draft is not None:
            imgui.same_line()
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.8, 0.4, 1.0),
                f"| assoc draft: {len(self._draft.associated)} "
                f"(hariç {len(self._draft.excluded)})",
            )

    # ------------------------------------------------------------------
    # 2. SETTINGS — toolbar (Apply / Cancel / Auto / Clear / Add)
    # ------------------------------------------------------------------
    def draw_settings(self) -> None:
        draft = self._draft
        if draft is None:
            return

        has_changes = bool(draft.dirty)
        if self.action_button("Apply##af_apply", 100, has_changes):
            info = self.service.apply(self._selected_polygon(), draft)
            self._status = (
                f"{info['associated']} frame assoc uygulandı, "
                f"{info['excluded']} hariç."
            )
            self._sync_preview()

        imgui.same_line()
        if self.action_button("Cancel##af_cancel", 90, True):
            self.service.cancel(self._selected_polygon(), draft)
            self._status = "Draft iptal edildi."
            self._sync_preview()

        imgui.same_line()
        if self.action_button("Auto Assoc##af_auto", 140, True):
            info = self.service.auto_assoc(self._selected_polygon(), draft, keep_excluded=True)
            self._status = f"Auto assoc: {info['added']} aday, {info['excluded']} hariç."
            self._sync_preview()

        imgui.same_line()
        if self.action_button("Clear##af_clear", 90, True):
            self.service.clear_draft(draft)
            self._status = "Draft temizlendi."
            self._sync_preview()

        imgui.same_line()
        selected_frames = self._selected_frames_from_scene()
        if self.action_button("Seçilileri Ekle##af_addsel", 150, bool(selected_frames)):
            ids = [int(f.unique_id) for f in selected_frames]
            info = self.service.add_selected_frames(self._selected_polygon(), draft, ids)
            self._status = f"{info['added']} seçili frame eklendi."
            self._sync_preview()

    def _selected_polygon(self) -> Polygon | None:
        if self.service is None or self._selected_polygon_id is None:
            return None
        return self.service.get_polygon(self._selected_polygon_id)

    # ------------------------------------------------------------------
    # 3. TABLE — assoc listesi + wind zone + grid
    # ------------------------------------------------------------------
    def draw_table(self) -> None:
        draft = self._draft
        if draft is None:
            return

        # --- Assoc listesi ---
        if imgui.collapsing_header(
            f"Hedef Frame'ler  (assoc: {len(draft.associated)} | hariç: {len(draft.excluded)})##af_assoc_hdr",
        ):
            self._draw_assoc_list_table(draft)

        # --- Wind zone ---
        polygon = self._selected_polygon()
        if polygon is not None:
            entries = self.service.list_wind_zones(polygon)
            if entries:
                if imgui.collapsing_header(
                    f"Rüzgar Zone Aktarımı ({len(entries)})##af_wind_hdr",
                ):
                    self._draw_wind_zone_table(polygon, entries)

        # --- Grid ayarları ---
        if imgui.collapsing_header("Grid Ayarları##af_grid_hdr"):
            self._draw_grid_section()

    def _draw_assoc_list_table(self, draft: AssocDraft) -> None:
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.7, 0.6, 1.0),
            "yeşil=assoc, kırmızı=hariç, sarı=seçili",
        )
        frames = self.service.list_frames()
        if not frames:
            imgui.text_disabled("Sahnede frame yok.")
            return

        imgui.checkbox("Tüm frame'leri göster##af_all", self._show_all_frames)
        visible_ids = (
            sorted(frames.keys()) if self._show_all_frames
            else sorted(draft.associated | draft.excluded)
        )

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
            | imgui.TableFlags_.scroll_y
        )
        if not imgui.begin_table("##af_assoc_tbl", 3, flags, imgui.ImVec2(0, 200)):
            return

        imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 32)
        imgui.table_setup_column("Frame", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("Durum", imgui.TableColumnFlags_.width_fixed, 80)
        imgui.table_headers_row()

        if not visible_ids:
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.text_disabled("Liste boş — Auto Assoc kullanın.")
        for uid in visible_ids:
            fr = frames.get(uid)
            if fr is None:
                continue
            on = uid in draft.associated
            is_excl = uid in draft.excluded

            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.push_id(f"af_{uid}")
            changed, new_on = imgui.checkbox("##chk", on)
            if changed:
                self.service.toggle(draft, uid, bool(new_on))
                self._sync_preview()
            imgui.pop_id()

            imgui.table_set_column_index(1)
            imgui.text(fr.label or f"Frame {uid}")

            imgui.table_set_column_index(2)
            if on:
                imgui.text_colored(imgui.ImVec4(0.4, 0.9, 0.5, 1.0), "assoc")
            elif is_excl:
                imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "hariç")
            else:
                imgui.text_disabled("—")

        imgui.end_table()

    def _draw_wind_zone_table(self, polygon: Polygon, entries: list) -> None:
        entry_keys = [(k, i) for k, i, _ in entries]
        if self._selected_wind_zone not in entry_keys:
            self._selected_wind_zone = entry_keys[0]
        sel = next(
            (e for e in entries if (e[0], e[1]) == self._selected_wind_zone),
            entries[0],
        )
        direction_key, zone_index, zone = sel

        imgui.push_item_width(280)
        if imgui.begin_combo("##af_wz", f"{direction_key} | {zone.label} ({zone_index + 1})"):
            for key, idx, item in entries:
                is_sel = (key, idx) == self._selected_wind_zone
                if imgui.selectable(f"{key} | {item.label} ({idx + 1})", is_sel)[1]:
                    self._selected_wind_zone = (key, idx)
            imgui.end_combo()
        imgui.pop_item_width()

        imgui.push_item_width(140)
        _, self._wind_cpe_index = imgui.combo(
            "Cpe türü##af_cpe", self._wind_cpe_index, ["Cpe10", "Cpe1"],
        )
        imgui.pop_item_width()

        imgui.push_item_width(140)
        _, self._cpi_positive = imgui.input_float("Cpi (+)##af_cpip", self._cpi_positive)
        imgui.pop_item_width()

        imgui.push_item_width(140)
        _, self._cpi_negative = imgui.input_float("Cpi (-)##af_cpim", self._cpi_negative)
        imgui.pop_item_width()

        if self.action_button("Rüzgar Zone Aktar##af_wind_transfer", 200, True):
            cpe_kind = "cpe10" if self._wind_cpe_index == 0 else "cpe1"
            result = self.service.transfer_wind_zone(
                polygon, direction_key, zone_index, zone,
                cpe_kind=cpe_kind,
                cpi_pos=self._cpi_positive,
                cpi_neg=self._cpi_negative,
            )
            self._handle_result(result)

    def _draw_grid_section(self) -> None:
        step, bins = self.service.get_grid_settings()
        if self._step_buffer is None:
            self._step_buffer = step
        if self._bins_buffer is None:
            self._bins_buffer = bins

        imgui.text(f"Grid adımı ({self.service.length_unit()})")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._step_buffer = imgui.input_float("##af_step", self._step_buffer, 1.0, 10.0)
        imgui.pop_item_width()

        imgui.text("Bin sayısı")
        imgui.same_line(180)
        imgui.push_item_width(120)
        _, self._bins_buffer = imgui.input_int("##af_bins", self._bins_buffer)
        imgui.pop_item_width()

        if self.action_button("Grid Ayarını Uygula##af_grid_apply", 180, True):
            self.service.set_grid_settings(self._step_buffer, self._bins_buffer)
            self._status = "Grid ayarları kaydedildi."

    # ------------------------------------------------------------------
    # 4. ACTIONS — transfer
    # ------------------------------------------------------------------
    def draw_actions(self) -> None:
        polygon = self._selected_polygon()
        if polygon is None:
            return

        summary = self.service.polygon_loads_summary(polygon)
        can_transfer = bool(summary["assigned_loads"])

        if self.action_button(
            "Seçili frame'lere aktar##af_transfer", 260, can_transfer,
        ):
            result = self.service.transfer_area_loads(polygon)
            self._handle_result(result)

        if not can_transfer:
            imgui.spacing()
            self.status_line(
                "⚠ Bu polygon üzerinde aktarılacak yük yok — Load Manager'dan yük atayın.",
                "warn",
            )

        if self._status:
            imgui.separator()
            imgui.text_wrapped(self._status)

    # ------------------------------------------------------------------
    # Yardımcılar
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

    def _handle_result(self, result: TransferResult) -> None:
        self._status = result.status
        if result.ok and result.touched_frames and callable(self.on_transfer_complete):
            self.on_transfer_complete(result.touched_frames)

    def _engine(self):
        return getattr(self.app, "engine", None) if self.app else None

    def _sync_preview(self) -> None:
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

    def _clear_preview(self) -> None:
        eng = self._engine()
        renderer = getattr(eng, "renderer", None) if eng else None
        if renderer is not None:
            renderer.set_assoc_preview(None)
        self._preview_active = False

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