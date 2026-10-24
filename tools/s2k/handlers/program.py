# tools/s2k/handlers/program.py
"""PROGRAM CONTROL, PROJECT INFORMATION."""
import logging

import pandas as pd

from tools.s2k.context import LoadContext
from tools.s2k.units_adapter import UnitConverter
from domain.definition import GeneralProjectInfo, SiteInformation

logger = logging.getLogger(__name__)


def handle_program_control(ctx: LoadContext, df: pd.DataFrame) -> None:
    if "CurrUnits" in df.columns and not df.empty:
        raw = str(df.iloc[0]["CurrUnits"]).strip()
        if raw:
            ctx.units = UnitConverter.from_sap(raw)
            logger.info("[Units] CurrUnits='%s'", raw)
            return
    ctx.units = UnitConverter()
    logger.info("[Units] CurrUnits yok, varsayılan N_MM")


def handle_project_information(ctx: LoadContext, df: pd.DataFrame) -> None:
    info: dict = {}
    for _, row in df.iterrows():
        key = str(row.get("Item", "")).strip()
        val = str(row.get("Data", "")).strip()
        if key:
            info[key] = val

    ctx.project_info["gen"] = GeneralProjectInfo(
        company_name=info.get("Company Name", ""),
        client_name=info.get("Client Name", ""),
        project_name=info.get("Project Name", "CAD Model"),
        project_number=info.get("Project Number", ""),
        model_name=info.get("Model Name", ""),
        model_description=info.get("Model Description", ""),
        revision_number=info.get("Revision Number", "R0"),
        frame_type=info.get("Frame Type", ""),
        engineer=info.get("Engineer", ""),
        checker=info.get("Checker", ""),
        supervisor=info.get("Supervisor", ""),
        issue_code=info.get("Issue Code", ""),
        design_code=info.get("Design Code", ""),
    )
    ctx.project_info["site"] = SiteInformation(
        cadastral_info="--- / --",
        live_load_factor=0.3,
        date="xx.xx.20xx",
        soil_class="ZD",
        subgrade_modulus_kn_m3=1500,
    )