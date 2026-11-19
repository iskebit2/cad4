# ui/widgets/status_bar.py
from __future__ import annotations

from imgui_bundle import imgui


def _v4(r: float, g: float, b: float, a: float = 1.0):
    return imgui.ImVec4(r, g, b, a)


def _format_selection(selected: list) -> str:
    if not selected:
        return "Seçim: Yok"
    if len(selected) == 1:
        el = selected[0]
        kind = type(el).__name__
        uid = getattr(el, "unique_id", "?")
        label = getattr(el, "label", "")
        suffix = f" ({label})" if label else ""
        return f"Seçim: {kind} #{uid}{suffix}"

    counts: dict[str, int] = {}
    for el in selected:
        kind = type(el).__name__
        counts[kind] = counts.get(kind, 0) + 1
    summary = ", ".join(f"{cnt} {k}" for k, cnt in counts.items())
    return f"Seçim: {len(selected)} eleman ({summary})"


class StatusBar:
    def __init__(self, height: float = 26.0) -> None:
        self.height = height
        self.last_key_text: str = "-"
        self.last_event_text: str = "Komut bekleniyor..."
        self.selection_text: str = "Seçim: Yok"

    def notify_key(self, key: int, action: int, mods: int) -> None:
        if action == 1:
            self.last_key_text = f"Key:{key} (mods:{mods})"
            self.last_event_text = f"Tuş basıldı -> {key}"

    def notify_command(self, text: str) -> None:
        self.last_event_text = text

    def notify_selection(self, selected: list) -> None:
        self.selection_text = _format_selection(selected)

    def draw(
        self,
        engine_connected: bool,
        app_status: str,
        mouse_pos: tuple[float, float],
        mouse_buttons: dict[int, bool],
        modifiers: int,
        fps: float,
        ucs_name: str = "Global",
        ucs_pos: tuple[float, float, float] | None = None,
    ) -> None:
        viewport = imgui.get_main_viewport()
        bar_pos = imgui.ImVec2(viewport.pos.x, viewport.pos.y + viewport.size.y - self.height)
        bar_size = imgui.ImVec2(viewport.size.x, self.height)

        imgui.set_next_window_pos(bar_pos)
        imgui.set_next_window_size(bar_size)

        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_docking
        )

        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(10.0, 4.0))
        imgui.push_style_color(imgui.Col_.window_bg, _v4(0.10, 0.12, 0.16, 0.96))

        if imgui.begin("##StatusBar", None, flags):
            if engine_connected:
                imgui.text_colored(_v4(0.25, 0.88, 0.45), "● Engine: BAĞLI")
            else:
                imgui.text_colored(_v4(0.92, 0.30, 0.30), "● Engine: YOK")

            imgui.same_line(spacing=14)
            imgui.text_disabled("|")
            imgui.same_line(spacing=14)

            imgui.text_colored(_v4(0.85, 0.88, 0.94), f"App: {app_status}")

            imgui.same_line(spacing=14)
            imgui.text_disabled("|")
            imgui.same_line(spacing=14)

            sel_color = _v4(0.40, 0.85, 1.00) if self.selection_text != "Seçim: Yok" else _v4(0.60, 0.64, 0.72)
            imgui.text_colored(sel_color, self.selection_text)

            imgui.same_line(spacing=14)
            imgui.text_disabled("|")
            imgui.same_line(spacing=14)

            mx, my = mouse_pos
            b_l = "L" if mouse_buttons.get(0) else "-"
            b_m = "M" if mouse_buttons.get(2) else "-"
            b_r = "R" if mouse_buttons.get(1) else "-"
            imgui.text(f"Mouse: ({mx:4.0f}, {my:4.0f}) [{b_l}{b_m}{b_r}]")

            imgui.same_line(spacing=14)
            imgui.text_disabled("|")
            imgui.same_line(spacing=14)

            if ucs_pos is not None:
                ux, uy, uz = ucs_pos
                imgui.text_colored(_v4(0.55, 0.90, 0.75), f"{ucs_name}: ({ux:8.1f}, {uy:8.1f}, {uz:6.1f})")
            else:
                imgui.text_disabled(f"{ucs_name}: (-, -, -)")

            mod_list = []
            if modifiers & 1:
                mod_list.append("SHIFT")
            if modifiers & 2:
                mod_list.append("CTRL")
            if modifiers & 4:
                mod_list.append("ALT")
            mod_str = "+".join(mod_list) if mod_list else "-"
            imgui.text_colored(_v4(0.95, 0.78, 0.30), f"{self.last_key_text} | Mods: {mod_str}")

            fps_text = f"{fps:5.1f} FPS"
            avail = imgui.get_content_region_avail().x
            text_w = imgui.calc_text_size(fps_text).x
            if avail > text_w + 10:
                imgui.same_line(spacing=avail - text_w)
            imgui.text_disabled(fps_text)

        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(2)