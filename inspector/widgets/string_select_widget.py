# inspector/widgets/string_select_widget.py
from imgui_bundle import imgui

from inspector.widgets.base import Widget


class StringSelectWidget(Widget):
    """Katalog listesinden STRING seçer."""
    kind = "section_name_ref"   # veya "string_select"

    def draw(self, field, ctx):
        catalog = getattr(ctx, "catalog", None)
        choices = catalog.list_sections() if catalog else []
        if not choices:
            return False
        cur = ctx.get(field.key)
        cur_s = cur if isinstance(cur, str) else ""
        try:
            idx = choices.index(cur_s)
        except ValueError:
            idx = 0
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_idx = imgui.combo(f"##{field.key}", idx, choices)
        if changed and 0 <= new_idx < len(choices):
            ctx.set(field.key, choices[new_idx])
            return True
        return False