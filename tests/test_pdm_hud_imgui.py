import pytest
from imgui_bundle import imgui

from app.cad_app import CadApp


class PDM:
    STAGE_P0 = "p0"
    STAGE_P1 = "p1"
    STAGE_P2 = "p2"
    STAGE_DEPTH_PLUS = "depth+"
    STAGE_DEPTH_MINUS = "depth-"
    stage = STAGE_P0
    depth_plus = 100.0
    depth_minus = 50.0


def _mock_hud_imgui(monkeypatch, *, expanded=True, fail_text=False):
    calls = []
    monkeypatch.setattr(
        imgui, "get_io",
        lambda: type("IO", (), {"display_size": imgui.ImVec2(800, 600)})(),
    )
    monkeypatch.setattr(imgui, "set_next_window_pos", lambda *args: None)
    monkeypatch.setattr(imgui, "set_next_window_size", lambda *args: None)
    monkeypatch.setattr(
        imgui, "push_style_var",
        lambda idx, value: calls.append(("push", idx, value)),
    )
    monkeypatch.setattr(imgui, "begin", lambda *args: (expanded, True))
    monkeypatch.setattr(
        imgui, "text_colored",
        lambda *args: (
            (_ for _ in ()).throw(RuntimeError("text failure"))
            if fail_text else None
        ),
    )
    monkeypatch.setattr(imgui, "end", lambda: calls.append(("end",)))
    monkeypatch.setattr(
        imgui, "pop_style_var", lambda: calls.append(("pop",))
    )
    return calls


def test_pdm_hud_uses_valid_style_var_and_imgui_vector(monkeypatch):
    calls = _mock_hud_imgui(monkeypatch)

    CadApp._draw_pdm_hud(None, PDM())

    assert calls[0] == (
        "push", imgui.StyleVar_.window_padding, imgui.ImVec2(8, 8)
    )
    assert calls[-2:] == [("end",), ("pop",)]


def test_pdm_hud_balances_imgui_scopes_when_text_raises(monkeypatch):
    calls = _mock_hud_imgui(monkeypatch, fail_text=True)

    with pytest.raises(RuntimeError, match="text failure"):
        CadApp._draw_pdm_hud(None, PDM())

    assert calls[-2:] == [("end",), ("pop",)]
