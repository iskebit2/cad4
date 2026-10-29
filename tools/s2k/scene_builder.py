# tools/s2k/scene_builder.py
"""Scene inşası: node/frame/area/link + load assignment.

S2K değerleri float (S2K CurrUnits) — dönüşüm convert_project_units'te.
"""
from __future__ import annotations

import logging
from collections import defaultdict

import pandas as pd
import numpy as np

from domain.definition import (
    AreaSection,
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


# ============================================================================
# YARDIMCILAR
# ============================================================================

def _order_polygon_nodes(nodes: list[Node]) -> list[Node]:
    """Poligon düğümlerini sırala — kelebek düzeltir.

    3 olası 2D projeksiyon dener (XY, XZ, YZ), her birinde açısal
    sıralama yapar, shoelace alanı en büyük olanı seçer.
    """
    if len(nodes) < 3:
        return nodes
    if len(nodes) == 3:
        return nodes

    import numpy as np
    pts = np.array([[n.x, n.y, n.z] for n in nodes], dtype=float)
    centroid = pts.mean(axis=0)
    rel = pts - centroid

    def _shoelace(proj_pts: np.ndarray) -> float:
        N = len(proj_pts)
        s = 0.0
        for i in range(N):
            a = proj_pts[i]
            b = proj_pts[(i + 1) % N]
            s += a[0] * b[1] - b[0] * a[1]
        return abs(s) * 0.5

    best_area = -1.0
    best_order = list(range(len(nodes)))

    for keep in [(0, 1), (0, 2), (1, 2)]:
        proj = rel[:, keep]
        angles = np.arctan2(proj[:, 1], proj[:, 0])
        order = np.argsort(angles)

        for cand in (order, order[::-1]):
            area = _shoelace(proj[cand])
            if area > best_area:
                best_area = area
                best_order = list(cand)

    return [nodes[i] for i in best_order]

def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _opt_float(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "None", "nan", "NaN"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _to_bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().upper() in ("YES", "TRUE", "1")


# ============================================================================
# PARSER
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


def _parse_area_assign(df) -> dict[str, dict]:
    """AREA SECTION ASSIGNMENTS → {area_id: {section, mat_prop, thick_over, offset_over}}."""
    if df is None or df.empty or "Area" not in df.columns:
        return {}
    out: dict[str, dict] = {}
    for _, r in df.iterrows():
        aid = str(r.get("Area", "")).strip()
        if not aid:
            continue
        out[aid] = {
            "section": str(r.get("Section", "")).strip(),
            "mat_prop": str(r.get("MatProp", "")).strip(),
            "thick_over": _opt_float(r.get("ThickOver")),
            "offset_over": _opt_float(r.get("OffsetOver")),
        }
    return out


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
# NODE
# ============================================================================
def create_nodes(builder, ctx: LoadContext) -> dict[str, Node]:
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

        node = builder.create_node(x, y, z, label=jid, restraint=restraints.get(jid))
        node.coord_sys = str(row.get("CoordSys", "GLOBAL")).strip()
        node.coord_type = str(row.get("CoordType", "Cartesian")).strip()
        node.special_jt = _to_bool(row.get("SpecialJt"), False)
        out[jid] = node

    _apply_joint_constraints(ctx, out)
    _apply_joint_added_mass(ctx, out)
    return out


def _apply_joint_constraints(ctx: LoadContext, node_map: dict[str, Node]) -> None:
    for jid, cname in ctx.joint_constraints.items():
        node = node_map.get(jid)
        if node is not None:
            node.constraint_name = cname


def _apply_joint_added_mass(ctx: LoadContext, node_map: dict[str, Node]) -> None:
    if not ctx.joint_added_mass:
        return
    for jid, data in ctx.joint_added_mass.items():
        node = node_map.get(jid)
        if node is None:
            continue
        node.mass_coord_sys = str(data.get("coord_sys", "Joint Local"))
        node.added_mass_1 = float(data.get("mass1", 0.0) or 0.0)
        node.added_mass_2 = float(data.get("mass2", 0.0) or 0.0)
        node.added_mass_3 = float(data.get("mass3", 0.0) or 0.0)
        node.added_mmi_1 = float(data.get("mmi1", 0.0) or 0.0)
        node.added_mmi_2 = float(data.get("mmi2", 0.0) or 0.0)
        node.added_mmi_3 = float(data.get("mmi3", 0.0) or 0.0)


# ============================================================================
# FRAME
# ============================================================================
def create_frames(
    builder, ctx: LoadContext, node_map: dict[str, Node],
) -> tuple[dict[str, Frame], int]:
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

    # --- frame parametrelerini bağla ---
    _apply_frame_insertion_points(ctx, out)
    _apply_frame_end_offsets(ctx, out)
    _apply_frame_output_stations(ctx, out)
    _apply_frame_auto_mesh(ctx, out)
    _apply_frame_modifiers(ctx, out)
    _apply_frame_design_procs(ctx, out)
    _apply_frame_time_dependent(ctx, out)

    return out, count


def _apply_frame_insertion_points(ctx, frame_map):
    for fid, data in ctx.frame_insertion_points.items():
        frame = frame_map.get(fid)
        if frame is None:
            continue
        frame.cardinal_pt = str(data.get("cardinal_pt", "10 (centroid)"))
        frame.mirror2 = _to_bool(data.get("mirror2"))
        frame.mirror3 = _to_bool(data.get("mirror3"))
        frame.transform = _to_bool(data.get("transform"), True)
        frame.insertion_coord_sys = str(data.get("coord_sys", "Local"))
        frame.jt_offset_i = (
            float(data.get("jt_offset_xi", 0.0) or 0.0),
            float(data.get("jt_offset_yi", 0.0) or 0.0),
            float(data.get("jt_offset_zi", 0.0) or 0.0),
        )
        frame.jt_offset_j = (
            float(data.get("jt_offset_xj", 0.0) or 0.0),
            float(data.get("jt_offset_yj", 0.0) or 0.0),
            float(data.get("jt_offset_zj", 0.0) or 0.0),
        )


def _apply_frame_end_offsets(ctx, frame_map):
    for fid, data in ctx.frame_end_offsets.items():
        frame = frame_map.get(fid)
        if frame is None:
            continue
        frame.offset_type = str(data.get("type", "User"))
        frame.offset_length_i = float(data.get("length_i", 0.0) or 0.0)
        frame.offset_length_j = float(data.get("length_j", 0.0) or 0.0)
        frame.rigid_factor = float(data.get("rigid_factor", 0.0) or 0.0)


def _apply_frame_output_stations(ctx, frame_map):
    df = getattr(ctx, "df_frame_output_stations", None)
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        frame = frame_map.get(str(r.get("Frame", "")).strip())
        if frame is None:
            continue
        frame.station_type = str(r.get("StationType", "MinNumSta")).strip()
        try:
            frame.min_num_sta = int(float(r.get("MinNumSta", 3)))
        except (TypeError, ValueError):
            frame.min_num_sta = 3
        frame.add_at_elm_int = _to_bool(r.get("AddAtElmInt"), True)
        frame.add_at_pt_load = _to_bool(r.get("AddAtPtLoad"), True)
        frame.max_sta_spcg = _opt_float(r.get("MaxStaSpcg"))


def _apply_frame_auto_mesh(ctx, frame_map):
    for fid, data in ctx.frame_auto_mesh.items():
        frame = frame_map.get(fid)
        if frame is None:
            continue
        frame.auto_mesh = _to_bool(data.get("auto_mesh", data.get("auto_divide")), False)
        frame.mesh_at_joints = _to_bool(data.get("at_joints"), False)
        frame.mesh_at_frames = _to_bool(data.get("at_frames"), False)
        try:
            frame.mesh_num_segments = int(float(data.get("num_segments", 0) or 0))
        except (TypeError, ValueError):
            frame.mesh_num_segments = 0
        frame.mesh_max_length = float(data.get("max_length", 0.0) or 0.0)
        frame.mesh_max_degrees = float(data.get("max_degrees", 0.0) or 0.0)


def _apply_frame_modifiers(ctx, frame_map):
    for fid, mods in ctx.frame_modifiers.items():
        frame = frame_map.get(fid)
        if frame is not None:
            frame.modifiers = dict(mods)


def _apply_frame_design_procs(ctx, frame_map):
    for fid, proc in ctx.frame_design_procs.items():
        frame = frame_map.get(fid)
        if frame is not None:
            frame.design_proc = proc


def _apply_frame_time_dependent(ctx, frame_map):
    df = getattr(ctx, "df_frame_time_dependent", None)
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        frame = frame_map.get(str(r.get("SectionName", "")).strip())
        if frame is None:
            continue
        frame.time_dependent = {
            "type_size": str(r.get("TypeSize", "Auto")).strip(),
            "auto_sf_size": _safe_float(r, "AutoSFSize", 1.0),
        }


# ============================================================================
# AREA
# ============================================================================
def create_areas(
    builder, ctx: LoadContext, node_map: dict[str, Node],
) -> tuple[dict[str, Area], int]:
    if ctx.df_area_conn is None or ctx.df_area_conn.empty:
        return {}, 0

    assign = _parse_area_assign(ctx.df_area_assign)
    out: dict[str, Area] = {}

    for _, row in ctx.df_area_conn.iterrows():
        aid = str(row.get("Area", "")).strip()
        if not aid:
            continue

        # --- düğümleri topla (3 veya 4) ---
        joints: list[Node] = []
        for i in range(1, 5):
            jid = str(row.get(f"Joint{i}", "")).strip()
            node = node_map.get(jid)
            if node is not None:
                joints.append(node)
        if len(joints) < 3:
            continue

        # ★ Kelebek düzeltme
        joints = _order_polygon_nodes(joints)

        adata = assign.get(aid, {})
        sname = adata.get("section", "")
        sec_obj: AreaSection | None = ctx.area_section_objects.get(sname)

        if sec_obj is not None:
            thickness = sec_obj.thickness
            material = sec_obj.material
        else:
            sdata = ctx.area_sections.get(sname, {})
            thickness = sdata.get("thickness", 100.0)
            material = sdata.get("material")

        try:
            area = builder.create_area(joints, thickness=thickness, label=f"A{aid}")
        except Exception as e:
            logger.error("[Area] %s: %s", aid, e, exc_info=True)
            continue

        area.section_name = sname
        area.area_section = sec_obj
        area.material = material
        area.mat_prop = adata.get("mat_prop", "")
        area.thick_over = adata.get("thick_over")
        area.offset_over = adata.get("offset_over")

        out[aid] = area

    return out, len(out)


# ============================================================================
# LINK
# ============================================================================
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
    _load_frame_loads(ctx, frame_map)
    _load_area_loads(ctx, area_map)


def assign_joint_loads(ctx: LoadContext, node_map) -> int:
    """ctx.joint_loads (dict) → node.loads. Tek kaynak."""
    if not ctx.joint_loads:
        return 0
    count = 0
    for joint_name, loads in ctx.joint_loads.items():
        node = node_map.get(joint_name)
        if node is None:
            continue
        node.loads.extend(loads)
        count += 1
    return count


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
            # NOT: dist_loads ÇİFT DÖNÜŞÜM riski nedeniyle DOLDURULMAZ.
            # Tek doğruluk kaynağı: frame.dist_load_sets.


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