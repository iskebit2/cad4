# app/analysis/seismic_combos.py
from __future__ import annotations

from dataclasses import dataclass, field

from data.enums import SpectrumSourceType
from domain.definition import (
    AutoSeismicTSC2018,
    ComboItem,
    LoadCase,
    LoadCombination,
    LoadPattern,
    ResponseSpectrumCase,
    ResponseSpectrumLoadAssignment,
    SpectrumFunction,
    StaticLoadAssignment,
)


@dataclass
class SeismicSetupReport:
    missing_patterns: list[str] = field(default_factory=list)
    missing_cases: list[str] = field(default_factory=list)
    missing_spectra: list[str] = field(default_factory=list)
    missing_drift_combos: list[str] = field(default_factory=list)
    missing_design_combos: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not (
            self.missing_patterns
            or self.missing_cases
            or self.missing_spectra
            or self.missing_drift_combos
            or self.missing_design_combos
        )


def _find_patterns_by_category(project) -> tuple[list[str], list[str]]:
    dead_names: list[str] = []
    live_names: list[str] = []
    for name, pat in (getattr(project, "load_patterns", None) or {}).items():
        dtype = str(getattr(pat, "design_type", "")).strip().casefold()
        if dtype.startswith(("dead", "super dead")) or dtype == "ölü":
            dead_names.append(name)
        elif dtype.startswith("live") or dtype in ("hareketli", "canlı"):
            live_names.append(name)
    return dead_names, live_names


def _find_earthquake_patterns(project) -> dict[str, str]:
    found: dict[str, str] = {}
    for name, pat in (getattr(project, "load_patterns", None) or {}).items():
        dtype = str(getattr(pat, "design_type", "")).strip().casefold()
        uname = name.strip().upper()
        if dtype in ("quake", "seismic", "deprem") or "QUAKE" in uname or uname in ("EX", "EY", "EQX", "EQY"):
            if "Y" in uname and "X" not in uname:
                found.setdefault("Y", name)
            elif "X" in uname:
                found.setdefault("X", name)
    for pat_name, auto in (getattr(project, "auto_seismics", None) or {}).items():
        d = str(getattr(auto, "direction", "")).strip().upper()
        if "Y" in d:
            found["Y"] = pat_name
        elif "X" in d:
            found["X"] = pat_name
    return found


def expected_design_combo_names() -> list[str]:
    names = ["1.4G+1.6Q"]
    for ex in ("EXP", "EXM"):
        for ey in ("EYP", "EYM"):
            for sx in ("+", "-"):
                for sy in ("+", "-"):
                    names.append(f"G+nQ{sx}{ex}{sy}0.3{ey}")
                    names.append(f"0.9G{sx}{ex}{sy}0.3{ey}")
    return names


def inspect_seismic_setup(project) -> SeismicSetupReport:
    report = SeismicSetupReport()
    if project is None:
        return report

    cfg = getattr(getattr(project, "config", None), "seismic", None)
    if cfg is None:
        return report

    patterns = getattr(project, "load_patterns", None) or {}
    cases = getattr(project, "load_cases", None) or {}
    rs_cases = getattr(project, "response_spectrum_cases", None) or {}
    combos = getattr(project, "combinations", None) or {}

    eq_pats = _find_earthquake_patterns(project)
    if "X" not in eq_pats and "QUAKEX" not in patterns:
        report.missing_patterns.append("QUAKEX")
    if "Y" not in eq_pats and "QUAKEY" not in patterns:
        report.missing_patterns.append("QUAKEY")

    for cname in cfg.load_cases:
        uc = cname.upper()
        if uc.startswith("EQ"):
            if cname not in rs_cases and cname not in cases:
                report.missing_spectra.append(cname)
        else:
            if cname not in cases:
                report.missing_cases.append(cname)

    for dname in cfg.drift_combo_names:
        if dname not in combos and dname not in cases and dname not in rs_cases:
            report.missing_drift_combos.append(dname)

    for cname in expected_design_combo_names():
        if cname not in combos:
            report.missing_design_combos.append(cname)

    return report


def ensure_tbdy_spectrum_function(project, func_name: str = "TBDY2018_DD2") -> SpectrumFunction:
    funcs = getattr(project, "spectrum_functions", None)
    if funcs and func_name in funcs:
        return funcs[func_name]
    if funcs:
        first_key = next(iter(funcs))
        return funcs[first_key]

    cfg = project.config.seismic
    sf = SpectrumFunction(
        name=func_name,
        source_type=SpectrumSourceType.TSC_2018,
        damp=0.05,
        ss=float(cfg.dd2.get("Ss", 0.329)),
        s1=float(cfg.dd2.get("S1", 0.128)),
        tl=6.0,
        site_class=cfg.zemin_sinifi,
        r_coeff=float(cfg.R),
        d_coeff=float(cfg.D),
        i_coeff=float(cfg.I),
    )
    project.add_spectrum_function(sf)
    return sf


def ensure_seismic_cases_and_combos(project, *, include_design_combos: bool = True) -> list[str]:
    created: list[str] = []
    if project is None:
        return created

    cfg = project.config.seismic
    patterns = project.load_patterns
    cases = project.load_cases
    rs_cases = project.response_spectrum_cases
    combos = project.combinations

    dead_names, live_names = _find_patterns_by_category(project)
    if not dead_names:
        patterns["DEAD"] = LoadPattern(name="DEAD", design_type="Dead", self_wt_mult=1.0)
        dead_names = ["DEAD"]
        created.append("Pattern: DEAD")

    for dname in dead_names:
        if dname not in cases:
            cases[dname] = LoadCase(
                name=dname,
                case_type="LinStatic",
                design_type="Dead",
                static_assignments=[StaticLoadAssignment(load_name=dname, load_sf=1.0)],
            )
            created.append(f"LoadCase: {dname}")

    for lname in live_names:
        if lname not in cases:
            cases[lname] = LoadCase(
                name=lname,
                case_type="LinStatic",
                design_type="Live",
                static_assignments=[StaticLoadAssignment(load_name=lname, load_sf=1.0)],
            )
            created.append(f"LoadCase: {lname}")

    eq_pats = _find_earthquake_patterns(project)
    for axis, qname in (("X", "QUAKEX"), ("Y", "QUAKEY")):
        pat_name = eq_pats.get(axis, qname)
        if pat_name not in patterns:
            patterns[pat_name] = LoadPattern(name=pat_name, design_type="Quake", self_wt_mult=0.0)
            created.append(f"Pattern: {pat_name}")
        if pat_name not in project.auto_seismics:
            project.add_auto_seismic(
                AutoSeismicTSC2018(
                    load_pattern=pat_name,
                    direction=axis,
                    percent_ecc=0.05,
                    r_coeff=float(cfg.R),
                    d_coeff=float(cfg.D),
                    i_coeff=float(cfg.I),
                    ss=float(cfg.dd2.get("Ss", 0.329)),
                    s1=float(cfg.dd2.get("S1", 0.128)),
                    site_class=cfg.zemin_sinifi,
                    fs=float(cfg.dd2.get("Fs", 1.3)),
                    f1=float(cfg.dd2.get("F1", 1.5)),
                )
            )
        if qname not in cases:
            cases[qname] = LoadCase(
                name=qname,
                case_type="LinStatic",
                design_type="Quake",
                static_assignments=[StaticLoadAssignment(load_name=pat_name, load_sf=1.0)],
            )
            created.append(f"LoadCase: {qname}")

    spec_fn = ensure_tbdy_spectrum_function(project)
    for eq_name, angle in (("EQX", 0.0), ("EQY", 90.0)):
        if eq_name not in rs_cases:
            rs_cases[eq_name] = ResponseSpectrumCase(
                name=eq_name,
                modal_combo="CQC",
                dir_combo="SRSS",
                damping=0.05,
                eccentricity=0.05,
                assignments=[
                    ResponseSpectrumLoadAssignment(
                        load_name="U1" if angle == 0.0 else "U2",
                        function_name=spec_fn.name,
                        angle=angle,
                        sf=9806.65,
                    )
                ],
            )
            created.append(f"SpectrumCase: {eq_name}")

    drift_specs: dict[str, list[ComboItem]] = {
        "EXP": [ComboItem("EQX", 1.0), ComboItem("QUAKEX", 0.05)],
        "EXM": [ComboItem("EQX", 1.0), ComboItem("QUAKEX", -0.05)],
        "EYP": [ComboItem("EQY", 1.0), ComboItem("QUAKEY", 0.05)],
        "EYM": [ComboItem("EQY", 1.0), ComboItem("QUAKEY", -0.05)],
    }
    for dname in cfg.drift_combo_names:
        if dname not in combos and dname not in cases and dname not in rs_cases:
            items = drift_specs.get(dname.upper())
            if items is None:
                axis_case = "EQY" if "Y" in dname.upper() else "EQX"
                items = [ComboItem(axis_case, 1.0)]
            combos[dname] = LoadCombination(
                name=dname,
                combo_type="Linear Add",
                auto_design=False,
                items=items,
            )
            created.append(f"DriftCombo: {dname}")

    if include_design_combos:
        g_items = [ComboItem(d, 1.0) for d in dead_names]
        q_items = [ComboItem(l, 1.0) for l in live_names]

        if "1.4G+1.6Q" not in combos:
            combos["1.4G+1.6Q"] = LoadCombination(
                name="1.4G+1.6Q",
                combo_type="Linear Add",
                auto_design=True,
                items=[ComboItem(d, 1.4) for d in dead_names] + [ComboItem(l, 1.6) for l in live_names],
            )
            created.append("Combo: 1.4G+1.6Q")

        n_live = float(getattr(cfg, "n", 0.30))
        sds = float(cfg.dd2.get("Sds", 0.428))
        ed_factor = 0.3 * sds

        for ex in ("EXP", "EXM"):
            for ey in ("EYP", "EYM"):
                for sx_lbl, sx in (("+", 1.0), ("-", -1.0)):
                    for sy_lbl, sy in (("+", 1.0), ("-", -1.0)):
                        cname_1 = f"G+nQ{sx_lbl}{ex}{sy_lbl}0.3{ey}"
                        if cname_1 not in combos:
                            items_1 = (
                                [ComboItem(d, 1.0 + ed_factor) for d in dead_names]
                                + [ComboItem(l, n_live) for l in live_names]
                                + [ComboItem(ex, sx), ComboItem(ey, 0.3 * sy)]
                            )
                            combos[cname_1] = LoadCombination(
                                name=cname_1,
                                combo_type="Linear Add",
                                auto_design=True,
                                items=items_1,
                            )
                            created.append(f"Combo: {cname_1}")

                        cname_2 = f"0.9G{sx_lbl}{ex}{sy_lbl}0.3{ey}"
                        if cname_2 not in combos:
                            items_2 = (
                                [ComboItem(d, max(0.0, 0.9 - ed_factor)) for d in dead_names]
                                + [ComboItem(ex, sx), ComboItem(ey, 0.3 * sy)]
                            )
                            combos[cname_2] = LoadCombination(
                                name=cname_2,
                                combo_type="Linear Add",
                                auto_design=True,
                                items=items_2,
                            )
                            created.append(f"Combo: {cname_2}")

    return created