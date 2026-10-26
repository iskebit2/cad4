# tools/s2k/handlers/__init__.py
"""
Handler router + priority. Her handler (ctx, df) imzasında.

build_router() → {table_name: handler}
build_sorted_router() → [(table_name, handler)]  (önceliğe göre sıralı)
"""
from typing import Callable, Dict, List, Tuple

from tools.s2k.handlers import (
    program, materials, sections, links, nodes, frames, areas,
    loads, patterns, spectra, grids, section_cuts,
)


PRIORITY: Dict[str, int] = {
    "PROGRAM CONTROL": 10,
    "PROJECT INFORMATION": 11,
    "GRID LINES": 12,

    "MATERIAL PROPERTIES 01 - GENERAL": 20,
    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": 21,

    "SECTION DESIGNER PROPERTIES 01 - GENERAL": 29,
    "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON": 29,
    "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": 29,

    "FRAME SECTION PROPERTIES 01 - GENERAL": 30,
    "FRAME SECTION PROPERTIES 04 - AUTO SELECT": 31,
    "AREA SECTION PROPERTIES": 32,
    "LINK PROPERTY DEFINITIONS 01 - GENERAL": 33,
    "LINK PROPERTY DEFINITIONS 02 - LINEAR": 34,

    "LOAD PATTERN DEFINITIONS": 40,
    "LOAD CASE DEFINITIONS": 41,
    "CASE - STATIC 1 - LOAD ASSIGNMENTS": 42,
    "CASE - MODAL 1 - GENERAL": 43,
    "COMBINATION DEFINITIONS": 44,
    "MASS SOURCE": 45,

    "JOINT COORDINATES": 50,
    "JOINT RESTRAINT ASSIGNMENTS": 51,
    "CONNECTIVITY - FRAME": 52,
    "CONNECTIVITY - AREA": 53,
    "CONNECTIVITY - LINK": 54,
    "JOINT CONSTRAINT ASSIGNMENTS": 55,

    "FRAME SECTION ASSIGNMENTS": 60,
    "AREA SECTION ASSIGNMENTS": 61,
    "LINK PROPERTY ASSIGNMENTS": 62,
    "FRAME RELEASE ASSIGNMENTS 1 - GENERAL": 63,
    "FRAME PROPERTY MODIFIERS": 64,
    "FRAME DESIGN PROCEDURES": 65,
    "FRAME AUTO MESH ASSIGNMENTS": 66,
    "CONSTRAINT DEFINITIONS - DIAPHRAGM": 70,

    "JOINT LOADS - FORCE": 75,
    "FRAME LOADS - GRAVITY": 76,
    "FRAME LOADS - DISTRIBUTED": 77,
    "FRAME LOADS - POINTS": 78,
    "FRAME LOADS - TEMPERATURE": 79,
    "AREA LOADS - UNIFORM": 80,
    "AREA LOADS - UNIFORM TO FRAME": 81,
    "AREA LOADS - WIND PRESSURE COEFFICIENTS": 82,

    "FUNCTION - RESPONSE SPECTRUM - TSC-2018": 85,
    "FUNCTION - RESPONSE SPECTRUM - FILE": 86,
    "FUNCTION - RESPONSE SPECTRUM - USER": 87,
    "CASE - RESPONSE SPECTRUM 1 - GENERAL": 88,
    "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS": 89,
    "AUTO SEISMIC - TSC-2018": 90,

    "SECTION CUTS 1 - GENERAL": 95,
    "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS": 96,
}


def get_priority(table_name: str) -> int:
    return PRIORITY.get(table_name, 999)


def build_router() -> Dict[str, Callable]:
    return {
        # Program
        "PROGRAM CONTROL": program.handle_program_control,
        "PROJECT INFORMATION": program.handle_project_information,

        # Materials
        "MATERIAL PROPERTIES 01 - GENERAL": materials.handle_material_props,
        "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": materials.handle_material_mech,

        # Sections
        "FRAME SECTION PROPERTIES 01 - GENERAL": sections.handle_frame_props,
        "FRAME SECTION PROPERTIES 04 - AUTO SELECT": sections.handle_auto_select_lists,
        "AREA SECTION PROPERTIES": sections.handle_area_props,
        "SECTION DESIGNER PROPERTIES 01 - GENERAL": sections.handle_sd_general,
        "SECTION DESIGNER PROPERTIES 16 - SHAPE POLYGON": sections.handle_sd_polygon,
        "SECTION DESIGNER PROPERTIES 19 - SHAPE REINFORCING RECTANGLE": sections.handle_sd_rebar_rect,

        # Links
        "LINK PROPERTY DEFINITIONS 01 - GENERAL": links.handle_link_props,
        "LINK PROPERTY DEFINITIONS 02 - LINEAR": links.handle_link_props_linear,

        # Patterns / Cases / Combos
        "LOAD PATTERN DEFINITIONS": patterns.handle_load_patterns,
        "LOAD CASE DEFINITIONS": patterns.handle_load_cases,
        "CASE - STATIC 1 - LOAD ASSIGNMENTS": patterns.handle_static_assignments,
        "CASE - MODAL 1 - GENERAL": patterns.handle_modal_cases,
        "COMBINATION DEFINITIONS": patterns.handle_combinations,
        "MASS SOURCE": patterns.handle_mass_source,

        # Nodes / connectivity
        "JOINT COORDINATES": nodes.handle_joints,
        "JOINT RESTRAINT ASSIGNMENTS": nodes.handle_joint_restraints,
        "JOINT CONSTRAINT ASSIGNMENTS": nodes.handle_joint_constraints,
        "CONNECTIVITY - FRAME": frames.handle_frame_conn,
        "CONNECTIVITY - AREA": areas.handle_area_conn,
        "CONNECTIVITY - LINK": links.handle_link_conn,

        # Frame/Area assignments
        "FRAME SECTION ASSIGNMENTS": frames.handle_frame_assign,
        "FRAME RELEASE ASSIGNMENTS 1 - GENERAL": frames.handle_frame_releases,
        "FRAME PROPERTY MODIFIERS": frames.handle_frame_modifiers,
        "FRAME DESIGN PROCEDURES": frames.handle_frame_design_procs,
        "FRAME AUTO MESH ASSIGNMENTS": frames.handle_frame_auto_mesh,
        "AREA SECTION ASSIGNMENTS": areas.handle_area_assign,
        "LINK PROPERTY ASSIGNMENTS": links.handle_link_assign,
        "CONSTRAINT DEFINITIONS - DIAPHRAGM": nodes.handle_diaphragms,

        # Loads
        "JOINT LOADS - FORCE": loads.handle_joint_loads,
        "FRAME LOADS - GRAVITY": loads.handle_frame_gravity,
        "FRAME LOADS - DISTRIBUTED": loads.handle_frame_distributed,
        "FRAME LOADS - POINTS": loads.handle_frame_points,
        "FRAME LOADS - TEMPERATURE": loads.handle_frame_temperature,
        "AREA LOADS - UNIFORM": loads.handle_area_uniform,
        "AREA LOADS - UNIFORM TO FRAME": loads.handle_area_uniform_to_frame,
        "AREA LOADS - WIND PRESSURE COEFFICIENTS": loads.handle_area_wind,
    
        # Spectra
        "FUNCTION - RESPONSE SPECTRUM - TSC-2018": spectra.handle_spectrum_functions_TSC,
        "FUNCTION - RESPONSE SPECTRUM - FILE": spectra.handle_spectrum_functions_file,
        "FUNCTION - RESPONSE SPECTRUM - USER": spectra.handle_spectrum_functions_user,
        "CASE - RESPONSE SPECTRUM 1 - GENERAL": spectra.handle_response_spectrum_gen,
        "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS": spectra.handle_response_spectrum_assign,
        "AUTO SEISMIC - TSC-2018": spectra.handle_auto_seismic,

        # Grid / Section cuts
        "GRID LINES": grids.handle_grid_lines,
        "SECTION CUTS 1 - GENERAL": section_cuts.handle_section_cuts_gen,
        "SECTION CUTS 3 - QUADRILATERAL DEFINITIONS": section_cuts.handle_section_cuts_quad,
    }


def build_sorted_router() -> List[Tuple[str, Callable]]:
    router = build_router()
    items = [(name, h, get_priority(name)) for name, h in router.items()]
    items.sort(key=lambda x: x[2])
    return [(name, h) for name, h, _ in items]