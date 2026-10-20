# ui/widgets/section_preview.py
"""
Kesit 2D önizleme çizici.
Section.profile_type + profile_params + color'dan otomatik avatar üretir.
"""
import math
import imgui

from data.enums import SectionType



# ============================================================================
# YARDIMCI: Aspect-fit hesabı
# ============================================================================
def _fit_dims(params_w, params_h, avail_w, avail_h, margin=4.0):
    """
    Profil boyutlarını (w, h) verilen alana oranlı sığdır.
    Döndürür: (draw_w, draw_h, offset_x, offset_y)
    """
    if params_w <= 0 or params_h <= 0:
        return 0.0, 0.0, 0.0, 0.0

    avail_w -= 2 * margin
    avail_h -= 2 * margin

    scale = min(avail_w / params_w, avail_h / params_h)
    draw_w = params_w * scale
    draw_h = params_h * scale
    off_x = margin + (avail_w - draw_w) * 0.5
    off_y = margin + (avail_h - draw_h) * 0.5
    return draw_w, draw_h, off_x, off_y


def _color_u32(color, alpha=1.0):
    """(r, g, b) tuple → packed ImU32."""
    r = max(0, min(255, int(color[0] * 255)))
    g = max(0, min(255, int(color[1] * 255)))
    b = max(0, min(255, int(color[2] * 255)))
    a = max(0, min(255, int(alpha * 255)))
    return (a << 24) | (b << 16) | (g << 8) | r


def _color_u32_dark(color, factor=0.4, alpha=1.0):
    """Koyulaştırılmış renk — içi boş profillerde kenar için."""
    r = max(0, min(1, color[0] * factor))
    g = max(0, min(1, color[1] * factor))
    b = max(0, min(1, color[2] * factor))
    return _color_u32((r, g, b), alpha)


# ============================================================================
# PROFİL ÇİZİCİLERİ
# Her biri (draw_list, x0, y0, avail_w, avail_h, color, params) alır.
# x0, y0 → ekran koordinatı (sol üst köşe)
# ============================================================================
def _draw_rect(dl, x0, y0, aw, ah, color, p):
    b = float(p.get("b", 300.0))
    h = float(p.get("h", 600.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    dl.add_rect_filled(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + dh, _color_u32(color))
    dl.add_rect(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + dh,
                _color_u32_dark(color), thickness=1.0)


def _draw_circle(dl, x0, y0, aw, ah, color, p):
    d = float(p.get("d", 400.0))
    dw, dh, ox, oy = _fit_dims(d, d, aw, ah)
    cx = x0 + ox + dw * 0.5
    cy = y0 + oy + dh * 0.5
    r = dw * 0.5
    dl.add_circle_filled(cx, cy, r, _color_u32(color))
    dl.add_circle(cx, cy, r, _color_u32_dark(color), num_segments=48, thickness=1.0)


def _draw_pipe(dl, x0, y0, aw, ah, color, p):
    d = float(p.get("d", 400.0))
    t = float(p.get("t", 20.0))
    dw, dh, ox, oy = _fit_dims(d, d, aw, ah)
    cx = x0 + ox + dw * 0.5
    cy = y0 + oy + dh * 0.5
    r_out = dw * 0.5
    r_in = max(0.0, r_out * (1 - 2 * t / d)) if d > 0 else 0.0
    # Dış halka
    dl.add_circle_filled(cx, cy, r_out, _color_u32(color))
    # İç delik — arkaplan rengiyle
    dl.add_circle_filled(cx, cy, r_in, _color_u32((0.08, 0.10, 0.16)))
    # Kenar
    dl.add_circle(cx, cy, r_out, _color_u32_dark(color), num_segments=48, thickness=1.0)
    dl.add_circle(cx, cy, r_in, _color_u32_dark(color), num_segments=48, thickness=1.0)


def _draw_box(dl, x0, y0, aw, ah, color, p):
    b = float(p.get("b", 400.0))
    h = float(p.get("h", 400.0))
    t = float(p.get("t", 20.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    # Dış kutu
    dl.add_rect_filled(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + dh, _color_u32(color))
    # İç boşluk — kalınlık oranı
    if b > 0 and h > 0:
        inner_ox = dw * (t / b)
        inner_oy = dh * (t / h)
        if inner_ox > 0 and inner_oy > 0:
            dl.add_rect_filled(
                x0 + ox + inner_ox, y0 + oy + inner_oy,
                x0 + ox + dw - inner_ox, y0 + oy + dh - inner_oy,
                _color_u32((0.08, 0.10, 0.16))
            )
    # Kenar
    dl.add_rect(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + dh,
                _color_u32_dark(color), thickness=1.0)


def _draw_i(dl, x0, y0, aw, ah, color, p):
    h = float(p.get("h", 400.0))
    b = float(p.get("b", 200.0))
    tw = float(p.get("tw", 10.0))
    tf = float(p.get("tf", 15.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    # Ölçek katsayısı
    sx = dw / b if b > 0 else 1.0
    sy = dh / h if h > 0 else 1.0

    # Alt başlık
    dl.add_rect_filled(
        x0 + ox, y0 + oy + dh - tf * sy,
        x0 + ox + dw, y0 + oy + dh,
        _color_u32(color)
    )
    # Üst başlık
    dl.add_rect_filled(
        x0 + ox, y0 + oy,
        x0 + ox + dw, y0 + oy + tf * sy,
        _color_u32(color)
    )
    # Gövde (ortada)
    web_w = tw * sx
    web_x = x0 + ox + dw * 0.5 - web_w * 0.5
    dl.add_rect_filled(
        web_x, y0 + oy + tf * sy,
        web_x + web_w, y0 + oy + dh - tf * sy,
        _color_u32(color)
    )


def _draw_c(dl, x0, y0, aw, ah, color, p):
    h = float(p.get("h", 300.0))
    b = float(p.get("b", 100.0))
    tw = float(p.get("tw", 8.0))
    tf = float(p.get("tf", 12.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    sx = dw / b if b > 0 else 1.0
    sy = dh / h if h > 0 else 1.0

    # Üst başlık
    dl.add_rect_filled(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + tf * sy, _color_u32(color))
    # Alt başlık
    dl.add_rect_filled(x0 + ox, y0 + oy + dh - tf * sy, x0 + ox + dw, y0 + oy + dh, _color_u32(color))
    # Gövde (sol)
    dl.add_rect_filled(x0 + ox, y0 + oy + tf * sy, x0 + ox + tw * sx, y0 + oy + dh - tf * sy, _color_u32(color))


def _draw_l(dl, x0, y0, aw, ah, color, p):
    h = float(p.get("h", 100.0))
    b = float(p.get("b", 100.0))
    t = float(p.get("t", 10.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    sx = dw / b if b > 0 else 1.0
    sy = dh / h if h > 0 else 1.0

    # Dikey bacak
    dl.add_rect_filled(x0 + ox, y0 + oy, x0 + ox + t * sx, y0 + oy + dh, _color_u32(color))
    # Yatay bacak
    dl.add_rect_filled(x0 + ox, y0 + oy + dh - t * sy, x0 + ox + dw, y0 + oy + dh, _color_u32(color))


def _draw_t(dl, x0, y0, aw, ah, color, p):
    h = float(p.get("h", 200.0))
    b = float(p.get("b", 150.0))
    tw = float(p.get("tw", 8.0))
    tf = float(p.get("tf", 12.0))
    dw, dh, ox, oy = _fit_dims(b, h, aw, ah)
    sx = dw / b if b > 0 else 1.0
    sy = dh / h if h > 0 else 1.0

    # Üst başlık
    dl.add_rect_filled(x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + tf * sy, _color_u32(color))
    # Gövde
    web_w = tw * sx
    web_x = x0 + ox + dw * 0.5 - web_w * 0.5
    dl.add_rect_filled(web_x, y0 + oy + tf * sy, web_x + web_w, y0 + oy + dh, _color_u32(color))


def _draw_fallback(dl, x0, y0, aw, ah, color, p):
    """Bilinmeyen tip — gri dolu kutu."""
    dl.add_rect_filled(x0 + 4, y0 + 4, x0 + aw - 4, y0 + ah - 4,
                       _color_u32((0.4, 0.4, 0.45)))
    dl.add_rect(x0 + 4, y0 + 4, x0 + aw - 4, y0 + ah - 4,
                _color_u32_dark((0.6, 0.6, 0.7)), thickness=1.0)


# Tip → çizici eşleşmesi
_PROFILE_DRAWERS = {
    SectionType.RECT:    _draw_rect,
    SectionType.CIRCLE:  _draw_circle,
    SectionType.PIPE:    _draw_pipe,
    SectionType.BOX:     _draw_box,
    SectionType.TUBE:    _draw_box,   # TUBE ≈ BOX
    SectionType.I:       _draw_i,
    SectionType.C:       _draw_c,
    SectionType.CHANNEL: _draw_c,     # CHANNEL ≈ C
    SectionType.L:       _draw_l,
    SectionType.T:       _draw_t,
}


# ============================================================================
# ANA API
# ============================================================================
def draw_section_preview(section, avail_w: float = 160.0, avail_h: float = 120.0):
    """
    Verilen Section için 2D önizleme çizer.
    ImGui draw_list kullanır — çağrıldığı yere widget yerleştirir.

    Args:
        section: Section dataclass
        avail_w: Maksimum genişlik (piksel)
        avail_h: Maksimum yükseklik (piksel)
    """
    # Arkaplan kutusu
    dl = imgui.get_window_draw_list()
    cur_x, cur_y = imgui.get_cursor_screen_pos()

    # Arkaplan
    bg_col = _color_u32((0.10, 0.12, 0.18), 1.0)
    border_col = _color_u32((0.25, 0.30, 0.40), 1.0)
    dl.add_rect_filled(cur_x, cur_y, cur_x + avail_w, cur_y + avail_h, bg_col)
    dl.add_rect(cur_x, cur_y, cur_x + avail_w, cur_y + avail_h, border_col, thickness=1.0)

    # Profil çiz
    if section is None:
        return
    drawer = _PROFILE_DRAWERS.get(section.profile_type, _draw_fallback)
    color = tuple(section.color) if section.color else (0.7, 0.7, 0.7)
    try:
        drawer(dl, cur_x, cur_y, avail_w, avail_h, color, section.profile_params or {})
    except Exception:
        # Hata olursa fallback
        _draw_fallback(dl, cur_x, cur_y, avail_w, avail_h, color, {})

    # İmleci widget'ın altına taşı
    imgui.set_cursor_screen_pos((cur_x, cur_y + avail_h + 4))
    imgui.dummy(avail_w, avail_h)   # yer ayır