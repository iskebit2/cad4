# inspector/widgets/info_widget.py
"""Salt okunur bilgi alanı — Section / Material / SD özeti."""
from __future__ import annotations

from imgui_bundle import imgui

from inspector.widgets.base import DrawContext, Widget


class InfoWidget(Widget):
    """Salt okunur bilgi alanı.

    `field.source_key` ("section" / "material" / "area_section") hangi
    nesnenin özetleneceğini belirler. SD section, rebar, time-dependent
    gibi tüm alt detayları gösterir.
    """
    kind = "info"

    def draw(self, field, ctx: DrawContext) -> bool:
        imgui.align_text_to_frame_padding()
        imgui.text(field.label or field.key)
        imgui.same_line(140)

        source_key = getattr(field, "source_key", "section")
        obj = ctx.get(source_key)

        if obj is None:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "(yok)")
            return False

        # Hangi tip? dict / Section / Material / AreaSection
        summary = self._build_summary(source_key, obj)
        if not summary:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0), "—")
            return False

        # Ana satır
        imgui.text_colored(
            imgui.ImVec4(0.65, 0.75, 0.55, 1.0),
            summary["headline"],
        )

        # Hover tooltip — detaylı özet
        if imgui.is_item_hovered() and summary.get("tooltip"):
            imgui.set_tooltip(summary["tooltip"])

        return False

    # ------------------------------------------------------------------
    def _build_summary(self, source_key: str, obj) -> dict:
        """Nesne tipine göre başlık + tooltip metni."""
        if source_key == "material":
            return self._material_summary(obj)
        if source_key == "area_section":
            return self._area_section_summary(obj)
        return self._section_summary(obj)

    # ------------------------------------------------------------------
    @staticmethod
    def _attr(o, key, default=None):
        if isinstance(o, dict):
            return o.get(key, default)
        return getattr(o, key, default)

    # ------------------------------------------------------------------
    def _section_summary(self, sec) -> dict:
        """Section özeti — SD, rebar, time-dependent dahil."""
        name = self._attr(sec, "name", "?")
        ptype = self._attr(sec, "profile_type", None)
        params = self._attr(sec, "profile_params", {}) or {}
        mat = self._attr(sec, "material", None)
        mat_name = self._attr(mat, "name", "-") if mat else "-"

        pstr = getattr(ptype, "name", str(ptype)) if ptype is not None else "?"
        sd = self._attr(sec, "sd_section", None)
        rebar_col = self._attr(sec, "rebar_column", {}) or {}
        rebar_beam = self._attr(sec, "rebar_beam", {}) or {}
        time_dep = self._attr(sec, "time_dependent", {}) or {}

        # --- Headline ---
        if sd is not None:
            n_shapes = len(sd.shapes or [])
            n_pts = sum(len(sh.points) for sh in (sd.shapes or []))
            headline = f"SD  [{n_shapes} shape, {n_pts} pt]  {mat_name}"
        elif pstr in ("RECT", "CUSTOM") and params:
            h = params.get("h", params.get("d", 0.0))
            b = params.get("b", 0.0)
            if h and b:
                headline = f"{pstr}  {h:g}×{b:g}  [{mat_name}]"
            else:
                headline = f"{pstr}  [{mat_name}]"
        else:
            headline = f"{pstr}  [{mat_name}]"

        # Rebar özeti (varsa)
        rebar_bits = []
        if rebar_col:
            n3 = rebar_col.get("num_bars3_dir", 0)
            n2 = rebar_col.get("num_bars2_dir", 0)
            bar = rebar_col.get("bar_size_l", "")
            if n3 and n2:
                rebar_bits.append(f"Kol: {n3}×{n2} {bar}")
        if rebar_beam:
            top = rebar_beam.get("top_left_area", 0.0)
            bot = rebar_beam.get("bot_left_area", 0.0)
            if top or bot:
                rebar_bits.append(f"Kiriş: A_top={top:g} A_bot={bot:g}")
        if rebar_bits:
            headline += "  " + " | ".join(rebar_bits)

        # --- Tooltip ---
        lines = [
            f"Ad: {name}",
            f"Tip: {pstr}",
            f"Malzeme: {mat_name}",
        ]

        if params:
            lines.append("Profil:")
            for k in ("h", "b", "tw", "tf", "t", "r", "ro", "ri",
                      "Area", "I33", "I22", "J"):
                v = params.get(k)
                if v is not None and v != 0:
                    lines.append(f"  {k} = {v:g}")

        if sd is not None:
            lines.append("")
            lines.append(f"SD Section:")
            lines.append(f"  Design: {sd.design_type}")
            lines.append(f"  nPolygon: {sd.n_polygon}")
            lines.append(f"  AxisAngle: {sd.axis_angle:g}°")
            lines.append(f"  Mesh: abs={sd.mesh_sz_abs:g} rel={sd.mesh_sz_rel:g}")
            for i, sh in enumerate(sd.shapes or []):
                lines.append(f"  Shape[{i}]: {sh.name} "
                             f"({len(sh.points)} pt, mat={sh.material or '—'})")

        if rebar_col:
            lines.append("")
            lines.append("Betonarme Kolon:")
            for k in ("rebar_mat_l", "rebar_mat_c", "reinf_config", "lat_reinf",
                      "cover", "num_bars3_dir", "num_bars2_dir",
                      "bar_size_l", "bar_size_c", "spacing_c", "reinf_type"):
                v = rebar_col.get(k)
                if v not in (None, "", 0, 0.0):
                    lines.append(f"  {k}: {v}")

        if rebar_beam:
            lines.append("")
            lines.append("Betonarme Kiriş:")
            for k in ("rebar_mat_l", "rebar_mat_c", "top_cover", "bot_cover",
                      "top_left_area", "top_rght_area",
                      "bot_left_area", "bot_rght_area"):
                v = rebar_beam.get(k)
                if v not in (None, "", 0, 0.0):
                    lines.append(f"  {k}: {v:g}" if isinstance(v, (int, float)) else f"  {k}: {v}")

        if time_dep:
            lines.append("")
            lines.append(f"Time Dependent: {time_dep}")

        lines.append("")
        lines.append("Düzenlemek için Definitions panelini kullan")

        return {"headline": headline, "tooltip": "\n".join(lines)}

    # ------------------------------------------------------------------
    def _material_summary(self, mat) -> dict:
        name = self._attr(mat, "name", "?")
        mtype = self._attr(mat, "mat_type", None)
        tstr = getattr(mtype, "name", str(mtype)) if mtype is not None else "?"

        E = self._attr(mat, "E1", 0.0)
        G = self._attr(mat, "G12", 0.0)
        nu = self._attr(mat, "nu12", 0.0)
        rho = self._attr(mat, "density", 0.0)

        headline = f"{tstr}  E={E:g}  ν={nu:g}  ρ={rho:.3g}"

        lines = [
            f"Ad: {name}",
            f"Tip: {tstr}",
            f"E = {E:g}",
            f"G = {G:g}",
            f"ν = {nu:g}",
            f"ρ = {rho:.3g}",
        ]

        fy = self._attr(mat, "fy", 0.0)
        fu = self._attr(mat, "fu", 0.0)
        if fy:
            lines.append(f"fy = {fy:g}")
        if fu:
            lines.append(f"fu = {fu:g}")

        fc = self._attr(mat, "fc", 0.0)
        if fc:
            lines.append(f"fc = {fc:g}")

        return {"headline": headline, "tooltip": "\n".join(lines)}

    # ------------------------------------------------------------------
    def _area_section_summary(self, sec) -> dict:
        name = self._attr(sec, "name", "?")
        ptype = self._attr(sec, "prop_type", None)
        pstr = getattr(ptype, "name", str(ptype)) if ptype is not None else "?"
        thickness = self._attr(sec, "thickness", 0.0)
        mat = self._attr(sec, "material", None)
        mat_name = self._attr(mat, "name", "-") if mat else "-"

        headline = f"{pstr}  t={thickness:g}  [{mat_name}]"

        lines = [
            f"Ad: {name}",
            f"Tip: {pstr}",
            f"Kalınlık: {thickness:g}",
            f"Malzeme: {mat_name}",
            f"AreaType: {self._attr(sec, 'area_type', '—')}",
            f"DrillDOF: {self._attr(sec, 'drill_dof', False)}",
        ]
        return {"headline": headline, "tooltip": "\n".join(lines)}