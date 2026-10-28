from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class BoolWidget(Widget):
    kind = "bool"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, False)
        Widget.label_row(field.label or field.key)
        changed, new_v = imgui.checkbox(f"##{field.key}", bool(cur))
        if changed:
            ctx.set(field.key, bool(new_v))
        return changed