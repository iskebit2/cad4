# ui/panels/polygon/frame_transfer_tab.py
from __future__ import annotations

from copy import deepcopy
from typing import Any
from imgui_bundle import imgui

import app.commands as cmd
from domain.definition import FrameDistributedLoad
from domain.element import Frame
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame
from ui.base.inspector_panel import InspectorContext


def _summarize_load(load_set: FrameDistributedLoad | None) -> str:
    if load_set is None or not load_set.segments:
        return "—"
    qs: list[float] = []
    for seg in load_set.segments:
        qs.append(float(seg.q1))
        qs.append(float(seg.q2))
    q_min = min(qs)
    q_max = max(qs)
    if abs(q_max - q_min) <= 1e-6:
        return f"{q_max:+.3f}"
    return f"{q_min:+.3f} .. {q_max:+.3f}"


class FrameTransferTab:
    def __init__(self) -> None:
        self._poly_id: int | None = None
        self._include_area: bool = True
        self._wind_dir_idx: int = 0
        self._cpe_idx: int = 0
        self._cpi_pos: float = 0.2
        self._cpi_neg: float = -0.3
        self._staged: dict = {}
        self._cache_key = None 
        self._error: str = ""
        self._pattern_filter_idx: int = 0

    def draw(self, ctx: InspectorContext, polygon: Polygon, service: AreaToFrame) -> None:
        imgui.spacing()
        pid = int(polygon.unique_id)
        if self._poly_id != pid:
            self._poly_id = pid
            self._staged = {}
            self._error = ""
            self._pattern_filter_idx = 0

        ad = service.analysis_data(polygon)
        assoc_ids = sorted(int(fid) for fid in ad.associated_frame_ids)
        if not assoc_ids:
            imgui.text_disabled("Önce Frame Assoc sekmesinden hedef frame seçin.")
            return

        zone_dict = polygon.zone_children_by_direction or {}
        dir_keys = sorted(zone_dict.keys())
        wind_options = ["Yok"] + dir_keys
        if self._wind_dir_idx >= len(wind_options):
            self._wind_dir_idx = 0

        _, self._include_area = imgui.checkbox("Alan Yükleri##ft_inc_area", self._include_area)
        if dir_keys:
            imgui.same_line()
            imgui.push_item_width(120)
            _, self._wind_dir_idx = imgui.combo("Rüzgar##ft_wdir", self._wind_dir_idx, wind_options)
            imgui.pop_item_width()
            if self._wind_dir_idx > 0:
                imgui.same_line()
                imgui.push_item_width(85)
                _, self._cpe_idx = imgui.combo("##ft_cpe", self._cpe_idx, ["Cpe10", "Cpe1"])
                imgui.pop_item_width()
                imgui.push_item_width(90)
                _, self._cpi_pos = imgui.input_float("Cpi+##ft_cpip", self._cpi_pos, 0.0, 0.0, "%.2f")
                imgui.same_line()
                _, self._cpi_neg = imgui.input_float("Cpi-##ft_cpim", self._cpi_neg, 0.0, 0.0, "%.2f")
                imgui.pop_item_width()

        if imgui.button("Hesapla##ft_calc", imgui.ImVec2(120, 26)):
            self._recompute(polygon, service, wind_options)
        
        if not self._staged or self._staged == {}:
            imgui.spacing()
            imgui.text_disabled("Hesaplanmış yük satırı yok.")
            if self._error:
                imgui.text_colored(imgui.ImVec4(1.0, 0.45, 0.45, 1.0), self._error)
            return
        patterns = sorted({
                key[0] if isinstance(key, tuple) else key
                for pats in self._staged.values()
                for key in pats
            })
        if patterns:
            imgui.same_line()
            filter_items = ["Tümü"] + patterns
            if self._pattern_filter_idx >= len(filter_items):
                self._pattern_filter_idx = 0
            imgui.push_item_width(170)
            _, self._pattern_filter_idx = imgui.combo("##ft_pat_flt", self._pattern_filter_idx, filter_items)
            imgui.pop_item_width()

        if self._error:
            imgui.text_colored(imgui.ImVec4(1.0, 0.45, 0.45, 1.0), self._error)

        rows = self._build_rows(service, assoc_ids, patterns)
        if not rows:
            imgui.spacing()
            imgui.text_disabled("Hesaplanmış yük satırı yok.")
            return

        imgui.spacing()
        if imgui.small_button("Tümüne Add##ft_all_add"):
            self._emit_bulk(ctx, rows, "add")
        imgui.same_line()
        if imgui.small_button("Tümüne Replace##ft_all_rep"):
            self._emit_bulk(ctx, rows, "replace")
        imgui.same_line()
        if imgui.small_button("Tümünü Delete##ft_all_del"):
            self._emit_bulk(ctx, rows, "delete")

        unit_lbl = service.line_load_unit()
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("##ft_rows_tbl", 5, flags, imgui.ImVec2(0, 320)):
            return

        imgui.table_setup_column("Frame", imgui.TableColumnFlags_.width_fixed, 75)
        imgui.table_setup_column("Pattern", imgui.TableColumnFlags_.width_fixed, 125)
        imgui.table_setup_column(f"Mevcut ({unit_lbl})", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column(f"Hesaplanan ({unit_lbl})", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_column("İşlem", imgui.TableColumnFlags_.width_fixed, 155)
        imgui.table_headers_row()

        for row_idx, (fid, frame, pat, existing_ls, calc_ls) in enumerate(rows):
            imgui.push_id(f"ft_r_{row_idx}")
            imgui.table_next_row()

            imgui.table_set_column_index(0)
            flabel = getattr(frame, "label", None) or f"F_{fid}"
            if imgui.selectable(f"{flabel}##sel", False)[0] and frame is not None:
                self._open_frame_load_panel(ctx, frame, pat)

            imgui.table_set_column_index(1)
            imgui.text(pat)

            imgui.table_set_column_index(2)
            imgui.text(_summarize_load(existing_ls))

            imgui.table_set_column_index(3)
            imgui.text(_summarize_load(calc_ls))

            imgui.table_set_column_index(4)
            if calc_ls is not None:
                if imgui.small_button("Add"):
                    self._emit_single(ctx, fid, pat, calc_ls, "add")
                imgui.same_line()
                if imgui.small_button("Replace"):
                    self._emit_single(ctx, fid, pat, calc_ls, "replace")
                imgui.same_line()
            if existing_ls is not None:
                if imgui.small_button("Del"):
                    self._emit_single(ctx, fid, pat, calc_ls or existing_ls, "delete")

            imgui.pop_id()

        imgui.end_table()

    def _recompute(self, polygon, service, wind_options):
        
        self._error = ""
        wind_dir = wind_options[self._wind_dir_idx] if self._wind_dir_idx > 0 else None
        cpe_kind = "cpe10" if self._cpe_idx == 0 else "cpe1"
        ad = service.analysis_data(polygon)
        
        if not self._include_area and not wind_dir:
            self._staged = {}
            self._error = "En az bir yük kaynağı seçin."
            return
        if self._include_area and not ad.assigned_loads and not wind_dir:
            self._staged = {}
            self._error = "Polygon üzerinde atanmış alan yükü yok."
            return

        cache_key = (
            int(polygon.unique_id),
            bool(self._include_area),
            wind_dir,
            cpe_kind,
            float(self._cpi_pos),
            float(self._cpi_neg),
            tuple(sorted(int(fid) for fid in ad.associated_frame_ids)),
            tuple((l.pattern_name, l.direction, float(l.value)) for l in ad.assigned_loads),
            service.get_grid_settings(),
        )
        if getattr(self, "_cache_key", None) == cache_key and self._staged:
            return
        self._cache_key = cache_key

        result = service.compute_polygon_frame_loads(
            polygon,
            include_area_loads=self._include_area,
            wind_direction_key=wind_dir,
            cpe_kind=cpe_kind,
            cpi_pos=float(self._cpi_pos),
            cpi_neg=float(self._cpi_neg),
        )
        

        self._staged = result if result is not None else {}

    
    def _build_rows(
        self,
        service: AreaToFrame,
        assoc_ids: list[int],
        patterns: list[str],
    ) -> list[tuple[int, Frame | None, str, FrameDistributedLoad | None, FrameDistributedLoad | None]]:

        if not patterns:
            return []

        active_pat = None
        if 0 < self._pattern_filter_idx <= len(patterns):
            active_pat = patterns[self._pattern_filter_idx - 1]

        target_pats = [active_pat] if active_pat else patterns

        frames = service.math_model.frames if service.math_model else {}
        rows = []

        for fid in assoc_ids:
            frame = frames.get(int(fid))
            existing_sets = getattr(frame, "dist_load_sets", {}) if frame is not None else {}
            calc_sets = self._staged.get(int(fid), {})

            for key, calc_ls in calc_sets.items():
                pattern_name = key[0] if isinstance(key, tuple) else key

                if pattern_name not in target_pats:
                    continue

                # Mevcut yükü aynı pattern ve doğrultuda bul.
                existing_ls = next(
                            (
                                item for item in existing_sets.values()
                                if item.pattern_name == pattern_name
                                and item.coord_sys == calc_ls.coord_sys
                                and item.load_dir == calc_ls.load_dir
                                and getattr(item, "force_or_moment", "Force") == getattr(calc_ls, "force_or_moment", "Force")
                            ),
                            None,
                        )

                rows.append((
                    int(fid), frame, pattern_name, existing_ls, calc_ls
                ))

        return rows


    def _emit_single(self, ctx, fid, pat, load_set, mode):
        key = getattr(load_set, "key", None) or (
            load_set.pattern_name,
            load_set.load_dir,
            load_set.coord_sys,
            getattr(load_set, "force_or_moment", "Force"),
        )
        ctx.app.put_command(
            cmd.ApplyFrameTransferAction(
                staged_loads={int(fid): {key: deepcopy(load_set)}},
                mode=mode,
            )
        )

    def _emit_bulk(self, ctx, rows, mode):
        payload: dict[int, dict[Any, FrameDistributedLoad]] = {}
        for fid, _, pat, existing_ls, calc_ls in rows:
            target_ls = calc_ls if mode != "delete" else (calc_ls or existing_ls)
            if target_ls is None:
                continue
            key = getattr(target_ls, "key", None) or (
                target_ls.pattern_name,
                target_ls.load_dir,
                target_ls.coord_sys,
                getattr(target_ls, "force_or_moment", "Force"),
            )
            payload.setdefault(int(fid), {})[key] = deepcopy(target_ls)
        if payload:
            ctx.app.put_command(cmd.ApplyFrameTransferAction(staged_loads=payload, mode=mode))

    def _open_frame_load_panel(self, ctx: InspectorContext, frame: Frame, pattern_name: str) -> None:
        reg = getattr(ctx.app, "panel_registry", None)
        entry = reg.get("frame_load") if reg is not None else None
        if entry is None:
            return
        panel = entry.instance
        panel.open()
        panel.pattern_name = pattern_name
        panel.set_target_frames([frame])