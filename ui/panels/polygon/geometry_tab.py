# ui/panels/polygon/geometry_tab.py
from __future__ import annotations

from imgui_bundle import imgui
import app.commands as cmd

from data.enums import DistType, PolygonType
from domain.polygon import Polygon
from ui.base.inspector_panel import InspectorContext
from ui.widgets.color_picker import color_edit3


class GeometryTab:
    TYPES = ("GENERIC", "SURFACE", "ZONE", "SECTION_CUT", "LOAD_AREA")
    DIST_VALUES = (DistType.TWO_WAY, DistType.ONE_WAY_U1, DistType.ONE_WAY_U2)
    DIST_LABELS = ("Two way", "One way (U1)", "One way (U2)")

    def draw(self, ctx: InspectorContext, polygon: Polygon) -> None:
        imgui.spacing()
        cur_type = self.TYPES.index(polygon.poly_type.name) if polygon.poly_type.name in self.TYPES else 0
        changed_t, new_t = imgui.combo("Tip##sp_type", cur_type, list(self.TYPES))
        if changed_t:
            ctx.app.put_command(
                cmd.SetPolygonType([int(polygon.unique_id)], getattr(PolygonType, self.TYPES[new_t]))
            )

        cur_dist = self.DIST_VALUES.index(polygon.dist_type) if polygon.dist_type in self.DIST_VALUES else 0
        changed_d, new_d = imgui.combo("Dağıtım Yönü##sp_dist", cur_dist, list(self.DIST_LABELS))
        if changed_d:
            ctx.app.put_command(
                cmd.SetPolygonDistType([int(polygon.unique_id)], self.DIST_VALUES[new_d])
            )

        rgb = list(polygon.color[:3]) if polygon.color else [0.8, 0.3, 0.8]
        changed_c, new_rgb = color_edit3("Renk##sp_color", rgb)
        if changed_c:
            alpha = polygon.color[3] if polygon.color and len(polygon.color) > 3 else 1.0
            ctx.app.put_command(
                cmd.SetPolygonColor([int(polygon.unique_id)], [*new_rgb, alpha])
            )

        imgui.spacing()
        imgui.text(f"Köşe Sayısı: {len(polygon.nodes)}")
        imgui.text(f"İlişkili Frame: {len(polygon.associated)} | Hariç: {len(polygon.excluded)}")

        imgui.spacing()
        if imgui.button("Plane Düzlemine Dönüştür##sp_toplane", imgui.ImVec2(-1, 0)):
            ctx.app.put_command(cmd.PolygonToPlane(int(polygon.unique_id)))