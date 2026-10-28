# inspector/widgets/string_widget.py
from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class StringWidget(Widget):
    kind = "string"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, "")
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_v = imgui.input_text(f"##{field.key}", str(cur or ""))
        if changed:
            ctx.set(field.key, str(new_v))
        return changed