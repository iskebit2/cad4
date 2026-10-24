# tools/s2k/handlers/areas.py
"""AREA CONNECTIVITY, ASSIGNMENTS."""
import pandas as pd

from tools.s2k.context import LoadContext


def handle_area_conn(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_conn = df


def handle_area_assign(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_area_assign = df