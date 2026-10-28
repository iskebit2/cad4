# core/analysis/run.py
"""
Yüksek seviye analiz servisi — UI'nin tek giriş noktası.

    from core.analysis.run import AnalysisService
    result = AnalysisService.run(scene, project, options)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.analysis.material_takeoff import TakeoffResult, compute_takeoff
from core.analysis.modal_analysis import SpectralResult
from core.analysis.structuralanalysis import StructuralAnalysisResult, run_analysis


@dataclass
class AnalysisOptions:
    n_live: float = 0.3
    n_modes: int = 12
    run_modal: bool = True
    run_spectral: bool = False
    run_takeoff: bool = True
    spectrum_name: str | None = None     # project.spectrum_functions'tan
    use_shear_deform: bool = True


@dataclass
class AnalysisBundle:
    options: AnalysisOptions
    result: StructuralAnalysisResult | None = None
    spectral: SpectralResult | None = None
    takeoff: TakeoffResult | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.result is not None and not self.errors


class AnalysisService:
    @staticmethod
    def run(scene, project, options: AnalysisOptions) -> AnalysisBundle:
        bundle = AnalysisBundle(options=options)

        # --- Spektrum ---
        spectrum = None
        if options.run_spectral:
            if options.spectrum_name:
                spectrum = project.spectrum_functions.get(options.spectrum_name)
                if spectrum is None:
                    bundle.errors.append(
                        f"Spektrum bulunamadı: {options.spectrum_name}"
                    )
            # Yoksa default TBDY parametrelerinden üret
            if spectrum is None and not bundle.errors:
                bundle.errors.append(
                    "Spektrum seçilmedi — spectral atlandı"
                )

        # --- Ana analiz ---
        try:
            bundle.result = run_analysis(
                scene, project,
                n_live=options.n_live,
                n_modes=options.n_modes,
                spectrum=spectrum,
                validate=True,
            )
            if bundle.result.modal is None:
                bundle.errors.append("Modal sonuç üretilemedi")
            if spectrum is not None and bundle.result.spectral is not None:
                bundle.spectral = bundle.result.spectral
        except Exception as e:
            bundle.errors.append(f"Analiz hatası: {e}")

        # --- Metraj ---
        if options.run_takeoff:
            try:
                bundle.takeoff = compute_takeoff(scene)
            except Exception as e:
                bundle.errors.append(f"Metraj hatası: {e}")

        return bundle