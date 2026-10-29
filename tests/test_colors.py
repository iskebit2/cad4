import pytest
from tools.s2k.handlers._colors import color_from_string, NAMED_COLORS, DEFAULT_COLOR


@pytest.mark.parametrize("name,expected", [
    ("Red",         (1.0, 0.0, 0.0)),
    ("red",         (1.0, 0.0, 0.0)),
    ("RED",         (1.0, 0.0, 0.0)),
    ("Cyan",        (0.0, 1.0, 1.0)),
    ("Magenta",     (1.0, 0.0, 1.0)),
    ("Gray4",       (0.65, 0.65, 0.65)),
    ("Gray8Dark",   (0.25, 0.25, 0.25)),
    ("Gray1Light",  (0.95, 0.95, 0.95)),
    ("DarkRed",     (0.55, 0.0, 0.0)),
    ("white",       (1.0, 1.0, 1.0)),
])
def test_named_colors(name, expected):
    assert color_from_string(name) == expected


@pytest.mark.parametrize("bgr,expected", [
    (16776960, (0.0, 1.0, 1.0)),     # Cyan
    (255,      (1.0, 0.0, 0.0)),     # Red
    (65280,    (0.0, 1.0, 0.0)),     # Green
    (16711680, (0.0, 0.0, 1.0)),     # Blue
    (16711935, (1.0, 0.0, 1.0)),     # Magenta
])
def test_bgr_numeric(bgr, expected):
    assert color_from_string(bgr) == pytest.approx(expected, abs=1e-2)


@pytest.mark.parametrize("hexcol,expected", [
    ("#FF0000", (1.0, 0.0, 0.0)),
    ("#00FF00", (0.0, 1.0, 0.0)),
    ("#0000FF", (0.0, 0.0, 1.0)),
    ("#FFFF00", (1.0, 1.0, 0.0)),
])
def test_hex_colors(hexcol, expected):
    assert color_from_string(hexcol) == expected


def test_unknown_falls_back():
    assert color_from_string("Nonsense") == DEFAULT_COLOR
    assert color_from_string("") == DEFAULT_COLOR
    assert color_from_string(None) == DEFAULT_COLOR
    assert color_from_string("nan") == DEFAULT_COLOR


def test_all_named_colors_have_valid_range():
    for name, rgb in NAMED_COLORS.items():
        for c in rgb:
            assert 0.0 <= c <= 1.0, f"{name} geçersiz bileşen: {c}"