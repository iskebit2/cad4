import pandas as pd
from tools.s2k.context import LoadContext
from tools.s2k.handlers.links import (
    handle_link_props, handle_link_props_linear,
)


def test_link_props_general_and_linear():
    ctx = LoadContext()

    # 01 - GENERAL
    df1 = pd.DataFrame([{
        "LinkProp": "L1", "LinkType": "LINEAR",
        "DOF1": "Yes", "DOF2": "No", "DOF3": "Yes",
        "DOF4": "No", "DOF5": "No", "DOF6": "No",
    }])
    handle_link_props(ctx, df1)
    prop = ctx.link_props["L1"]
    assert prop.DOF["U1"] is True
    assert prop.DOF["U2"] is False

    # 02 - LINEAR
    df2 = pd.DataFrame([{
        "LinkProp": "L1",
        "Ke1": "1000", "Ke2": "2000", "Ke3": "3000",
        "Ke4": "1e6", "Ke5": "2e6", "Ke6": "3e6",
        "Ce1": "10", "Ce2": "20", "Ce3": "30",
        "Ce4": "0", "Ce5": "0", "Ce6": "0",
    }])
    handle_link_props_linear(ctx, df2)
    assert prop.Ke["U1"] == 1000.0
    assert prop.Ke["R1"] == 1e6
    assert prop.Ce["U1"] == 10.0


def test_link_props_linear_alias_columns():
    """K1/Stiff1 alias'ları."""
    ctx = LoadContext()
    df = pd.DataFrame([{"LinkProp": "L2", "K1": "500", "Stiff2": "600"}])
    handle_link_props_linear(ctx, df)
    prop = ctx.link_props["L2"]
    assert prop.Ke["U1"] == 500.0
    assert prop.Ke["U2"] == 600.0