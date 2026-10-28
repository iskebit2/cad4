from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class EnumWidget(Widget):
    kind = "enum"

    def draw(self, field, ctx: DrawContext) -> bool:
        choices = field.choices or []
        cur = str(ctx.get(field.key, choices[0] if choices else ""))

        try:
            idx = choices.index(cur)
        except ValueError:
            idx = 0

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_idx = imgui.combo(f"##{field.key}", idx, choices)
        if changed and 0 <= new_idx < len(choices):
            ctx.set(field.key, choices[new_idx])
            return True
        return False