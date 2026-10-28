from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class ListWidget(Widget):
    """Sadece okunabilir liste (ör. bağlı eleman ID'leri)."""
    kind = "list"

    MAX_SHOWN = 50

    def draw(self, field, ctx: DrawContext) -> bool:
        items = ctx.get(field.key, []) or []
        imgui.align_text_to_frame_padding()
        imgui.text(field.label or field.key)
        imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.7, 1.0), f'({len(items)} eleman)')

        imgui.indent(12)
        for item in items[: self.MAX_SHOWN]:
            imgui.bullet_text(str(item))
        if len(items) > self.MAX_SHOWN:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), f'...ve {len(items) - self.MAX_SHOWN} tane daha')



        imgui.unindent(12)
        return False  # read-only