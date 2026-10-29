from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class FloatWidget(Widget):
    kind = "float"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, 0.0)
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-60 if field.unit else -1)
        changed, new_v = imgui.input_float(
            f"##{field.key}", float(cur or 0.0),
            step=getattr(field, "step", 0.0),
            format=getattr(field, "format", "%.3f"),
        )
        if field.unit:
            imgui.same_line()
            imgui.text_disabled(field.unit)
        if changed:
            ctx.set(field.key, float(new_v))
        return changed