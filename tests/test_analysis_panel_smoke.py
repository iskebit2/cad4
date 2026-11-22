# tests/test_analysis_panel_smoke.py
"""Panelin UI yaşam döngüsünü headless olarak doğrula (imgui context gerekmez)."""
from ui.panels.analysis_panel import AnalysisManagerPanel
from tests.test_model import HeadlessContext, build_structure


def test_panel_lifecycle():
    ctx = HeadlessContext()
    build_structure(ctx)

    panel = AnalysisManagerPanel(app=ctx)

    # Yaşam döngüsü
    panel.open()
    assert panel.visible
    panel.set_context({"app": ctx})
    assert not panel._is_running
    assert panel._spectrum_names == []  # projede spektrum yok

    # Sınıf meta
    assert panel.panel_name == "analysis_manager"
    assert panel.uses_draft is False
    assert panel.show_apply_bar is False
    assert panel.context == ("app",)

    # Context'ten app'i çekmiş olmalı
    assert panel.app is ctx
    assert panel._project() is ctx.current_project
    assert panel._scene() is not None

    panel.close()
    assert not panel.visible