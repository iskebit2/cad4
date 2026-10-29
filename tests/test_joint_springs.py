# tests/test_joint_springs.py
import pandas as pd
from tools.s2k.context import LoadContext
from tools.s2k.handlers.nodes import handle_joint_springs


def test_joint_springs_parsed():
    ctx = LoadContext()
    df = pd.DataFrame([
        {"Joint": "25", "CoordSys": "Local",
         "U1": "1000", "U2": "2000", "U3": "500",
         "R1": "0", "R2": "0", "R3": "0"},
    ])
    handle_joint_springs(ctx, df)
    s = ctx.joint_springs["25"]
    assert s["u1"] == 1000.0
    assert s["u2"] == 2000.0
    assert s["u3"] == 500.0
    assert s["r1"] == 0.0