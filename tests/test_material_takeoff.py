from core.analysis.material_takeoff import ElementWeight, TakeoffResult


def test_element_weight_is_stored_in_newtons_and_exposed_in_kilonewtons():
    element = ElementWeight(
        unique_id=1,
        element_type="Frame",
        label="F1",
        material_name="Steel",
        section_name="IPE200",
        mass_kg=1000.0,
        weight_N=9806.65,
    )

    assert element.weight_N == 9806.65
    assert element.weight_kN == 9.80665


def test_takeoff_total_weight_is_reported_in_kilonewtons():
    result = TakeoffResult(
        elements=[
            ElementWeight(
                unique_id=1,
                element_type="Frame",
                label="F1",
                material_name="Steel",
                section_name="IPE200",
                weight_N=9806.65,
            ),
            ElementWeight(
                unique_id=2,
                element_type="Frame",
                label="F2",
                material_name="Steel",
                section_name="IPE200",
                weight_N=19613.3,
            ),
        ]
    )

    assert result.total_weight_kN == 29.41995
