# inspector/widgets/info_widget.py
from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class InfoWidget(Widget):
    """Salt okunur bilgi alanı. `field.getter` ile veriyi çeker."""
    kind = "info"

    def draw(self, field, ctx: DrawContext) -> bool:
        imgui.align_text_to_frame_padding()
        imgui.text(field.label or field.key)
        imgui.same_line(140)

        source_key = getattr(field, "source_key", "section")
        sec = ctx.get(source_key)

        # --- Güvenli erişim ---
        if sec is None:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), '(yok)')
            return False

        # dict ise attribute yerine dict-erişimi kullan
        def _attr(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        name = _attr(sec, "name", "?")
        ptype = _attr(sec, "profile_type", None)
        params = _attr(sec, "profile_params", {}) or {}
        pstr = getattr(ptype, "value", str(ptype)) if ptype is not None else "?"

        parts = [pstr]
        for k in ("b", "h", "tw", "tf", "t", "r", "ro", "ri"):
            v = params.get(k) if isinstance(params, dict) else None
            if v is not None:
                parts.append(f"{k}={float(v):g}")

        imgui.text_colored(imgui.ImVec4(0.65, 0.75, 0.55, 1.0), '  '.join(parts))
        if imgui.is_item_hovered():
            mat = _attr(sec, "material", None)
            mat_name = _attr(mat, "name", "-") if mat else "-"
            imgui.set_tooltip(f"Ad: {name}\nMalzeme: {mat_name}\n"
                            "Düzenlemek için Definitions panelini kullan")
        return False