import imgui
from inspector.widgets.base import Widget, DrawContext
from inspector.schema_bridge import MIXED


class MixedWidget(Widget):
    """Herhangi bir field.kind için MIXED gösterimi."""
    kind = "_mixed"  # özel; registry'de direkt çağrılmaz

    def draw(self, field, ctx: DrawContext) -> bool:
        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)

        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, 0.30, 0.25, 0.10, 1.0)
        imgui.push_style_color(imgui.COLOR_TEXT, 0.95, 0.85, 0.45, 1.0)

        changed = False
        try:
            changed = self._draw_editor(field, ctx)
        finally:
            imgui.pop_style_color(2)

        return changed

    # ------------------------------------------------------------------
    def _draw_editor(self, field, ctx) -> bool:
        if field.kind == "bool":
            changed, new_v = imgui.checkbox(f"##m_{field.key}", False)
            Widget.mixed_marker()
            if changed:
                ctx.set(field.key, bool(new_v))
            return changed

        if field.kind == "float":
            changed, new_v = imgui.input_float(
                f"##m_{field.key}", 0.0,
                step=getattr(field, "step", 0.0),
                format=getattr(field, "format", "%.3f"),
            )
            Widget.mixed_marker()
            if changed:
                ctx.set(field.key, float(new_v))
            return changed

        if field.kind == "int":
            changed, new_v = imgui.input_int(f"##m_{field.key}", 0)
            Widget.mixed_marker()
            if changed:
                ctx.set(field.key, int(new_v))
            return changed

        if field.kind == "enum":
            choices = field.choices or []
            changed, idx = imgui.combo(f"##m_{field.key}", 0, choices)
            Widget.mixed_marker()
            if changed and 0 <= idx < len(choices):
                ctx.set(field.key, choices[idx])
            return changed

        if field.kind == "color":
            changed, (r, g, b) = imgui.color_edit3(f"##m_{field.key}", 0.5, 0.5, 0.5)
            Widget.mixed_marker()
            if changed:
                ctx.set(field.key, [r, g, b])
            return changed

        # str ve diğerleri: mixed buffer kullan
        buf = ctx.mixed_buffer.get(field.key, "")
        changed, new_v = imgui.input_text(
            f"##m_{field.key}", buf, 512,
            imgui.INPUT_TEXT_ENTER_RETURNS_TRUE,
        )
        Widget.mixed_marker()
        if changed:
            ctx.mixed_buffer[field.key] = new_v
            if new_v.strip():
                ctx.set(field.key, new_v)
                return True
        return False