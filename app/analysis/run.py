# app/analysis/run.py
from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.material_takeoff import TakeoffResult, compute_takeoff
from app.analysis.modal_analysis import SpectralResult
from app.analysis.structuralanalysis import StructuralAnalysisResult, run_analysis


@dataclass
class AnalysisOptions:
    n_live: float = 0.3
    n_modes: int = 12
    run_static: bool = True
    run_modal: bool = True
    run_spectral: bool = False
    run_takeoff: bool = True
    static_case_names: list[str] | None = None
    spectrum_name: str | None = None
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

        spectrum = None
        if options.run_spectral:
            if options.spectrum_name:
                spectrum = project.spectrum_functions.get(options.spectrum_name)
                if spectrum is None:
                    bundle.errors.append(f"Spektrum bulunamadı: {options.spectrum_name}")
            if spectrum is None and not bundle.errors:
                bundle.errors.append("Spektrum seçilmedi — spectral atlandı")

        bundle.result = run_analysis(
            project,
            scene=scene,
            n_live=options.n_live,
            n_modes=options.n_modes,
            run_static=options.run_static,
            run_modal=options.run_modal,
            static_case_names=options.static_case_names,
            spectrum=spectrum,
            validate=True,
            use_shear_deform=options.use_shear_deform,
        )

        if options.run_modal and bundle.result.modal is None:
            bundle.errors.append("Modal sonuç üretilemedi")
        if spectrum is not None and bundle.result.spectral is not None:
            bundle.spectral = bundle.result.spectral

        if options.run_takeoff:
            bundle.takeoff = compute_takeoff(scene)

        return bundle