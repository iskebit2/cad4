# ui/panels/polygon/wind_zones_tab.py
from __future__ import annotations
from statistics import mean

from imgui_bundle import imgui
import app.commands as cmd
from core.units import Dimension, UnitSystem, convert_value
from domain.polygon import Polygon
from ui.base.inspector_panel import InspectorContext


class WindZonesTab:
    def __init__(self) -> None:
        self._dir_idx: int = 0
        self._cpe_idx: int = 0
        self._cpi_pos: float = 0.2
        self._cpi_neg: float = -0.3

    def draw(self, ctx: InspectorContext, polygon: Polygon) -> None:
        imgui.spacing()
        zone_dict = polygon.zone_children_by_direction or {}
        if not zone_dict:
            imgui.text_disabled("Bu polygon için rüzgar zone verisi yok.")
            return

        dir_keys = sorted(zone_dict.keys())
        if self._dir_idx >= len(dir_keys):
            self._dir_idx = 0

        _, self._dir_idx = imgui.combo("Rüzgar Yönü##sp_wz_dir", self._dir_idx, dir_keys)
        active_dir = dir_keys[self._dir_idx]
        polygon.show_zones_direction = active_dir

        _, self._cpe_idx = imgui.combo("Cpe Türü##sp_wz_cpe", self._cpe_idx, ["Cpe10", "Cpe1"])
        _, self._cpi_pos = imgui.input_float("Cpi (+)##sp_wz_cpip", self._cpi_pos)
        _, self._cpi_neg = imgui.input_float("Cpi (-)##sp_wz_cpim", self._cpi_neg)
        if imgui.button("Hide##sp_hide", imgui.ImVec2(80, 0)):
            ctx.app.put_command(cmd.ToggleZones(enabled=None))
        project = ctx.project
        pressure_result = project.loads.wind_results.get(active_dir) if project else None
        q_p = float(getattr(pressure_result, "q_p", 0.0)) if pressure_result is not None else 100.0

        unit_sys = project.unit_system if project else UnitSystem.KN_M
        area_unit = f"{unit_sys.force_unit}/{unit_sys.length_unit}²"
        imgui.text_disabled(f"q_p= {q_p:.3f} kN/m2.. unit_sys: {unit_sys} area_unit: {area_unit}")
        
        zones = zone_dict.get(active_dir, [])
        flags = (
                    imgui.TableFlags_.borders
                    | imgui.TableFlags_.row_bg
                    | imgui.TableFlags_.sizing_stretch_prop
                    | imgui.TableFlags_.resizable
                    | imgui.TableFlags_.reorderable
                    | imgui.TableFlags_.hideable
                )
        if imgui.begin_table("##sp_wz_tbl", 4, flags, imgui.ImVec2(0, 220)):
            imgui.table_setup_column("Bölge", imgui.TableColumnFlags_.width_fixed, 65)
            imgui.table_setup_column("Cpe", imgui.TableColumnFlags_.width_fixed, 95)
            # imgui.table_setup_column(f"Yük ({area_unit})", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column(f"Yük ({area_unit})")
            imgui.table_setup_column("İşlem", imgui.TableColumnFlags_.width_fixed, 60)
            imgui.table_headers_row()

            cpe_key = "cpe10" if self._cpe_idx == 0 else "cpe1"
            ovr_key = "cpe10_override" if self._cpe_idx == 0 else "cpe1_override"

            for zi, z_dict in enumerate(zones):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(str(z_dict.get("label", "")))

                raw_coefs = z_dict.get(ovr_key) or z_dict.get(cpe_key, (0.0, 0.0))
                if isinstance(raw_coefs, (int, float)):
                    c_min = c_max = float(raw_coefs)
                else:
                    vals = tuple(float(v) for v in raw_coefs)
                    c_min = vals[0]
                    c_max = vals[1] if len(vals) > 1 else vals[0]

                imgui.table_set_column_index(1)
                imgui.text(f"{c_min:+.2f}/{c_max:+.2f}")

                imgui.table_set_column_index(2)
                if q_p > 0.0:
                    w_vals = [
                        float(
                            convert_value(
                                Dimension.AREA_LOAD,
                                q_p * (cpe - cpi),
                                UnitSystem.KN_M,
                                unit_sys,
                            )
                        )
                        for cpe in (c_min, c_max)
                        for cpi in (self._cpi_pos, self._cpi_neg)
                    ]
                    imgui.text(f"{min(w_vals):+.3f} .. {mean(w_vals):+.3f} .. {max(w_vals):+.3f}")
                else:
                    imgui.text("—")

                imgui.table_set_column_index(3)
                if z_dict.get("cpe10_override") or z_dict.get("cpe1_override"):
                    if imgui.small_button(f"Sıfırla##wz_rst_{zi}"):
                        ctx.app.put_command(
                            cmd.ResetWindZoneOverride(int(polygon.unique_id), active_dir, zi)
                        )
            imgui.end_table()