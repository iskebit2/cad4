# ui/helpers/apply_bar.py
from __future__ import annotations

from typing import Callable

from imgui_bundle import imgui


def draw_apply_bar(
    dirty: bool,
    on_apply: Callable[[], None],
    on_reset: Callable[[], None],
) -> bool | None:
    imgui.push_style_var(imgui.StyleVar_.item_spacing, imgui.ImVec2(6, 4))

    if dirty:
        imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(1.0, 0.75, 0.3, 1.0))
        imgui.text("● Değişiklik var")
    else:
        imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(0.6, 0.6, 0.6, 1.0))
        imgui.text("○ Değişiklik yok")
    imgui.pop_style_color()

    imgui.same_line()

    avail = imgui.get_content_region_avail().x
    btn_w = 90.0
    if avail > btn_w * 2 + 12:
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + avail - btn_w * 2 - 12)

    imgui.begin_disabled(not dirty)
    if imgui.button("Apply", imgui.ImVec2(btn_w, 0)):
        on_apply()
    imgui.end_disabled()

    imgui.same_line()

    imgui.begin_disabled(not dirty)
    if imgui.button("Reset", imgui.ImVec2(btn_w, 0)):
        on_reset()
    imgui.end_disabled()

    imgui.pop_style_var()
    return None