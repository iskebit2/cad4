import imgui
from inspector.widgets.base import Widget, DrawContext


class IntWidget(Widget):
    kind = "int"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, 0)
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_v = imgui.input_int(f"##{field.key}", int(cur or 0))
        if changed:
            ctx.set(field.key, int(new_v))
        return changed