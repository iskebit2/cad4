# tools/spectrum_tools.py
from __future__ import annotations

from domain.definition import (
    SpectrumFunction, SpectrumSourceType, get_tsc2018_site_coefficients,
)


def create_tbdy2018_spectrum(
    project,
    name: str,
    ss: float,
    s1: float,
    site_class: str = "ZC",
    r_coeff: float = 1.0,
    d_coeff: float = 1.0,
    i_coeff: float = 1.0,
    tl: float = 6.0,
    num_points: int = 200,
) -> SpectrumFunction:
    if r_coeff <= 0 or i_coeff <= 0:
        raise ValueError("r_coeff ve i_coeff pozitif olmalı")
    if num_points < 1:
        raise ValueError("num_points en az 1 olmalı")

    fs, f1 = get_tsc2018_site_coefficients(ss, s1, site_class)
    sds, sd1 = ss * fs, s1 * f1
    ta = 0.2 * sd1 / sds if sds > 0 else 0.0
    tb = sd1 / sds if sds > 0 else 0.0
    dt = max(tl + 2.0, 8.0) / num_points

    points = []
    for k in range(num_points + 1):
        t = k * dt
        if ta > 0 and t < ta:
            sae = (0.4 + 0.6 * t / ta) * sds
        elif t <= tb:
            sae = sds
        elif t <= tl:
            sae = sd1 / t
        else:
            sae = sd1 * tl / (t * t)
        ra = ((d_coeff + (r_coeff / i_coeff - d_coeff) * t / tb)
              if (t < tb and tb > 0) else r_coeff / i_coeff)
        points.append((round(t, 4), round(sae / ra, 6)))

    spec = SpectrumFunction(
        name=name, source_type=SpectrumSourceType.TSC_2018,
        ss=ss, s1=s1, tl=tl, site_class=site_class, fs=fs, f1=f1,
        r_coeff=r_coeff, d_coeff=d_coeff, i_coeff=i_coeff, points=points,
    )
    project.add_spectrum_function(spec)
    return spec