# ui/panels/polygon/frame_assoc_tab.py
from __future__ import annotations

from imgui_bundle import imgui
import app.commands as cmd
from app.commands import polygon_commands as PLC
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame, AssocDraft, AssocPreview
from ui.base.inspector_panel import InspectorContext


class FrameAssocTab:
    
    def __init__(self) -> None:
        self.draft: AssocDraft | None = None
        self._show_all: bool = False

    def ensure_draft(self, service: AreaToFrame, polygon: Polygon) -> AssocDraft:
        if self.draft is None or self.draft.polygon_id != int(polygon.unique_id):
            self.draft = service.new_draft(polygon)
        return self.draft

    def build_preview(self) -> AssocPreview | None:
        if self.draft is None:
            return None
        return AssocPreview(
            polygon_id=self.draft.polygon_id,
            associated=set(self.draft.associated),
            excluded=set(self.draft.excluded),
            active=True,
        )

    def draw(self, ctx: InspectorContext, polygon: Polygon, service: AreaToFrame) -> bool:
        draft = self.ensure_draft(service, polygon)
        preview_dirty = False

        imgui.spacing()
        imgui.text_colored(
            imgui.ImVec4(0.3, 0.9, 0.3, 1.0),
            f"Assoc: {len(draft.associated)} | Hariç: {len(draft.excluded)}",
        )

        if imgui.button("Apply##sp_apply", imgui.ImVec2(90, 0)) and draft.dirty:
            ctx.app.put_command(
                cmd.ApplyPolygonAssoc(
                    polygon_id=int(polygon.unique_id),
                    associated=set(draft.associated),
                    excluded=set(draft.excluded),
                )
            )
            draft.dirty = False
            preview_dirty = True
        imgui.same_line()
        if imgui.button("Cancel##sp_cancel", imgui.ImVec2(90, 0)):
            service.cancel_assoc(polygon, draft)
            preview_dirty = True
        imgui.same_line()
        if imgui.button("Auto Assoc##sp_auto", imgui.ImVec2(110, 0)):
            service.auto_assoc(polygon, draft, keep_excluded=True)
            preview_dirty = True
        imgui.same_line()
        if imgui.button("Clear##sp_clear", imgui.ImVec2(80, 0)):
            service.clear_draft(draft)
            preview_dirty = True
        imgui.same_line()
        if imgui.button("Hide##sp_hide", imgui.ImVec2(80, 0)):
            ctx.app.put_command(cmd.TogglePolygon(enabled=None))
        imgui.separator()
        _, self._show_all = imgui.checkbox("Tüm frame'leri göster##sp_all", self._show_all)

        frames = ctx.project.math_model.frames if ctx.project else {}
        visible_ids = (
            sorted(frames.keys())
            if self._show_all
            else sorted(draft.associated | draft.excluded)
        )

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
            | imgui.TableFlags_.scroll_y
        )
        if imgui.begin_table("##sp_assoc_tbl", 3, flags, imgui.ImVec2(0, 260)):
            imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 32)
            imgui.table_setup_column("Frame", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("Durum", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_headers_row()
            for uid in visible_ids:
                fr = frames.get(uid)
                if fr is None:
                    continue
                on = uid in draft.associated
                is_excl = uid in draft.excluded
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.push_id(f"sp_{uid}")
                changed, new_on = imgui.checkbox("##chk", on)
                if changed:
                    service.toggle(draft, uid, bool(new_on))
                    preview_dirty = True
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

        return preview_dirty