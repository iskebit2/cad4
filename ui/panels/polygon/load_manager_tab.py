# ui/panels/polygon/load_manager_tab.py
from __future__ import annotations

from imgui_bundle import imgui
import app.commands as cmd
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame
from ui.base.inspector_panel import InspectorContext


class LoadManagerTab:
    def draw(self, ctx: InspectorContext, polygon: Polygon, service: AreaToFrame) -> None:
        imgui.spacing()
        ad = service.analysis_data(polygon)
        loads = ad.assigned_loads

        if not loads:
            imgui.text_disabled("Atanmış alan yükü yok.")
            return

        flags = imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.sizing_stretch_prop
        if imgui.begin_table("##sp_loads_tbl", 4, flags, imgui.ImVec2(0, 260)):
            imgui.table_setup_column("Pattern", imgui.TableColumnFlags_.width_fixed, 90)
            imgui.table_setup_column("Değer", imgui.TableColumnFlags_.width_fixed, 100)
            imgui.table_setup_column("Yön", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("", imgui.TableColumnFlags_.width_fixed, 32)
            imgui.table_headers_row()
            for idx, load in enumerate(loads):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(load.pattern_name)
                imgui.table_set_column_index(1)
                imgui.text(f"{load.value:+.3f} {service.area_load_unit()}")
                imgui.table_set_column_index(2)
                imgui.text(load.direction.value)
                imgui.table_set_column_index(3)
                imgui.push_id(f"rm_al_{idx}")
                if imgui.small_button("X"):
                    ctx.app.put_command(
                        cmd.RemovePolygonAreaLoad(int(polygon.unique_id), idx)
                    )
                imgui.pop_id()
            imgui.end_table()