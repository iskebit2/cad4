# tools/s2k/router.py
"""Tablo adı → Handler eşlemesi + öncelik."""

from typing import Callable, Dict, List, Tuple

from tools.s2k import handlers as H


PRIORITY = {
    # 1. Program ve birimler
    "PROGRAM CONTROL":                                  10,
    "PROJECT INFORMATION":                              11,
    
    # 2. Malzemeler
    "MATERIAL PROPERTIES 01 - GENERAL":                 20,
    "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": 21,
    
    # 3. Kesitler
    "FRAME SECTION PROPERTIES 01 - GENERAL":            30,
    "FRAME SECTION PROPERTIES 04 - AUTO SELECT":         31,
    "AREA SECTION PROPERTIES":                          32,
    "LINK PROPERTY DEFINITIONS 01 - GENERAL":           33,
    
    # 4. Yük & Analiz Tanımları
    "LOAD PATTERN DEFINITIONS":                         40,
    "LOAD CASE DEFINITIONS":                            41,
    "CASE - STATIC 1 - LOAD ASSIGNMENTS":               42,
    "CASE - MODAL 1 - GENERAL":                         43,
    "COMBINATION DEFINITIONS":                          44,
    "MASS SOURCE":                                      45,
    
    # 5. Geometri
    "JOINT COORDINATES":                                50,
    "JOINT RESTRAINT ASSIGNMENTS":                      51,
    "CONNECTIVITY - FRAME":                             52,
    "CONNECTIVITY - AREA":                              53,
    "CONNECTIVITY - LINK":                              54,
    
    # 6. Atamalar
    "FRAME SECTION ASSIGNMENTS":                        60,
    "AREA SECTION ASSIGNMENTS":                         61,
    "LINK PROPERTY ASSIGNMENTS":                        62,
    "FRAME RELEASE ASSIGNMENTS 1 - GENERAL":            63,
    
    # 7. Yükler
    "JOINT LOADS - FORCE":                              70,
    "FRAME LOADS - GRAVITY":                            71,
    "FRAME LOADS - DISTRIBUTED":                        72,
    "FRAME LOADS - POINTS":                             73,
    "FRAME LOADS - TEMPERATURE":                        74,
    "AREA LOADS - UNIFORM":                             75,
    "AREA LOADS - UNIFORM TO FRAME":                    76,
    "AREA LOADS - WIND PRESSURE COEFFICIENTS":          77,

    # 8. Spektrum & Seismic
    "FUNCTION - RESPONSE SPECTRUM - TSC-2018":          80,
    "FUNCTION - RESPONSE SPECTRUM - FILE":              81,
    "FUNCTION - RESPONSE SPECTRUM - USER":              82,
    "CASE - RESPONSE SPECTRUM 1 - GENERAL":             83,
    "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS":    84,
    "AUTO SEISMIC - TSC-2018":                          85,
}


def get_priority(table_name: str) -> int:
    return PRIORITY.get(table_name, 999)


def build_router() -> Dict[str, Callable]:
    return {
        "PROGRAM CONTROL":                                  H.handle_program_control,
        "PROJECT INFORMATION":                              H.handle_project_information,
        
        "MATERIAL PROPERTIES 01 - GENERAL":                 H.handle_material_props,
        "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES": H.handle_material_mech,
        
        "FRAME SECTION PROPERTIES 01 - GENERAL":            H.handle_frame_props,
        "FRAME SECTION PROPERTIES 04 - AUTO SELECT":         H.handle_auto_select_lists,
        "AREA SECTION PROPERTIES":                          H.handle_area_props,
        "LINK PROPERTY DEFINITIONS 01 - GENERAL":           H.handle_link_props,
        
        "LOAD PATTERN DEFINITIONS":                         H.handle_load_patterns,
        "LOAD CASE DEFINITIONS":                            H.handle_load_cases,
        "CASE - STATIC 1 - LOAD ASSIGNMENTS":               H.handle_static_assignments,
        "CASE - MODAL 1 - GENERAL":                         H.handle_modal_cases,
        "COMBINATION DEFINITIONS":                          H.handle_combinations,
        "MASS SOURCE":                                      H.handle_mass_source,
        
        "JOINT COORDINATES":                                H.handle_joints,
        "JOINT RESTRAINT ASSIGNMENTS":                      H.handle_joint_restraints,
        "CONNECTIVITY - FRAME":                             H.handle_frame_conn,
        "CONNECTIVITY - AREA":                              H.handle_area_conn,
        "CONNECTIVITY - LINK":                              H.handle_link_conn,
        
        "FRAME SECTION ASSIGNMENTS":                        H.handle_frame_assign,
        "AREA SECTION ASSIGNMENTS":                         H.handle_area_assign,
        "LINK PROPERTY ASSIGNMENTS":                        H.handle_link_assign,
        "FRAME RELEASE ASSIGNMENTS 1 - GENERAL":            H.handle_frame_releases,
        
        "JOINT LOADS - FORCE":                              H.handle_joint_loads,
        "FRAME LOADS - GRAVITY":                            H.handle_frame_gravity,
        "FRAME LOADS - DISTRIBUTED":                        H.handle_frame_distributed,
        "FRAME LOADS - POINTS":                             H.handle_frame_points,
        "FRAME LOADS - TEMPERATURE":                        H.handle_frame_temperature,
        "AREA LOADS - UNIFORM":                             H.handle_area_uniform,
        "AREA LOADS - UNIFORM TO FRAME":                    H.handle_area_uniform_to_frame,
        "AREA LOADS - WIND PRESSURE COEFFICIENTS":          H.handle_area_wind,

        "FUNCTION - RESPONSE SPECTRUM - TSC-2018":          H.handle_spectrum_functions_TSC,
        "FUNCTION - RESPONSE SPECTRUM - FILE":              H.handle_spectrum_functions_file,
        "FUNCTION - RESPONSE SPECTRUM - USER":              H.handle_spectrum_functions_user,
        "CASE - RESPONSE SPECTRUM 1 - GENERAL":             H.handle_response_spectrum_gen,
        "CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS":    H.handle_response_spectrum_assign,
        "AUTO SEISMIC - TSC-2018":                          H.handle_auto_seismic,
    }


def build_sorted_router() -> List[Tuple[str, Callable]]:
    router = build_router()
    items = [(name, handler, get_priority(name)) for name, handler in router.items()]
    items.sort(key=lambda x: x[2])
    return [(name, handler) for name, handler, _ in items]