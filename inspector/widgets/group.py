from imgui_bundle import imgui

from inspector.widgets.base import DrawContext
from inspector.widgets.registry import widget_for_kind


class GroupDrawer:
    """Schema group'unu çizer. Widget değil, bir akış yardımcısı."""

    def __init__(self, open_groups: set):
        self.open_groups = open_groups

    def draw(self, gi: int, group, ctx: DrawContext) -> bool:
        key = f"grp_{gi}"
        is_open = key in self.open_groups

        arrow = "▼" if is_open else ">"
        header = f"{arrow}  {group.title}##hdr_{gi}"

        if imgui.selectable(header, False)[0]:
            if is_open:
                self.open_groups.discard(key)
                is_open = False
            else:
                self.open_groups.add(key)
                is_open = True

        changed_any = False
        if is_open:
            imgui.indent(16)
            for f in group.fields:
                if self._draw_field(f, ctx):
                    changed_any = True
            imgui.unindent(16)

        return changed_any

    # ------------------------------------------------------------------
    def _draw_field(self, field, ctx: DrawContext) -> bool:
        from inspector.schema_bridge import MIXED

        imgui.push_id(field.key)
        try:
            # MIXED -> mixed widget
            if ctx.get(field.key) == MIXED:
                from inspector.widgets.mixed_widget import MixedWidget
                return MixedWidget().draw(field, ctx)

            w = widget_for_kind(field.kind)
            if w is None:
                imgui.text_colored(imgui.ImVec4(0.9, 0.5, 0.5, 1.0), f'{field.label or field.key}: (desteklenmeyen kind={field.kind})')



                return False
            return w.draw(field, ctx)
        finally:
            imgui.pop_id()