# tools/s2k/handlers/spectra.py
"""RESPONSE SPECTRUM FUNCTIONS/CASES, AUTO SEISMIC."""
import pandas as pd

from data.enums import SpectrumSourceType
from domain.definition import (
    AutoSeismicTSC2018,
    ResponseSpectrumCase,
    ResponseSpectrumLoadAssignment,
    SpectrumFunction,
)
from tools.s2k.context import LoadContext


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def handle_spectrum_functions_TSC(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        name = str(r.get("Name", "")).strip()
        if not name:
            continue
        ctx.spectrum_functions[name] = SpectrumFunction(
            name=name, source_type=SpectrumSourceType.TSC_2018,
            damp=_safe_float(r, "FuncDamp", 0.05),
            spec_dir=str(r.get("SpecDir", "Horizontal")).strip(),
            ss=_safe_float(r, "Ss"), s1=_safe_float(r, "S1"),
            tl=_safe_float(r, "TL", 6.0),
            site_class=str(r.get("SiteClass", "ZD")).strip(),
            fs=_safe_float(r, "Fs", 1.0), f1=_safe_float(r, "F1", 1.0),
            r_coeff=_safe_float(r, "R", 1.0),
            d_coeff=_safe_float(r, "D", 1.0),
            i_coeff=_safe_float(r, "I", 1.0),
        )


def handle_spectrum_functions_file(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        name = str(r.get("Name", "")).strip()
        if not name:
            continue
        ctx.spectrum_functions[name] = SpectrumFunction(
            name=name, source_type=SpectrumSourceType.FROM_FILE,
            damp=_safe_float(r, "FuncDamp", 0.05),
            data_type=str(r.get("DataType", "Period vs Accel")).strip(),
            file_path=str(r.get("FileName", "")).strip(),
        )


def handle_spectrum_functions_user(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        name = str(r.get("Name", "")).strip()
        if not name:
            continue
        sf = ctx.spectrum_functions.setdefault(
            name, SpectrumFunction(name=name, source_type=SpectrumSourceType.USER,
                                   damp=_safe_float(r, "FuncDamp", 0.05))
        )
        sf.points.append((_safe_float(r, "Period"), _safe_float(r, "Accel")))


def handle_response_spectrum_gen(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_spec_gen = df


def handle_response_spectrum_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_spec_ass = df
    if ctx.df_spec_gen is None or ctx.df_spec_gen.empty:
        return
    cases = {}
    for _, r in ctx.df_spec_gen.iterrows():
        cname = str(r.get("Case", "")).strip()
        if cname:
            cases[cname] = ResponseSpectrumCase(
                name=cname,
                modal_combo=str(r.get("ModalCombo", "CQC")).strip(),
                dir_combo=str(r.get("DirCombo", "SRSS")).strip(),
                damping=_safe_float(r, "ConstDamp", 0.05),
                eccentricity=_safe_float(r, "EccenRatio", 0.0),
            )
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            case_obj = cases.get(str(r.get("Case", "")).strip())
            if case_obj is None:
                continue
            case_obj.assignments.append(ResponseSpectrumLoadAssignment(
                load_name=str(r.get("LoadName", "U1")).strip(),
                function_name=str(r.get("Function", "")).strip(),
                angle=_safe_float(r, "Angle", 0.0),
                sf=_safe_float(r, "TransAccSF", 1.0),
            ))
    ctx.response_spectrum_cases = cases


def handle_auto_seismic(ctx: LoadContext, df: pd.DataFrame) -> None:
    for _, r in df.iterrows():
        pat = str(r.get("LoadPat", "")).strip()
        if not pat:
            continue
        ctx.auto_seismics[pat] = AutoSeismicTSC2018(
            load_pattern=pat,
            direction=str(r.get("Dir", "X")).strip(),
            percent_ecc=_safe_float(r, "PercentEcc", 0.05),
            period_calc=str(r.get("PeriodCalc", "Prog Calc")).strip(),
            ct_and_x=str(r.get("CtAndX", "0.10m, 0.75")).strip(),
            r_coeff=_safe_float(r, "R", 2.5),
            d_coeff=_safe_float(r, "D", 2.5),
            i_coeff=_safe_float(r, "I", 1.2),
            ss=_safe_float(r, "Ss"), s1=_safe_float(r, "S1"),
            tl=_safe_float(r, "TL", 8.0),
            site_class=str(r.get("SiteClass", "ZC")).strip(),
            fs=_safe_float(r, "Fs", 1.0), f1=_safe_float(r, "F1", 1.0),
        )