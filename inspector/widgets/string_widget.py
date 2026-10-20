# inspector/widgets/string_widget.py

import imgui
from inspector.widgets.base import Widget, DrawContext


class StringWidget(Widget):
    kind = "string"

    def draw(self, field, ctx: DrawContext) -> bool:
        cur = ctx.get(field.key, "")
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_v = imgui.input_text(f"##{field.key}", str(cur or ""), 512)
        if changed:
            ctx.set(field.key, str(new_v))
        return changed