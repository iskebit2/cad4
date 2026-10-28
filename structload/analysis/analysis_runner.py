# analysis/analysis_runner.py
"""
Analiz Modülleri Sarmalayıcı

"""

import traceback
from typing import Any

from structload.loads.snow_load import SnowLoad
from structload.loads.spectrum import Spectrum
from structload.windcalc.wind_results import WindReport


class AnalysisResult:
    """Analiz çıktısını GUI'ye taşımak için basit taşıyıcı."""

    def __init__(
        self,
        key: str,
        title: str,
        report: Any = None,
        error: str | None = None,
        extra: dict | None = None,
    ):
        self.key = key
        self.title = title
        self.report = report
        self.error = error
        self.extra = extra or {}

    @property
    def success(self) -> bool:
        return self.error is None

    def as_text(self) -> str:
        if not self.success:
            return f"❌ {self.title} analizi başarısız:\n{self.error}"
        return str(self.report)


# ----------------------------------------------------------------------
# Rüzgâr
# ----------------------------------------------------------------------

def run_wind(config: dict, data: dict) -> AnalysisResult:
    try:
        result = WindReport({
            "proje_bilgileri": config.get("proje_bilgileri", {}),
            "points": config.get("points", []),
            "polygons": config.get("polygons", []),
            "wind_config": data,
        })
        report = result.report()
        return AnalysisResult(
            key="wind",
            title="Rüzgâr",
            report=report,
            extra={"analysis": result},
        )
    except Exception as e:
        traceback.print_exc()
        return AnalysisResult(
            key="wind",
            title="Rüzgâr",
            error=f"{type(e).__name__}: {e}",
        )


# ----------------------------------------------------------------------
# Kar
# ----------------------------------------------------------------------

def run_snow(config: dict, data: dict) -> AnalysisResult:
    try:
        snow = SnowLoad(data)
        report = snow.report()
        return AnalysisResult(
            key="snow",
            title="Kar",
            report=report,
            extra={"analysis": snow},
        )
    except Exception as e:
        traceback.print_exc()
        return AnalysisResult(
            key="snow",
            title="Kar",
            error=f"{type(e).__name__}: {e}",
        )


# ----------------------------------------------------------------------
# Deprem
# ----------------------------------------------------------------------

def run_earthquake(config: dict, data: dict) -> AnalysisResult:
    try:
        eq = Spectrum(data)
        eq.run(T1=config.get("T1", 0))
        report = {
            "parameters": eq.table_parameters,
            "spectrum": eq.table_spectrum,
        }
        return AnalysisResult(
            key="earthquake",
            title="Deprem",
            report=report,
            extra={"analysis": eq},
        )
    except Exception as e:
        traceback.print_exc()
        return AnalysisResult(
            key="earthquake",
            title="Deprem",
            error=f"{type(e).__name__}: {e}",
        )


# ----------------------------------------------------------------------
# Spektrum Grafiği
# ----------------------------------------------------------------------

def show_spectrum_plot(earthquake_analysis) -> dict:
    """
    Spektrum grafiğini oluşturur ve gösterir.

    Returns
    -------
    dict: {"ok": bool, "save_path": str | None, "error": str | None}
    """
    try:
        save_path = "spectrum.png"
        earthquake_analysis.spectrum_plot(save=True, filename=save_path)
        return {"ok": True, "save_path": save_path, "error": None}

    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "save_path": None, "error": f"{type(e).__name__}: {e}"}