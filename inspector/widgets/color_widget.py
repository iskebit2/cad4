from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class ColorWidget(Widget):
    kind = "color"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, [0.5, 0.5, 0.5])
        if not isinstance(cur, (list, tuple)) or len(cur) < 3:
            cur = [0.5, 0.5, 0.5]
        r, g, b = float(cur[0]), float(cur[1]), float(cur[2])

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, color = imgui.color_edit3(f"##{field.key}", [r, g, b])
        if changed:
            ctx.set(field.key, color)
        return changed