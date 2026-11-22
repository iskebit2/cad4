# tests/test_analysis_panel.py
"""Analiz panelini gerçek cad4 projesiyle uçtan uca test et."""
from __future__ import annotations
import numpy as np


def test_build_and_analyse():
    from tests.test_model import HeadlessContext, build_structure
    from app.commands.analysis.run import AnalysisOptions, AnalysisService

    # 1) Model kurulumu (test_model.py'deki fonksiyon aynen kullanılıyor)
    ctx = HeadlessContext()
    project = build_structure(ctx)

    # 2) Panelin çalıştıracağı servis (headless)
    opts = AnalysisOptions(
        n_live=0.3,
        n_modes=6,
        run_modal=True,
        run_spectral=False,
        run_takeoff=True,
        spectrum_name=None,
    )
    bundle = AnalysisService.run(project.math_model, project, opts)

    # 3) Sonuç doğrulamaları
    assert bundle.result is not None, f"Analiz hatası: {bundle.errors}"
    assert not bundle.errors, f"Uyarılar: {bundle.errors}"

    # -- DEAD toplam FZ ~95 kN olmalı (yoğunluk düzeltmesinden sonra)
    dead = bundle.result.static_results["DEAD"]
    total_fz = -dead.applied_forces.reshape(-1, 6)[:, 2].sum() / 1000.0
    print(f"DEAD toplam FZ = {total_fz:.2f} kN")
    assert 70.0 < total_fz < 130.0, f"DEAD FZ={total_fz:.1f} kN (beklenen ~95)"

    # -- LIVE toplam FZ ~140 kN olmalı
    live = bundle.result.static_results["LIVE"]
    total_fz = -live.applied_forces.reshape(-1, 6)[:, 2].sum() / 1000.0
    print(f"LIVE toplam FZ = {total_fz:.2f} kN")
    assert 130.0 < total_fz < 150.0

    # -- Denge: applied + reactions = 0
    for case in ("DEAD", "LIVE"):
        r = bundle.result.static_results[case]
        applied = r.applied_forces.reshape(-1, 6).sum(axis=0)
        reacted = r.reactions.reshape(-1, 6).sum(axis=0)
        bal = applied + reacted
        assert np.allclose(bal[:3], 0, atol=1.0), f"{case} kuvvet dengesi: {bal[:3]}"
        assert np.allclose(bal[3:], 0, atol=1.0), f"{case} moment dengesi: {bal[3:]}"

    # -- Modal
    modal = bundle.result.modal
    assert modal is not None
    print(f"T1 = {modal.periods[0]:.4f} s, f1 = {modal.frequencies[0]:.3f} Hz")
    assert 0.05 < modal.periods[0] < 5.0
    assert np.all(np.diff(modal.frequencies) >= -1e-6)

    # -- Metraj
    tk = bundle.takeoff
    assert tk is not None
    print(
        f"Toplam kütle: {tk.total_mass_kg:.1f} kg "
        f"({tk.total_mass_ton:.3f} ton), "
        f"ağırlık: {tk.total_weight_kN:.2f} kN"
    )
    assert 2000 < tk.total_mass_kg < 25000
    assert 20.0 < tk.total_weight_kN < 250.0

    # -- Panel bundle alanları
    assert bundle.result is not None
    assert bundle.takeoff is not None
    print("\n✓ Panel bundle tüm alanları dolu, tüm testler geçti.")


if __name__ == "__main__":
    test_build_and_analyse()