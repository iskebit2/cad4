# tools/s2k/handlers/__init__.py
"""Handler router + priority. Her handler (ctx, df) imzasında.

build_router() → {table_name: handler}
build_sorted_router() → [(table_name, handler)]  (önceliğe göre sıralı)
"""
from __future__ import annotations

from collections.abc import Callable

from functools import partial

from data.enums import ConstraintType
from tools.s2k.handlers import (
    areas,
    frames,
    grids,
    links,
    loads,
    materials,
    nodes,
    patterns,
    program,
    section_cuts,
    sections,
    spectra,
)


# ============================================================================
# PRIORITY — handler çalışma sırası
# ============================================================================
PRIORITY: dict[str, int] = {
    # --- program / proje ---
    "PROGRAM CONTROL": 10,
    "PROJECT INFORMATION": 11,
    "GRID LINES": 12,

    # --- malzeme ---
    "MATERIAL PROPERTIES 01 - GENERAL": 20,
    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": 21,
    "MATERIAL PROPERTIES 03A - STEEL DATA": 22,
    "MATERIAL PROPERTIES 03B - CONCRETE DATA": 22,
    "MATERIAL PROPERTIES 03E - REBAR DATA": 22,
    "MATERIAL PROPERTIES 03F - TENDON DATA": 22,
    "MATERIAL PROPERTIES 03J - COUPLED NONLINEAR VON MISES DATA": 22,
    "MATERIAL PROPERTIES 04 - DESIGN CONCRETE": 22,
    "MATERIAL PROPERTIES 06 - DAMPING PARAMETERS": 22,
    "MATERIAL PROPERTIES 09 - ACCEPTANCE CRITERIA": 22,

    # --- section designer ---
    "SECTION DESIGNER PROPERTIES 01 - GENERAL": 29,
    "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON": 29,
    "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": 29,
    "SECTION DESIGNER PROPERTIES 30 - FIBER GENERAL": 29,

    # --- frame/area/link sections ---
    "FRAME SECTION PROPERTIES 01 - GENERAL": 30,
    "FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN": 30,
    "FRAME SECTION PROPERTIES 03 - CONCRETE BEAM": 30,
    "FRAME SECTION PROPERTIES 04 - AUTO SELECT": 31,
    "FRAME SECTION PROPERTIES 13 - TIME DEPENDENT": 31,
    "AREA SECTION PROPERTIES": 32,
    "AREA SECTION PROPERTY DESIGN PARAMETERS": 32,
    "AREA SECTION PROPERTY - TIME DEPENDENT": 32,
    "LINK PROPERTY DEFINITIONS 01 - GENERAL": 33,
    "LINK PROPERTY DEFINITIONS 02 - LINEAR": 34,

    # --- pattern / case / combo ---
    "LOAD PATTERN DEFINITIONS": 40,          # v25
    "LOAD CASE DEFINITIONS": 41,             # v25 (LoadCase) / v10 (LoadPattern)
    "ANALYSIS CASE DEFINITIONS": 41,         # v10 (LoadCase)
    "CASE - STATIC 1 - LOAD ASSIGNMENTS": 42,
    "CASE - MODAL 1 - GENERAL": 43,
    "COMBINATION DEFINITIONS": 44,
    "MASS SOURCE": 45,

    # --- node ---
    "JOINT COORDINATES": 50,
    "JOINT RESTRAINT ASSIGNMENTS": 51,
    "CONNECTIVITY - FRAME": 52,
    "CONNECTIVITY - AREA": 53,
    "CONNECTIVITY - LINK": 54,
    "JOINT CONSTRAINT ASSIGNMENTS": 55,
    "JOINT ADDED MASS ASSIGNMENTS": 56,
    "JOINT SPRING ASSIGNMENTS 1 - UNCOUPLED": 57,
    "JOINT SPRING ASSIGNMENTS 2 - COUPLED": 58,

    # --- frame parametreleri ---
    "FRAME SECTION ASSIGNMENTS": 60,
    "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL": 60,
    "AREA SECTION ASSIGNMENTS": 61,
    "LINK PROPERTY ASSIGNMENTS": 62,
    "FRAME RELEASE ASSIGNMENTS 1 - GENERAL": 63,
    "FRAME PROPERTY MODIFIERS": 64,
    "FRAME DESIGN PROCEDURES": 65,
    "FRAME AUTO MESH ASSIGNMENTS": 66,
    "FRAME AUTO SUBDIVISION ASSIGNMENTS": 66,   # v10 alias
    "FRAME INSERTION POINT ASSIGNMENTS": 67,
    "FRAME OFFSET ALONG LENGTH ASSIGNMENTS": 68,
    "FRAME OUTPUT STATION ASSIGNMENTS": 69,
    "FRAME LOAD TRANSFER OPTIONS": 71,

    # --- constraint ---
    "CONSTRAINT DEFINITIONS - BEAM": 70,
    "CONSTRAINT DEFINITIONS - BODY": 70,
    "CONSTRAINT DEFINITIONS - DIAPHRAGM": 70,
    "CONSTRAINT DEFINITIONS - EQUAL": 70,
    "CONSTRAINT DEFINITIONS - LINE": 70,
    "CONSTRAINT DEFINITIONS - LOCAL": 70,
    "CONSTRAINT DEFINITIONS - PLATE": 70,
    "CONSTRAINT DEFINITIONS - ROD": 70,
    "CONSTRAINT DEFINITIONS - WELD": 70,

    # --- yükler ---
    "JOINT LOADS - FORCE": 75,
    "FRAME LOADS - GRAVITY": 76,
    "FRAME LOADS - DISTRIBUTED": 77,
    "FRAME LOADS - POINTS": 78,
    "FRAME LOADS - TEMPERATURE": 79,
    "AREA LOADS - UNIFORM": 80,
    "AREA LOADS - UNIFORM TO FRAME": 81,
    "AREA LOADS - WIND PRESSURE COEFFICIENTS": 82,

    # --- spektrum ---
    "FUNCTION - RESPONSE SPECTRUM - TSC-2018": 85,
    "FUNCTION - RESPONSE SPECTRUM - FILE": 86,
    "FUNCTION - RESPONSE SPECTRUM - USER": 87,
    "CASE - RESPONSE SPECTRUM 1 - GENERAL": 88,
    "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS": 89,
    "AUTO SEISMIC - TSC-2018": 90,

    # --- section cut / grid ---
    "SECTION CUTS 1 - GENERAL": 95,
    "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS": 96,
}


def get_priority(table_name: str) -> int:
    return PRIORITY.get(table_name, 999)


# ============================================================================
# ROUTER
# ============================================================================
def build_router() -> dict[str, Callable]:
    return {
        # --- Program ---
        "PROGRAM CONTROL": program.handle_program_control,
        "PROJECT INFORMATION": program.handle_project_information,

        # --- Materials ---
        "MATERIAL PROPERTIES 01 - GENERAL": materials.handle_material_props,
        "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": materials.handle_material_mech,
        "MATERIAL PROPERTIES 03A - STEEL DATA": materials.handle_material_steel,
        "MATERIAL PROPERTIES 03B - CONCRETE DATA": materials.handle_material_concrete,
        "MATERIAL PROPERTIES 03E - REBAR DATA": materials.handle_material_rebar,
        "MATERIAL PROPERTIES 03F - TENDON DATA": materials.handle_material_tendon,
        "MATERIAL PROPERTIES 03J - COUPLED NONLINEAR VON MISES DATA": materials.handle_material_von_mises,
        "MATERIAL PROPERTIES 04 - DESIGN CONCRETE": materials.handle_material_design_concrete_v10,
        "MATERIAL PROPERTIES 06 - DAMPING PARAMETERS": materials.handle_material_damping,
        "MATERIAL PROPERTIES 09 - ACCEPTANCE CRITERIA": materials.handle_material_acceptance,

        # --- Section designer ---
        "SECTION DESIGNER PROPERTIES 01 - GENERAL": sections.handle_sd_general,
        "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON": sections.handle_sd_polygon,
        "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": sections.handle_sd_rebar_rect,
        "SECTION DESIGNER PROPERTIES 30 - FIBER GENERAL": sections.handle_sd_fiber_general,

        # --- Frame / Area / Link section ---
        "FRAME SECTION PROPERTIES 01 - GENERAL": sections.handle_frame_props,
        "FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN": sections.handle_frame_section_rebar_col,
        "FRAME SECTION PROPERTIES 03 - CONCRETE BEAM": sections.handle_frame_section_rebar_beam,
        "FRAME SECTION PROPERTIES 04 - AUTO SELECT": sections.handle_auto_select_lists,
        "FRAME SECTION PROPERTIES 13 - TIME DEPENDENT": sections.handle_frame_section_time_dependent,
        "AREA SECTION PROPERTIES": sections.handle_area_props,
        "AREA SECTION PROPERTY DESIGN PARAMETERS": areas.handle_area_section_design,
        "AREA SECTION PROPERTY - TIME DEPENDENT": areas.handle_area_section_time_dep,

        # --- Link props ---
        "LINK PROPERTY DEFINITIONS 01 - GENERAL": links.handle_link_props,
        "LINK PROPERTY DEFINITIONS 02 - LINEAR": links.handle_link_props_linear,

        # --- Pattern / Case / Combo ---
        "LOAD PATTERN DEFINITIONS": patterns.handle_load_patterns,
        "LOAD CASE DEFINITIONS": patterns.handle_load_cases,
        "ANALYSIS CASE DEFINITIONS": patterns.handle_analysis_cases_v10,
        "CASE - STATIC 1 - LOAD ASSIGNMENTS": patterns.handle_static_assignments,
        "CASE - MODAL 1 - GENERAL": patterns.handle_modal_cases,
        "COMBINATION DEFINITIONS": patterns.handle_combinations,
        "MASS SOURCE": patterns.handle_mass_source,

        # --- Node / connectivity ---
        "JOINT COORDINATES": nodes.handle_joints,
        "JOINT RESTRAINT ASSIGNMENTS": nodes.handle_joint_restraints,
        "JOINT CONSTRAINT ASSIGNMENTS": nodes.handle_joint_constraints,
        "JOINT ADDED MASS ASSIGNMENTS": nodes.handle_joint_added_mass,
        "JOINT SPRING ASSIGNMENTS 1 - UNCOUPLED": nodes.handle_joint_springs,
        "CONNECTIVITY - FRAME": frames.handle_frame_conn,
        "CONNECTIVITY - AREA": areas.handle_area_conn,
        "CONNECTIVITY - LINK": links.handle_link_conn,

        # --- Frame parametreleri ---
        "FRAME SECTION ASSIGNMENTS": frames.handle_frame_assign,
        "FRAME RELEASE ASSIGNMENTS 1 - GENERAL": frames.handle_frame_releases,
        "FRAME PROPERTY MODIFIERS": frames.handle_frame_modifiers,
        "FRAME DESIGN PROCEDURES": frames.handle_frame_design_procs,
        "FRAME AUTO MESH ASSIGNMENTS": frames.handle_frame_auto_mesh,
        "FRAME AUTO SUBDIVISION ASSIGNMENTS": frames.handle_frame_auto_mesh,   # v10 alias
        "FRAME INSERTION POINT ASSIGNMENTS": frames.handle_frame_insertion_points,
        "FRAME OFFSET ALONG LENGTH ASSIGNMENTS": frames.handle_frame_end_offsets,
        "FRAME OUTPUT STATION ASSIGNMENTS": frames.handle_frame_output_stations,
        "FRAME LOAD TRANSFER OPTIONS": frames.handle_frame_load_transfer,
        "FRAME LOCAL AXES ASSIGNMENTS 1 - TYPICAL": frames.handle_frame_local_axes,

        # --- Area / Link assignment ---
        "AREA SECTION ASSIGNMENTS": areas.handle_area_assign,
        "LINK PROPERTY ASSIGNMENTS": links.handle_link_assign,

        # --- Constraint (9 tip) ---
        "CONSTRAINT DEFINITIONS - BEAM": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.BEAM),
        "CONSTRAINT DEFINITIONS - BODY": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.BODY),
        "CONSTRAINT DEFINITIONS - DIAPHRAGM": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.DIAPHRAGM),
        "CONSTRAINT DEFINITIONS - EQUAL": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.EQUAL),
        "CONSTRAINT DEFINITIONS - LINE": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.LINE),
        "CONSTRAINT DEFINITIONS - LOCAL": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.LOCAL),
        "CONSTRAINT DEFINITIONS - PLATE": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.PLATE),
        "CONSTRAINT DEFINITIONS - ROD": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.ROD),
        "CONSTRAINT DEFINITIONS - WELD": partial(
            nodes.handle_constraint_definitions, ctype=ConstraintType.WELD),

        # --- Yükler ---
        "JOINT LOADS - FORCE": loads.handle_joint_loads,
        "FRAME LOADS - GRAVITY": loads.handle_frame_gravity,
        "FRAME LOADS - DISTRIBUTED": loads.handle_frame_distributed,
        "FRAME LOADS - POINTS": loads.handle_frame_points,
        "FRAME LOADS - TEMPERATURE": loads.handle_frame_temperature,
        "AREA LOADS - UNIFORM": loads.handle_area_uniform,
        "AREA LOADS - UNIFORM TO FRAME": loads.handle_area_uniform_to_frame,
        "AREA LOADS - WIND PRESSURE COEFFICIENTS": loads.handle_area_wind,

        # --- Spectrum ---
        "FUNCTION - RESPONSE SPECTRUM - TSC-2018": spectra.handle_spectrum_functions_TSC,
        "FUNCTION - RESPONSE SPECTRUM - FILE": spectra.handle_spectrum_functions_file,
        "FUNCTION - RESPONSE SPECTRUM - USER": spectra.handle_spectrum_functions_user,
        "CASE - RESPONSE SPECTRUM 1 - GENERAL": spectra.handle_response_spectrum_gen,
        "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS": spectra.handle_response_spectrum_assign,
        "AUTO SEISMIC - TSC-2018": spectra.handle_auto_seismic,

        # --- Grid / Section cut ---
        "GRID LINES": grids.handle_grid_lines,
        "SECTION CUTS 1 - GENERAL": section_cuts.handle_section_cuts_gen,
        "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS": section_cuts.handle_section_cuts_quad,
    }


def build_sorted_router() -> list[tuple[str, Callable]]:
    router = build_router()
    items = [(name, h, get_priority(name)) for name, h in router.items()]
    items.sort(key=lambda x: x[2])
    return [(name, h) for name, h, _ in items]