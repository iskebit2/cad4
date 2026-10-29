from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class Tuple3Widget(Widget):
    """(x, y, z) tuple için üçlü input."""
    kind = "tuple3"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, (0.0, 0.0, 0.0))
        if not isinstance(cur, (tuple, list)) or len(cur) != 3:
            cur = (0.0, 0.0, 0.0)

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-60 if field.unit else -1)
        changed, new_vals = imgui.input_float3(
            f"##{field.key}",
            [float(cur[0]), float(cur[1]), float(cur[2])],
            format=getattr(field, "format", "%.3f"),
        )
        if field.unit:
            imgui.same_line()
            imgui.text_disabled(field.unit)
        if changed:
            ctx.set(field.key, tuple(new_vals))
        return changed