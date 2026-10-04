# tools/s2k/builder.py
"""
LoadContext → Scene inşası.
"""
from typing import Dict, Tuple

import pandas as pd

from logging_config import CadLogger
from domain.element import Node, Frame, Area, Link
from domain.definition import (
    Section, SectionType, Restraint, ObjType,
    PointLoad, FrameGravityLoad, FrameDistributedLoad,
    FramePointLoad, FrameTemperatureLoad,
    AreaUniformLoad, AreaUniformToFrameLoad,
    AreaWindPressureLoad, LoadDirection,
)
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder
from tools.s2k.context import LoadContext
from tools.s2k.utils import safe_float

logger = CadLogger.get(__name__)


def build_scene(ctx: LoadContext) -> Scene:
    builder = SceneBuilder()
    
    _register_definitions(builder, ctx)
    node_map = _create_nodes(builder, ctx)
    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    area_map, n_areas = _create_areas(builder, ctx, node_map)
    n_links = _create_links(builder, ctx, node_map)
    _assign_loads(ctx, node_map, frame_map, area_map)
    
    logger.info(
        f"[Builder] {len(node_map)} node, {n_frames} frame, "
        f"{n_areas} area, {n_links} link"
    )
    scene = builder.scene
    scene.units = str(ctx.units)
    # scene.project_info = ctx.project_info
    return scene


def _register_definitions(builder: SceneBuilder, ctx: LoadContext):
    def_mgr = builder.def_mgr
    
    def_mgr.project_info = ctx.project_info
    for mat in ctx.materials.values():
        def_mgr.add_material(mat)
    for sec in ctx.sections.values():
        def_mgr.add_section(sec)
    for prop in ctx.link_props.values():
        def_mgr.add_link_prop(prop)
    
    def_mgr.load_patterns = ctx.load_patterns
    def_mgr.load_cases = ctx.load_cases
    def_mgr.modal_cases = ctx.modal_cases
    def_mgr.combinations = ctx.load_combos
    def_mgr.mass_source_map = dict(ctx.mass_source_map)
    
    # Dinamik tanımların aktarımı
    def_mgr.spectrum_functions = ctx.spectrum_functions
    def_mgr.response_spectrum_cases = ctx.response_spectrum_cases
    def_mgr.auto_seismics = ctx.auto_seismics
    


def _create_nodes(builder: SceneBuilder, ctx: LoadContext) -> Dict[str, Node]:
    node_map: Dict[str, Node] = {}
    if ctx.df_joints is None or ctx.df_joints.empty:
        return node_map
    
    restraints = _parse_restraints(ctx.df_restraints)
    
    for _, row in ctx.df_joints.iterrows():
        joint_id = str(row.get('Joint', '')).strip()
        if not joint_id:
            continue
        
        try:
            x = ctx.units.L(float(row.get('XorR', row.get('X', 0))))
            y = ctx.units.L(float(row.get('Y', 0)))
            z = ctx.units.L(float(row.get('Z', 0)))
        except (ValueError, TypeError):
            logger.warning(f"Node {joint_id}: geçersiz koordinat")
            continue
        
        node = builder.create_node(
            x, y, z,
            label=f"N{joint_id}",
            restraint=restraints.get(joint_id),
        )
        node_map[joint_id] = node
    
    return node_map


def _parse_restraints(df: pd.DataFrame) -> Dict[str, dict]:
    if df is None or df.empty:
        return {}
    
    dof_map = {'U1': 'ux', 'U2': 'uy', 'U3': 'uz',
               'R1': 'rx', 'R2': 'ry', 'R3': 'rz'}
    
    restraints = {}
    for _, row in df.iterrows():
        joint_id = str(row.get('Joint', '')).strip()
        if not joint_id:
            continue
        
        rel = {
            our: True for sap, our in dof_map.items()
            if str(row.get(sap, '')).strip().upper() == 'YES'
        }
        if rel:
            restraints[joint_id] = rel
    
    return restraints


def _create_frames(builder: SceneBuilder, ctx: LoadContext, node_map: Dict[str, Node]) -> Tuple[Dict[str, Frame], int]:
    frame_map: Dict[str, Frame] = {}
    if ctx.df_frame_conn is None or ctx.df_frame_conn.empty:
        return frame_map, 0
    
    # Context parametresi dâhil edildi
    frame_assign = _parse_frame_assign(ctx.df_frame_assign, ctx)
    frame_release = _parse_frame_release(ctx.df_frame_release)
    fallback = _get_fallback_section(builder, ctx)
    
    count = 0
    for _, row in ctx.df_frame_conn.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        joint_i = str(row.get('JointI', '')).strip()
        joint_j = str(row.get('JointJ', '')).strip()
        
        if not frame_id or joint_i not in node_map or joint_j not in node_map:
            continue
        
        sect_name, rotation = frame_assign.get(frame_id, ("", 0.0))
        if sect_name not in ctx.sections:
            sect_name = fallback
        
        try:
            frame = builder.create_frame(
                node_map[joint_i],
                node_map[joint_j],
                sect_name,
                rotation_deg=rotation,
                label=f"F{frame_id}",
            )
            
            if frame_id in frame_release:
                frame.release_i = frame_release[frame_id]['i']
                frame.release_j = frame_release[frame_id]['j']
            
            frame_map[frame_id] = frame
            count += 1
        except ValueError as e:
            logger.warning(f"Frame {frame_id}: {e}")
    
    return frame_map, count


def _parse_frame_assign(df: pd.DataFrame, ctx: LoadContext = None) -> Dict[str, Tuple[str, float]]:
    if df is None or df.empty or 'Frame' not in df.columns:
        return {}
    
    result = {}
    for _, row in df.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        if not frame_id: 
            continue
        
        sect = (str(row.get('AnalSect', '')).strip() or str(row.get('Section', '')).strip())
        
        if ctx and sect in ctx.auto_select_lists:
            members = ctx.auto_select_lists[sect]
            if members:
                mid_idx = len(members) // 2
                original = sect
                sect = members[mid_idx]
                logger.debug(f"Frame {frame_id}: '{original}' → '{sect}' (liste ortası)")
        
        try:
            rotation = float(row.get('Angle', 0.0))
        except (ValueError, TypeError):
            rotation = 0.0
        
        result[frame_id] = (sect, rotation)
    
    return result


def _parse_frame_release(df: pd.DataFrame) -> Dict[str, dict]:
    if df is None or df.empty or 'Frame' not in df.columns:
        return {}
    
    i_cols = {'R1': 'PI', 'R2': 'V2I', 'R3': 'V3I', 'R4': 'TI', 'R5': 'M2I', 'R6': 'M3I'}
    j_cols = {'R1': 'PJ', 'R2': 'V2J', 'R3': 'V3J', 'R4': 'TJ', 'R5': 'M2J', 'R6': 'M3J'}
    
    releases = {}
    for _, row in df.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        if not frame_id:
            continue
        
        rel_i = {code: str(row.get(col, 'No')).strip().upper() == 'YES' for code, col in i_cols.items()}
        rel_j = {code: str(row.get(col, 'No')).strip().upper() == 'YES' for code, col in j_cols.items()}
        
        if any(rel_i.values()) or any(rel_j.values()):
            releases[frame_id] = {'i': rel_i, 'j': rel_j}
    
    return releases


def _get_fallback_section(builder: SceneBuilder, ctx: LoadContext) -> str:
    if ctx.sections:
        return next(iter(ctx.sections.keys()))
    
    default = Section(
        name="DEFAULT",
        profile_type=SectionType.RECT,
        profile_params={"h": 200.0, "b": 100.0},
        color=(0.5, 0.5, 0.5),
    )
    builder.def_mgr.add_section(default)
    ctx.sections["DEFAULT"] = default
    return "DEFAULT"


def _create_areas(builder: SceneBuilder, ctx: LoadContext, node_map: Dict[str, Node]) -> Tuple[Dict[str, Area], int]:
    area_map = {}
    if ctx.df_area_conn is None or ctx.df_area_conn.empty:
        return area_map, 0
    
    area_assign = _parse_area_assign(ctx.df_area_assign)
    
    for _, row in ctx.df_area_conn.iterrows():
        area_id = str(row.get('Area', '')).strip()
        
        joints = [node_map[j] for i in range(1, 5) if (j := str(row.get(f'Joint{i}', '')).strip()) in node_map]
        if len(joints) < 3:
            continue
        
        section_name = area_assign.get(area_id, "")
        section_data = ctx.area_sections.get(section_name, {})
        thickness = ctx.units.L(section_data.get("thickness", 100.0))
        
        area = builder.create_area(joints, thickness=thickness, label=f"A{area_id}")
        area.material = section_data.get("material")
        area.section_name = section_name
        
        area_map[area_id] = area
    
    return area_map, len(area_map)


def _parse_area_assign(df: pd.DataFrame) -> Dict[str, str]:
    if df is None or df.empty or 'Area' not in df.columns:
        return {}
    
    result = {}
    for _, row in df.iterrows():
        area_id = str(row.get('Area', '')).strip()
        if not area_id:
            continue
        result[area_id] = str(row.get('Section', '')).strip()
    
    return result


def _create_links(builder: SceneBuilder, ctx: LoadContext, node_map: Dict[str, Node]) -> int:
    if ctx.df_link_conn is None or ctx.df_link_conn.empty:
        return 0
    
    count = 0
    for _, row in ctx.df_link_conn.iterrows():
        link_id = str(row.get('Link', '')).strip()
        joint_i = str(row.get('JointI', '')).strip()
        joint_j = str(row.get('JointJ', '')).strip()
        
        if not link_id or joint_i not in node_map or joint_j not in node_map:
            continue
        
        prop_name = ctx.link_props.get(link_id, "LINK1")
        if hasattr(prop_name, 'name'):
            prop_name = prop_name.name
        
        builder.create_link(
            node_map[joint_i],
            node_map[joint_j],
            prop_name=prop_name,
            label=f"L{link_id}",
        )
        count += 1
    
    return count


def _assign_loads(ctx: LoadContext, node_map: Dict[str, Node], frame_map: Dict[str, Frame], area_map: Dict[str, Area]):
    _load_joint_loads(ctx, node_map)
    _load_frame_loads(ctx, frame_map)
    _load_area_loads(ctx, area_map)


def _parse_direction(dir_str: str) -> LoadDirection:
    d = str(dir_str).strip().upper()
    mapping = {
        "1": LoadDirection.LOCAL_1, "LOCAL1": LoadDirection.LOCAL_1,
        "2": LoadDirection.LOCAL_2, "LOCAL2": LoadDirection.LOCAL_2,
        "3": LoadDirection.LOCAL_3, "LOCAL3": LoadDirection.LOCAL_3,
        "X": LoadDirection.GLOBAL_X, "GX": LoadDirection.GLOBAL_X,
        "Y": LoadDirection.GLOBAL_Y, "GY": LoadDirection.GLOBAL_Y,
        "Z": LoadDirection.GLOBAL_Z, "GZ": LoadDirection.GLOBAL_Z,
        "GRAV": LoadDirection.GRAVITY, "GRAVITY": LoadDirection.GRAVITY,
        "PX": LoadDirection.PROJECTED_X,
        "PY": LoadDirection.PROJECTED_Y,
        "PZ": LoadDirection.PROJECTED_Z,
    }
    return mapping.get(d, LoadDirection.GRAVITY)


def _load_joint_loads(ctx: LoadContext, node_map: Dict[str, Node]):
    df = ctx.df_joint_loads
    if df is None or df.empty:
        return
    
    for _, r in df.iterrows():
        j_id = str(r.get('Joint', '')).strip()
        node = node_map.get(j_id)
        if not node:
            continue
        
        node.loads.append(PointLoad(
            pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
            fx=ctx.units.F(safe_float(r, 'F1')),
            fy=ctx.units.F(safe_float(r, 'F2')),
            fz=ctx.units.F(safe_float(r, 'F3')),
            mx=ctx.units.M(safe_float(r, 'M1')),
            my=ctx.units.M(safe_float(r, 'M2')),
            mz=ctx.units.M(safe_float(r, 'M3')),
        ))


def _load_frame_loads(ctx: LoadContext, frame_map: Dict[str, Frame]):
    df_g = ctx.df_frame_gravity
    if df_g is not None and not df_g.empty:
        for _, r in df_g.iterrows():
            frame = frame_map.get(str(r.get('Frame', '')).strip())
            if frame:
                frame.gravity_loads.append(FrameGravityLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    multiplier_x=safe_float(r, 'MultiplierX'),
                    multiplier_y=safe_float(r, 'MultiplierY'),
                    multiplier_z=safe_float(r, 'MultiplierZ'),
                ))
    
    df_d = ctx.df_frame_distributed
    if df_d is not None and not df_d.empty:
        for _, r in df_d.iterrows():
            frame = frame_map.get(str(r.get('Frame', '')).strip())
            if not frame:
                continue
            
            ftype = str(r.get('Type', 'Force')).upper()
            is_rel = "REL" in str(r.get('DistType', 'RelDist')).upper()
            
            d1 = safe_float(r, 'RelDistA') if is_rel else ctx.units.L(safe_float(r, 'AbsDistA'))
            d2 = safe_float(r, 'RelDistB') if is_rel else ctx.units.L(safe_float(r, 'AbsDistB'))
            
            p1_raw = safe_float(r, 'FOverLA')
            p2_raw = safe_float(r, 'FOverLB', default=p1_raw)
            
            if ftype == 'FORCE':
                p1, p2 = ctx.units.w(p1_raw), ctx.units.w(p2_raw)
            else:
                p1 = ctx.units.M(p1_raw) / ctx.units.length_scale
                p2 = ctx.units.M(p2_raw) / ctx.units.length_scale
            
            frame.dist_loads.append(FrameDistributedLoad(
                pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                force_or_moment=ftype,
                direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                p1=p1, p2=p2, d1=d1, d2=d2, is_relative=is_rel,
            ))


def _load_area_loads(ctx: LoadContext, area_map: Dict[str, Area]):
    df_u = ctx.df_area_uniform
    if df_u is not None and not df_u.empty:
        for _, r in df_u.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                area.uniform_loads.append(AreaUniformLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                    value=ctx.units.area_w(safe_float(r, 'UnifLoad', 0.0)),
                ))
    
    df_utf = ctx.df_area_uniform_to_frame
    if df_utf is not None and not df_utf.empty:
        for _, r in df_utf.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                area.uniform_to_frame_loads.append(AreaUniformToFrameLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    direction=_parse_direction(str(r.get('Dir', 'Gravity'))),
                    value=ctx.units.area_w(safe_float(r, 'UnifLoad', 0.0)),
                    dist_type=str(r.get('DistType', 'One way')).strip(),
                ))
    
    df_w = ctx.df_area_wind
    if df_w is not None and not df_w.empty:
        for _, r in df_w.iterrows():
            if area := area_map.get(str(r.get('Area', '')).strip()):
                is_ww = str(r.get('Windward', 'Yes')).strip().upper() == 'YES'
                area.wind_pressures.append(AreaWindPressureLoad(
                    pattern_name=str(r.get('LoadPat', 'DEFAULT')).strip(),
                    cp=safe_float(r, 'Cp'),
                    windward=is_ww,
                    dist_type=str(r.get('DistType', 'To Joints')).strip(),
                ))