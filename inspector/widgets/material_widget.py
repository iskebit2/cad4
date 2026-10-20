import imgui
from inspector.widgets.base import Widget, DrawContext


class MaterialWidget(Widget):
    """Area.material — Material nesnesi yazar."""
    kind = "material_ref"

    def draw(self, field, ctx: DrawContext) -> bool:
        catalog = getattr(ctx, "catalog", None)
        if catalog is None:
            imgui.text_colored("(catalog yok)", 0.8, 0.4, 0.4, 1.0)
            return False

        names = catalog.list_materials()
        if not names:
            imgui.text_colored("(tanımlı malzeme yok)", 0.7, 0.7, 0.5, 1.0)
            return False

        # "S275  [STEEL]" gibi
        labels = []
        for n in names:
            mat = catalog.get_material(n)
            mt = getattr(mat, "mat_type", None)
            tstr = getattr(mt, "name", str(mt)) if mt is not None else "?"
            labels.append(f"{n}  [{tstr}]")

        cur = ctx.get(field.key)
        if cur is None:
            cur_name = ""
        elif isinstance(cur, dict):
            cur_name = cur.get("name", "")
        else:
            cur_name = getattr(cur, "name", "")
        try:
            idx = names.index(cur_name)
        except ValueError:
            idx = 0

        Widget.label_row(field.label or field.key)
        imgui.set_next_item_width(-1)
        changed, new_idx = imgui.combo(f"##{field.key}", idx, labels)
        if changed and 0 <= new_idx < len(names):
            mat = catalog.get_material(names[new_idx])
            ctx.set(field.key, mat)
            return True
        return False