import imgui
from inspector.widgets.base import Widget, DrawContext


class LinkPropWidget(Widget):
    """Link.propname — string isim yazar (LinkProp nesnesi değil)."""
    kind = "link_prop_ref"

    def draw(self, field, ctx: DrawContext) -> bool:
        catalog = getattr(ctx, "catalog", None)
        if catalog is None:
            imgui.text_colored("(catalog yok)", 0.8, 0.4, 0.4, 1.0)
            return False

        names = catalog.list_link_props()
        if not names:
            imgui.text_colored("(tanımlı link prop yok)", 0.7, 0.7, 0.5, 1.0)
            return False

        labels = []
        for n in names:
            lp = catalog.get_link_prop(n) if hasattr(catalog, "get_link_prop") else None
            pt = getattr(lp, "prop_type", None) if lp else None
            tstr = getattr(pt, "name", str(pt)) if pt is not None else "?"
            labels.append(f"{n}  [{tstr}]")

        # Link.propname STRING — Section/Material gibi nesne değil
        cur = ctx.get(field.key)
        if isinstance(cur, dict):
            cur_name = cur.get("name", "")
        else:
            cur_name = str(cur) if cur else ""
        try:
            idx = names.index(cur_name)
        except ValueError:
            idx = 0

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_idx = imgui.combo(f"##{field.key}", idx, labels)
        if changed and 0 <= new_idx < len(names):
            ctx.set(field.key, names[new_idx])   # string!
            return True
        return False