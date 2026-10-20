import imgui
from inspector.widgets.base import Widget, DrawContext


class ListObjectWidget(Widget):
    kind = "list_object"

    def draw(self, field, ctx: DrawContext) -> bool:
        # Runtime import — circular import kırıcı
        from inspector.widgets.registry import widget_for_kind

        items = ctx.get(field.key, []) or []
        imgui.align_text_to_frame_padding()
        imgui.text(field.label or field.key)

        changed_any = False
        imgui.indent(12)

        for idx, item in enumerate(items):
            imgui.push_id(f"{field.key}#{idx}")

            title = item.get("pattern_name") or item.get("label") or f"[{idx}]"
            val = item.get("value")
            header = f"[{idx + 1}] {title}" + (f"  (v={val})" if val is not None else "")

            opened, _ = imgui.collapsing_header(header)
            if opened and field.item_schema:
                imgui.indent(12)
                for sub_f in field.item_schema:
                    sub_key = f"{field.key}.{idx}.{sub_f.key}"
                    sub_widget = widget_for_kind(sub_f.kind)
                    if sub_widget is None:
                        continue
                    if sub_widget.draw(_with_key(sub_f, sub_key), ctx):
                        changed_any = True
                imgui.unindent(12)

            imgui.pop_id()

        imgui.unindent(12)
        return changed_any


def _with_key(field, new_key):
    class _F:
        pass
    f = _F()
    f.__dict__.update(field.__dict__)
    f.key = new_key
    return f