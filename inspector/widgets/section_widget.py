# inspector/widgets/section_widget.py
from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class SectionWidget(Widget):
    kind = "section_ref"

    def draw(self, field, ctx: DrawContext) -> bool:
        catalog = getattr(ctx, "catalog", None)
        if catalog is None:
            imgui.text_colored(imgui.ImVec4(0.8, 0.4, 0.4, 1.0), '(catalog yok)')
            return False

        names = catalog.list_sections()
        if not names:
            imgui.text_colored(imgui.ImVec4(0.7, 0.7, 0.5, 1.0), '(tanımlı section yok)')
            return False

        # "IPE300  [I 150×300]" gibi label
        labels = []
        for n in names:
            sec = catalog.get_section(n)
            ptype = getattr(sec, "profile_type", None)
            pstr = getattr(ptype, "value", str(ptype)) if ptype else "?"
            labels.append(f"{n}  [{pstr}]")

        cur = ctx.get(field.key)

        cur_name = getattr(cur, "name", "") if cur else ""
        try:
            idx = names.index(cur_name)
        except ValueError:
            idx = 0

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_idx = imgui.combo(f"##{field.key}", idx, labels)
        if changed and 0 <= new_idx < len(names):
            sec = catalog.get_section(names[new_idx])
            ctx.set(field.key, sec)   # ← Section nesnesi yazar
            return True
        return False