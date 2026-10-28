# tools/s2k/scene_builder.py
"""
Scene inşası: node/frame/area/link + load assignment.
S2K değerleri `float` (S2K birimi) — ProjectBuilder dönüştürür.
"""
from __future__ import annotations

import logging
from collections import defaultdict

import pandas as pd

from domain.definition import (
    AreaUniformLoad,
    AreaUniformToFrameLoad,
    DistType,
    FrameDistributedLoad,
    FrameGravityLoad,
    LoadDirection,
    PointLoad,
)
from domain.element import Area, Frame, Node
from tools.s2k.context import LoadContext
from tools.s2k.handlers.loads import _sap_frame_dir_code

logger = logging.getLogger(__name__)


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ============================================================================
# YARDIMCILAR — parse
# ============================================================================
def _parse_restraints(df: pd.DataFrame) -> dict[str, dict]:
    if df is None or df.empty:
        return {}
    dof_map = {"U1": "ux", "U2": "uy", "U3": "uz", "R1": "rx", "R2": "ry", "R3": "rz"}
    out = {}
    for _, row in df.iterrows():
        jid = str(row.get("Joint", "")).strip()
        if not jid:
            continue
        rel = {our: True for sap, our in dof_map.items()
               if str(row.get(sap, "")).strip().upper() == "YES"}
        if rel:
            out[jid] = rel
    return out


def _parse_frame_assign(df, ctx) -> dict[str, tuple[str, float]]:
    if df is None or df.empty or "Frame" not in df.columns:
        return {}
    out = {}
    for _, row in df.iterrows():
        fid = str(row.get("Frame", "")).strip()
        if not fid:
            continue
        sect = str(row.get("AnalSect", row.get("Section", ""))).strip()
        if ctx and sect in ctx.auto_select_lists:
            members = ctx.auto_select_lists[sect]
            if members:
                sect = members[len(members) // 2]
        out[fid] = (sect, _safe_float(row, "Angle", 0.0))
    return out


def _parse_frame_release(df) -> dict[str, dict]:
    if df is None or df.empty or "Frame" not in df.columns:
        return {}
    i_cols = {"R1": "PI", "R2": "V2I", "R3": "V3I", "R4": "TI", "R5": "M2I", "R6": "M3I"}
    j_cols = {"R1": "PJ", "R2": "V2J", "R3": "V3J", "R4": "TJ", "R5": "M2J", "R6": "M3J"}
    out = {}
    for _, row in df.iterrows():
        fid = str(row.get("Frame", "")).strip()
        if not fid:
            continue
        ri = {c: str(row.get(c, "No")).strip().upper() == "YES" for c in i_cols.values()}
        rj = {c: str(row.get(c, "No")).strip().upper() == "YES" for c in j_cols.values()}
        if any(ri.values()) or any(rj.values()):
            out[fid] = {"i": ri, "j": rj}
    return out


def _parse_area_assign(df) -> dict[str, str]:
    if df is None or df.empty or "Area" not in df.columns:
        return {}
    return {str(r.get("Area", "")).strip(): str(r.get("Section", "")).strip()
            for _, r in df.iterrows() if str(r.get("Area", "")).strip()}


def _parse_link_assign(df) -> dict[str, str]:
    if df is None or df.empty or "Link" not in df.columns:
        return {}
    out = {}
    for _, r in df.iterrows():
        lid = str(r.get("Link", "")).strip()
        if not lid:
            continue
        prop = str(r.get("Prop", r.get("LinkProp", r.get("PropName", "")))).strip()
        if prop:
            out[lid] = prop
    return out


def _sap_area_dir(s: str) -> LoadDirection:
    return {
        "1": LoadDirection.LOCAL_1, "2": LoadDirection.LOCAL_2, "3": LoadDirection.LOCAL_3,
        "X": LoadDirection.GLOBAL_X, "Y": LoadDirection.GLOBAL_Y, "Z": LoadDirection.GLOBAL_Z,
        "GX": LoadDirection.GLOBAL_X, "GY": LoadDirection.GLOBAL_Y, "GZ": LoadDirection.GLOBAL_Z,
        "GRAV": LoadDirection.GRAVITY, "GRAVITY": LoadDirection.GRAVITY,
        "PX": LoadDirection.PROJECTED_X, "PY": LoadDirection.PROJECTED_Y, "PZ": LoadDirection.PROJECTED_Z,
    }.get(str(s).strip().upper(), LoadDirection.GRAVITY)


def _fallback_section_name(builder, ctx) -> str:
    """Hiç section yoksa builder'a DEFAULT ekle."""
    if builder.sections:
        return next(iter(builder.sections.keys()))
    from data.enums import SectionType
    builder.add_section(
        "DEFAULT", profile_type=SectionType.RECT,
        profile_params={"h": 200.0, "b": 100.0}, color=(0.5, 0.5, 0.5),
    )
    ctx.sections.setdefault("DEFAULT", builder.sections["DEFAULT"])
    return "DEFAULT"


# ============================================================================
# NODE / FRAME / AREA / LINK
# ============================================================================
def create_nodes(builder, ctx: LoadContext) -> dict[str, Node]:
    """Node'ları S2K biriminde yarat (float)."""
    if ctx.df_joints is None or ctx.df_joints.empty:
        return {}
    restraints = _parse_restraints(ctx.df_restraints)
    out: dict[str, Node] = {}
    for _, row in ctx.df_joints.iterrows():
        jid = str(row.get("Joint", "")).strip()
        if not jid:
            continue
        try:
            x = float(row.get("XorR", row.get("X", 0)))
            y = float(row.get("Y", 0))
            z = float(row.get("Z", 0))
        except (ValueError, TypeError):
            logger.warning("[Node] %s: geçersiz koordinat", jid)
            continue
        out[jid] = builder.create_node(x, y, z, label=jid, restraint=restraints.get(jid))
    return out


def create_frames(builder, ctx: LoadContext, node_map: dict[str, Node]) -> tuple[dict[str, Frame], int]:
    if ctx.df_frame_conn is None or ctx.df_frame_conn.empty:
        return {}, 0
    assign = _parse_frame_assign(ctx.df_frame_assign, ctx)
    releases = _parse_frame_release(ctx.df_frame_release)
    fallback = _fallback_section_name(builder, ctx)

    out: dict[str, Frame] = {}
    count = 0
    for _, row in ctx.df_frame_conn.iterrows():
        fid = str(row.get("Frame", "")).strip()
        ji = str(row.get("JointI", "")).strip()
        jj = str(row.get("JointJ", "")).strip()
        if not fid or ji not in node_map or jj not in node_map:
            continue
        sect, rot = assign.get(fid, ("", 0.0))
        if not sect or sect not in builder.sections:
            sect = fallback
        try:
            frame = builder.create_frame(
                node_map[ji], node_map[jj], sect,
                rotation_deg=rot, label=fid,
            )
            if fid in releases:
                frame.release_i = releases[fid]["i"]
                frame.release_j = releases[fid]["j"]
            out[fid] = frame
            count += 1
        except Exception as e:
            logger.error("[Frame] %s: %s", fid, e, exc_info=True)
    return out, count


def create_areas(builder, ctx: LoadContext, node_map: dict[str, Node]) -> tuple[dict[str, Area], int]:
    if ctx.df_area_conn is None or ctx.df_area_conn.empty:
        return {}, 0
    assign = _parse_area_assign(ctx.df_area_assign)
    out: dict[str, Area] = {}
    for _, row in ctx.df_area_conn.iterrows():
        aid = str(row.get("Area", "")).strip()
        joints = [node_map[j] for i in range(1, 5)
                  if (j := str(row.get(f"Joint{i}", "")).strip()) in node_map]
        if len(joints) < 3:
            continue
        sname = assign.get(aid, "")
        sdata = ctx.area_sections.get(sname, {})
        try:
            area = builder.create_area(
                joints, thickness=sdata.get("thickness", 100.0),
                label=f"A{aid}",
            )
            area.material = sdata.get("material")
            area.section_name = sname
            out[aid] = area
        except Exception as e:
            logger.error("[Area] %s: %s", aid, e, exc_info=True)
    return out, len(out)


def create_links(builder, ctx: LoadContext, node_map: dict[str, Node]) -> int:
    if ctx.df_link_conn is None or ctx.df_link_conn.empty:
        return 0
    prop_map = _parse_link_assign(ctx.df_link_assign)
    default_prop = next(iter(ctx.link_props), None)
    if default_prop is None:
        return 0
    count = 0
    for _, row in ctx.df_link_conn.iterrows():
        lid = str(row.get("Link", "")).strip()
        ji = str(row.get("JointI", "")).strip()
        jj = str(row.get("JointJ", "")).strip()
        if not lid or ji not in node_map or jj not in node_map:
            continue
        try:
            builder.create_link(
                node_map[ji], node_map[jj],
                prop_name=prop_map.get(lid, default_prop),
                label=lid,
            )
            count += 1
        except Exception as e:
            logger.warning("[Link] %s: %s", lid, e)
    return count


# ============================================================================
# LOAD ASSIGNMENTS
# ============================================================================
def assign_loads(ctx: LoadContext, node_map, frame_map, area_map) -> None:
    _load_joint_loads(ctx, node_map)
    _load_frame_loads(ctx, frame_map)
    _load_area_loads(ctx, area_map)


def _load_joint_loads(ctx: LoadContext, node_map):
    if ctx.df_joint_loads is None or ctx.df_joint_loads.empty:
        return
    for _, r in ctx.df_joint_loads.iterrows():
        node = node_map.get(str(r.get("Joint", "")).strip())
        if node is None:
            continue
        node.loads.append(PointLoad(
            pattern_name=str(r.get("LoadPat", "DEFAULT")).strip(),
            fx=_safe_float(r, "F1"),
            fy=_safe_float(r, "F2"),
            fz=_safe_float(r, "F3"),
            mx=_safe_float(r, "M1"),
            my=_safe_float(r, "M2"),
            mz=_safe_float(r, "M3"),
        ))


def _load_frame_loads(ctx: LoadContext, frame_map):
    # Gravity
    if ctx.df_frame_gravity is not None and not ctx.df_frame_gravity.empty:
        for _, r in ctx.df_frame_gravity.iterrows():
            frame = frame_map.get(str(r.get("Frame", "")).strip())
            if frame:
                frame.gravity_loads.append(FrameGravityLoad(
                    pattern_name=str(r.get("LoadPat", "DEFAULT")).strip(),
                    multiplier_x=_safe_float(r, "MultiplierX"),
                    multiplier_y=_safe_float(r, "MultiplierY"),
                    multiplier_z=_safe_float(r, "MultiplierZ"),
                ))

    # Distributed
    if ctx.df_frame_distributed is None or ctx.df_frame_distributed.empty:
        return
    per_frame = defaultdict(list)
    for _, r in ctx.df_frame_distributed.iterrows():
        fid = str(r.get("Frame", "")).strip()
        if not fid or fid not in frame_map:
            continue
        pat = str(r.get("LoadPat", "DEFAULT")).strip()
        csys = str(r.get("CoordSys", "Local")).strip()
        load_dir = _sap_frame_dir_code(str(r.get("Dir", "Gravity")))
        is_rel = "REL" in str(r.get("DistType", "RelDist")).upper()
        if is_rel:
            x1 = _safe_float(r, "RelDistA", 0.0)
            x2 = _safe_float(r, "RelDistB", 1.0)
        else:
            L = frame_map[fid].get_length()
            x1 = _safe_float(r, "DistA", 0.0) / L if L > 0 else 0.0
            x2 = _safe_float(r, "DistB", L) / L if L > 0 else 1.0
        ftype = str(r.get("Type", "Force")).upper()
        v1 = _safe_float(r, "FOverLA", 0.0)
        v2 = _safe_float(r, "FOverLB", v1)
        per_frame[fid].append({
            "pattern": pat, "csys": csys, "load_dir": load_dir,
            "is_rel": is_rel, "x1": x1, "x2": x2, "v1": v1, "v2": v2,
        })

    for fid, rows in per_frame.items():
        frame = frame_map[fid]
        by_pat = defaultdict(list)
        for row in rows:
            by_pat[row["pattern"]].append(row)
        for pat, items in by_pat.items():
            first = items[0]
            csys_norm = "Global" if first["csys"].lower().startswith("g") else "Local"
            load_set = FrameDistributedLoad(
                pattern_name=pat, coord_sys=csys_norm,
                load_dir=first["load_dir"], mode="REPLACE",
                is_relative=first["is_rel"], segments=[],
            )
            for it in items:
                load_set.add_segment(x1=it["x1"], x2=it["x2"], q1=it["v1"], q2=it["v2"])
            frame.dist_load_sets[pat] = load_set
            frame.dist_loads.extend(load_set.to_sap_loads())


def _load_area_loads(ctx: LoadContext, area_map):
    if ctx.df_area_uniform is not None and not ctx.df_area_uniform.empty:
        for _, r in ctx.df_area_uniform.iterrows():
            area = area_map.get(str(r.get("Area", "")).strip())
            if area:
                area.uniform_loads.append(AreaUniformLoad(
                    pattern_name=str(r.get("LoadPat", "DEFAULT")).strip(),
                    direction=_sap_area_dir(str(r.get("Dir", "Gravity"))),
                    value=_safe_float(r, "UnifLoad"),
                ))
    if ctx.df_area_uniform_to_frame is not None and not ctx.df_area_uniform_to_frame.empty:
        for _, r in ctx.df_area_uniform_to_frame.iterrows():
            area = area_map.get(str(r.get("Area", "")).strip())
            if area:
                area.uniform_to_frame_loads.append(AreaUniformToFrameLoad(
                    pattern_name=str(r.get("LoadPat", "DEFAULT")).strip(),
                    direction=_sap_area_dir(str(r.get("Dir", "Gravity"))),
                    value=_safe_float(r, "UnifLoad"),
                    dist_type=DistType.from_input(r.get("DistType", "One way")),
                    coordinate_system=str(r.get("CoordSys", "GLOBAL")).strip(),
                ))
                
def assign_joint_loads(ctx, node_map):
    """ctx.joint_loads'u node.loads'a bağla."""
    for joint_name, loads in ctx.joint_loads.items():
        node = node_map.get(joint_name)
        if node is None:
            continue
        node.loads.extend(loads)
    return len(ctx.joint_loads)