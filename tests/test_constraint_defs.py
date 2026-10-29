import pytest
import pandas as pd
from data.enums import ConstraintType
from tools.s2k.context import LoadContext
from tools.s2k.handlers.nodes import handle_constraint_definitions


@pytest.mark.parametrize("ctype,df_row,expected", [
    (ConstraintType.DIAPHRAGM,
     {"Name": "D1", "CoordSys": "GLOBAL", "Axis": "Z", "MultiLevel": "No"},
     {"axis": "Z", "multi_level": False}),
    (ConstraintType.BODY,
     {"Name": "B1", "UX": "Yes", "UY": "Yes", "UZ": "Yes",
      "RX": "Yes", "RY": "Yes", "RZ": "Yes"},
     {"ux": True, "uy": True, "uz": True,
      "rx": True, "ry": True, "rz": True}),
    (ConstraintType.WELD,
     {"Name": "W1", "Tolerance": "10", "UX": "Yes"},
     {"tolerance": 10.0, "ux": True}),
    (ConstraintType.LOCAL,
     {"Name": "L1", "U1": "Yes", "U2": "No", "R3": "Yes"},
     {"u1": True, "u2": False, "r3": True}),
])
def test_constraint_definitions(ctype, df_row, expected):
    ctx = LoadContext()
    df = pd.DataFrame([df_row])
    handle_constraint_definitions(ctx, df, ctype)

    cd = ctx.constraint_definitions[df_row["Name"]]
    assert cd.constraint_type == ctype
    for key, val in expected.items():
        assert getattr(cd, key) == val


def test_constraint_type_enum_values():
    assert ConstraintType.BODY.value == 1
    assert ConstraintType.DIAPHRAGM.value == 2
    assert ConstraintType.LINE.value == 13
    assert len(ConstraintType) == 9