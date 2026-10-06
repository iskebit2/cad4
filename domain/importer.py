# domain/importer.py
"""
SAP2000 -> CAD4 importer.

Tek sorumluluk:
    SAP2000 OAPI nesnelerini mevcut CAD4 domain nesnelerine dönüştürmek.

Importer yeni domain sınıfları üretmez.
Mevcut domain.definition ve domain.element sınıflarını kullanır.

Ana giriş:
    model = import_model(sap)

Sonuç:
    model["materials"]
    model["sections"]
    model["area_sections"]
    model["link_properties"]
    model["nodes"]
    model["frames"]
    model["areas"]
    model["links"]
"""

from __future__ import annotations

import logging
from typing import Any

from domain.definition import (
    AreaGravityLoad,
    AreaRefTemperatureLoad,
    AreaStrainLoad,
    AreaSurfacePressureLoad,
    AreaTemperatureLoad,
    AreaUniformLoad,
    AreaUniformToFrameLoad,
    AreaWindPressureLoad,
    FrameDistributedLoad,
    FrameGravityLoad,
    FramePointLoad,
    FrameTemperatureLoad,
    LoadDirection,
    PointLoad,
    Restraint,
)

from domain.element import Node, Frame, Area, Link

from domain.sect_mat import (
    get_materials,
    get_all_sections,
    get_area_sections,
    get_link_properties,
)

logger = logging.getLogger(__name__)


# ============================================================================
# GENEL YARDIMCILAR
# ============================================================================

def _ret_ok(ret: Any) -> bool:
    """SAP OAPI ret kodu başarılı mı?"""
    try:
        return int(ret) == 0
    except (TypeError, ValueError):
        return ret in (None, False)


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_list(value):
    """SAP tuple / list / scalar değerini listeye çevir."""
    if value is None:
        return []

    if isinstance(value, (tuple, list)):
        return list(value)

    return [value]


def _item_count(*values) -> int:
    """SAP GetLoad* çıktılarından güvenli item sayısı."""
    lengths = [
        len(v)
        for v in values
        if isinstance(v, (tuple, list))
    ]

    return min(lengths) if lengths else 0


def _direction(value) -> LoadDirection | None:
    """
    SAP direction -> CAD4 LoadDirection.

    ÖNEMLİ:
    SAP2000 Dir değerlerinin tüm OAPI anlamları burada tahmin edilmez.
    Bilinen string yönler çevrilir; bilinmeyen değer None döner.

    SAP tarafındaki gerçek mapping tools.sap_connect içinde
    doğrulanmışsa burada ayrıca kullanılabilir.
    """
    if isinstance(value, LoadDirection):
        return value

    if value is None:
        return None

    s = str(value).strip().upper()

    mapping = {
        "GX": LoadDirection.GLOBAL_X,
        "GY": LoadDirection.GLOBAL_Y,
        "GZ": LoadDirection.GLOBAL_Z,
        "GLOBAL_X": LoadDirection.GLOBAL_X,
        "GLOBAL_Y": LoadDirection.GLOBAL_Y,
        "GLOBAL_Z": LoadDirection.GLOBAL_Z,

        "1": LoadDirection.LOCAL_1,
        "2": LoadDirection.LOCAL_2,
        "3": LoadDirection.LOCAL_3,

        "LOCAL_1": LoadDirection.LOCAL_1,
        "LOCAL_2": LoadDirection.LOCAL_2,
        "LOCAL_3": LoadDirection.LOCAL_3,

        "GRAV": LoadDirection.GRAVITY,
        "GRAVITY": LoadDirection.GRAVITY,

        "PX": LoadDirection.PROJECTED_X,
        "PY": LoadDirection.PROJECTED_Y,
        "PZ": LoadDirection.PROJECTED_Z,

        "PROJECTED_X": LoadDirection.PROJECTED_X,
        "PROJECTED_Y": LoadDirection.PROJECTED_Y,
        "PROJECTED_Z": LoadDirection.PROJECTED_Z,
    }

    return mapping.get(s)


def _append(obj, attr: str, value) -> None:
    """Liste alanına güvenli append."""
    collection = getattr(obj, attr, None)

    if collection is None:
        collection = []
        setattr(obj, attr, collection)

    collection.append(value)


def _set_if(obj, attr: str, value) -> None:
    """Domain nesnesinde alanı güvenli şekilde set et."""
    setattr(obj, attr, value)


def collect_required_points(sap, selected):
    """Seçili Frame/Area/Link elemanlarının kullandığı Point isimlerini toplar."""
    point_names = set()

    for obj in selected:
        obj_type = obj["type"]
        name = obj["name"]

        if obj_type == "Point":
            point_names.add(name)

        elif obj_type == "Frame":
            point_i, point_j = sap.get_frame_points(name)
            point_names.add(point_i)
            point_names.add(point_j)

        elif obj_type == "Area":
            _, names, _ = sap.get_area_points(name)
            point_names.update(names)

        elif obj_type == "Link":
            point_i, point_j, _ = sap.get_link_points(name)
            point_names.add(point_i)
            point_names.add(point_j)

    return point_names


def select_required_points(sap, point_names):
    """Gerekli Point'leri SAP2000 selection'a ekler."""
    for point_name in point_names:
        ret = sap.SapModel.PointObj.SetSelected(point_name, True)

        if ret != 0:
            print(f"Point seçilemedi: {point_name}")


def prepare_point_selection(sap, selected):
    """Seçili elemanlardan gerekli Point'leri belirler ve SAP'de seçer."""
    point_names = collect_required_points(sap, selected)
    select_required_points(sap, point_names)
    return point_names

# ============================================================================
# NODE
# ============================================================================

def import_nodes(sap) -> dict[str, Node]:
    """
    SAP PointObj -> CAD4 Node.

    Tek bir Node nesnesi oluşturulur.
    Frame / Area / Link importer'ları bu sözlüğü kullanır.
    """

    sap_model = sap.SapModel
    nodes: dict[str, Node] = {}

    selected = sap.get_selected_objects()

    point_names = [
        item["name"]
        for item in selected
        if item.get("type") == "Point"
    ]

    for name in point_names:
        try:
            x, y, z = sap.get_point_coords(name)

            restraint_value, ret = (
                sap_model.PointObj.GetRestraint(name)
            )

            if not _ret_ok(ret):
                restraint_value = (False,) * 6

            restraint = Restraint.from_list(
                list(restraint_value)
            )

            # --------------------------------------------------------------
            # Kütle
            # --------------------------------------------------------------

            mass, ret = sap_model.PointObj.GetMass(name)

            if not _ret_ok(ret):
                mass = (0.0,) * 6

            mass = tuple(
                _safe_float(v)
                for v in _as_list(mass)[:6]
            )

            if len(mass) < 6:
                mass += (0.0,) * (6 - len(mass))

            # --------------------------------------------------------------
            # Yay
            # --------------------------------------------------------------

            spring, ret = sap_model.PointObj.GetSpring(name)

            if not _ret_ok(ret):
                spring = (0.0,) * 6

            spring = tuple(
                _safe_float(v)
                for v in _as_list(spring)[:6]
            )

            if len(spring) < 6:
                spring += (0.0,) * (6 - len(spring))

            node = Node(
                x=x,
                y=y,
                z=z,
                label=name,
                restraint=restraint,
                mass=mass,
                spring=spring,
            )

            nodes[name] = node

        except Exception:
            logger.exception("Node import failed: %s", name)

    return nodes


# ============================================================================
# FRAME
# ============================================================================

def _import_frame_releases(
    sap,
    frame,
) -> None:
    """Frame end releases."""

    name = frame.label

    try:
        ii, jj, start_value, end_value, ret = (
            sap.SapModel.FrameObj.GetReleases(name)
        )

        if not _ret_ok(ret):
            return

        # Solver'ın mevcut kullandığı yapı:
        # release_i / release_j -> {'R1': bool, ..., 'R6': bool}

        release_i = {
            f"R{i + 1}": bool(value)
            for i, value in enumerate(
                _as_list(ii)[:6]
            )
        }

        release_j = {
            f"R{i + 1}": bool(value)
            for i, value in enumerate(
                _as_list(jj)[:6]
            )
        }

        _set_if(frame, "release_i", release_i)
        _set_if(frame, "release_j", release_j)

        # Start/End partial release stiffness değerlerini de kaybetme.
        _set_if(
            frame,
            "release_start_values",
            tuple(
                _safe_float(v)
                for v in _as_list(start_value)[:6]
            ),
        )

        _set_if(
            frame,
            "release_end_values",
            tuple(
                _safe_float(v)
                for v in _as_list(end_value)[:6]
            ),
        )

    except Exception:
        logger.exception(
            "Frame releases import failed: %s",
            name,
        )


def _import_frame_local_axes(
    sap,
    frame,
) -> None:
    """Frame local-axis rotation."""

    name = frame.label

    try:
        value, Advanced, ret = sap.SapModel.FrameObj.GetLocalAxes(name)

        # SAP OAPI'den gelen açı.
        # Tek açı ise mevcut Frame API'sine rotation_deg olarak aktar.
        if isinstance(value, (tuple, list)):
            angle = value[0] if value else 0.0
        else:
            angle = value

        _set_if(
            frame,
            "rotation_deg",
            _safe_float(angle),
        )

    except Exception:
        logger.exception(
            "Frame local axis import failed: %s",
            name,
        )


def _import_frame_loads(
    sap,
    frame,
) -> None:
    """Frame üzerindeki bütün yükleri içeri aktar."""

    name = frame.label
    model = sap.SapModel

    # ----------------------------------------------------------------------
    # Point loads
    # ----------------------------------------------------------------------

    try:
        (numberitems,
         frame_names,
            load_pat,
            my_type,
            c_sys,
            dir_,
            reldist,
            dist,
            val,
            group,
        ) = model.FrameObj.GetLoadPoint(name)

        
        n = _item_count(
            load_pat,
            my_type,
            c_sys,
            dir_,
            dist,
            val,
        )

        for i in range(n):
            direction = _direction(dir_[i])

            if direction is None:
                direction = str(dir_[i])

            load = FramePointLoad(
                pattern_name=str(load_pat[i]),
                force_or_moment=str(my_type[i]),
                direction=direction,
                value=_safe_float(val[i]),
                distance=_safe_float(dist[i]),
            )

            # Domain sınıfında henüz CSys yoksa bile veri kaybolmasın.
            _set_if(
                load,
                "coordinate_system",
                str(c_sys[i]),
            )

            _append(
                frame,
                "point_loads",
                load,
            )

    except Exception:
        logger.exception(
            "Frame point loads import failed: %s",
            name,
        )

    # ----------------------------------------------------------------------
    # Distributed loads
    # ----------------------------------------------------------------------

    try:
        (numberitems,frame_names,
            load_pat,
            my_type,
            c_sys,
            dir_,
            rd1,
            rd2,
            dist1,
            dist2,
            val1,
            val2,
            group,
        ) = model.FrameObj.GetLoadDistributed(name)

    
        n = _item_count(
            load_pat,
            my_type,
            c_sys,
            dir_,
            rd1,
            rd2,
            dist1,
            dist2,
            val1,
            val2,
        )

        for i in range(n):
            direction = _direction(dir_[i])

            if direction is None:
                direction = str(dir_[i])

            load = FrameDistributedLoad(
                pattern_name=str(load_pat[i]),
                force_or_moment=str(my_type[i]),
                direction=direction,
                p1=_safe_float(val1[i]),
                p2=_safe_float(val2[i]),
                d1=_safe_float(dist1[i]),
                d2=_safe_float(dist2[i]),
                is_relative=True,
            )

            _set_if(
                load,
                "coordinate_system",
                str(c_sys[i]),
            )

            # Relative/absolute mesafeyi SAP'ten koru.
            _set_if(
                load,
                "relative_start",
                _safe_float(rd1[i]),
            )

            _set_if(
                load,
                "relative_end",
                _safe_float(rd2[i]),
            )

            _append(
                frame,
                "dist_loads",
                load,
            )

    except Exception:
        logger.exception(
            "Frame distributed loads import failed: %s",
            name,
        )

    # ----------------------------------------------------------------------
    # Gravity
    # ----------------------------------------------------------------------

    try:
        (numberitems,frame_names,
            load_pat,
            c_sys,
            wx,
            wy,
            wz,
            ret,
        ) = model.FrameObj.GetLoadGravity(name)

    
        n = _item_count(
            load_pat,
            wx,
            wy,
            wz,
        )

        for i in range(n):
            load = FrameGravityLoad(
                pattern_name=str(load_pat[i]),
                multiplier_x=_safe_float(wx[i]),
                multiplier_y=_safe_float(wy[i]),
                multiplier_z=_safe_float(wz[i]),
            )

            _append(
                frame,
                "gravity_loads",
                load,
            )

    except Exception:
        logger.exception(
            "Frame gravity loads import failed: %s",
            name,
        )

    # ----------------------------------------------------------------------
    # Temperature
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            temp_type,
            val,
            ret,
        ) = model.FrameObj.GetLoadTemperature(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                temp_type,
                val,
            )

            for i in range(n):
                _append(
                    frame,
                    "temperature_loads",
                    FrameTemperatureLoad(
                        pattern_name=str(load_pat[i]),
                        temp_type=str(temp_type[i]),
                        val=_safe_float(val[i]),
                    ),
                )

    except Exception:
        # Bazı SAP modellerinde bu API çağrısı desteklenmeyebilir.
        logger.debug(
            "No frame temperature loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Load transfer
    # ----------------------------------------------------------------------

    try:
        value, ret = model.FrameObj.GetLoadTransfer(name)

        if _ret_ok(ret):
            _set_if(
                frame,
                "load_transfer",
                bool(value),
            )

    except Exception:
        logger.debug(
            "Frame load-transfer import failed: %s",
            name,
            exc_info=True,
        )


def import_frames(
    sap,
    nodes: dict[str, Node],
    sections: dict[str, Any],
) -> dict[str, Frame]:
    """
    SAP FrameObj -> CAD4 Frame.

    Node'lar kesinlikle yeniden oluşturulmaz.
    """

    model = sap.SapModel
    frames: dict[str, Frame] = {}

    selected = sap.get_selected_objects()

    frame_names = [
        item["name"]
        for item in selected
        if item.get("type") == "Frame"
    ]

    for name in frame_names:
        try:
            point_i, point_j, ret = (
                model.FrameObj.GetPoints(name)
            )

            if not _ret_ok(ret):
                continue

            node_i = nodes.get(point_i)
            node_j = nodes.get(point_j)

            if node_i is None or node_j is None:
                logger.warning(
                    "Frame %s: node not found (%s, %s)",
                    name,
                    point_i,
                    point_j,
                )
                continue

            prop_name, SAuto, ret = (
                model.FrameObj.GetSection(name)
            )

            print(f"prop_name: {prop_name}")
            section = sections.get(prop_name)

            frame = Frame(
                node_i=node_i,
                node_j=node_j,
                section=section,
                label=name,
            )

            _set_if(frame, "propname", prop_name)

            _import_frame_releases(
                sap,
                frame,
            )

            _import_frame_local_axes(
                sap,
                frame,
            )

            _import_frame_loads(
                sap,
                frame,
            )

            node_i.add_connection(frame)
            node_j.add_connection(frame)

            frames[name] = frame

        except Exception:
            logger.exception(
                "Frame import failed: %s",
                name,
            )

    return frames


# ============================================================================
# AREA
# ============================================================================

def _import_area_loads(
    sap,
    area,
) -> None:
    """Area üzerindeki bütün yükleri aktar."""

    name = area.label
    model = sap.SapModel

    # ----------------------------------------------------------------------
    # Gravity
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            wx,
            wy,
            wz,
            ret,
        ) = model.AreaObj.GetLoadGravity(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                wx,
                wy,
                wz,
            )

            for i in range(n):
                _append(
                    area,
                    "gravity_loads",
                    AreaGravityLoad(
                        pattern_name=str(load_pat[i]),
                        multiplier_x=_safe_float(wx[i]),
                        multiplier_y=_safe_float(wy[i]),
                        multiplier_z=_safe_float(wz[i]),
                    ),
                )

    except Exception:
        logger.debug(
            "No area gravity loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Uniform
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            c_sys,
            dir_,
            value,
            ret,
        ) = model.AreaObj.GetLoadUniform(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                c_sys,
                dir_,
                value,
            )

            for i in range(n):
                direction = _direction(dir_[i])

                if direction is None:
                    direction = str(dir_[i])

                load = AreaUniformLoad(
                    pattern_name=str(load_pat[i]),
                    direction=direction,
                    value=_safe_float(value[i]),
                )

                _set_if(
                    load,
                    "coordinate_system",
                    str(c_sys[i]),
                )

                _append(
                    area,
                    "uniform_loads",
                    load,
                )

    except Exception:
        logger.debug(
            "No area uniform loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Uniform to frame
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            c_sys,
            dir_,
            value,
            dist_type,
            ret,
        ) = model.AreaObj.GetLoadUniformToFrame(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                c_sys,
                dir_,
                value,
                dist_type,
            )

            for i in range(n):
                direction = _direction(dir_[i])

                if direction is None:
                    direction = str(dir_[i])

                load = AreaUniformToFrameLoad(
                    pattern_name=str(load_pat[i]),
                    direction=direction,
                    value=_safe_float(value[i]),
                    dist_type=str(dist_type[i]),
                )

                _set_if(
                    load,
                    "coordinate_system",
                    str(c_sys[i]),
                )

                # SAP integer değerini ayrıca kaybetme.
                _set_if(
                    load,
                    "sap_dist_type",
                    _safe_int(dist_type[i]),
                )

                _append(
                    area,
                    "uniform_to_frame_loads",
                    load,
                )

    except Exception:
        logger.debug(
            "No area uniform-to-frame loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Wind pressure
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            my_type,
            cp,
            windward,
            dist_type,
            ret,
        ) = model.AreaObj.GetLoadWindPressure(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                my_type,
                cp,
                windward,
                dist_type,
            )

            for i in range(n):
                load = AreaWindPressureLoad(
                    pattern_name=str(load_pat[i]),
                    cp=_safe_float(cp[i]),
                    windward=bool(windward[i]),
                    dist_type=str(dist_type[i]),
                )

                _set_if(
                    load,
                    "sap_my_type",
                    _safe_int(my_type[i]),
                )

                _set_if(
                    load,
                    "sap_distribution_type",
                    _safe_int(dist_type[i]),
                )

                _append(
                    area,
                    "wind_pressure_loads",
                    load,
                )

    except Exception:
        logger.debug(
            "No area wind-pressure loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Surface pressure
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            face,
            pressure,
            ret,
        ) = model.AreaObj.GetLoadSurfacePressure(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                face,
                pressure,
            )

            for i in range(n):
                _append(
                    area,
                    "surface_pressure_loads",
                    AreaSurfacePressureLoad(
                        pattern_name=str(load_pat[i]),
                        face=str(face[i]),
                        pressure=_safe_float(
                            pressure[i]
                        ),
                    ),
                )

    except Exception:
        logger.debug(
            "No area surface-pressure loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Temperature
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            temp_type,
            val,
            ret,
        ) = model.AreaObj.GetLoadTemperature(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                temp_type,
                val,
            )

            for i in range(n):
                _append(
                    area,
                    "temperature_loads",
                    AreaTemperatureLoad(
                        pattern_name=str(load_pat[i]),
                        temp_type=str(temp_type[i]),
                        val=_safe_float(val[i]),
                    ),
                )

    except Exception:
        logger.debug(
            "No area temperature loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Strain
    # ----------------------------------------------------------------------

    try:
        (
            load_pat,
            component,
            val,
            ret,
        ) = model.AreaObj.GetLoadStrain(name)

        if _ret_ok(ret):
            n = _item_count(
                load_pat,
                component,
                val,
            )

            for i in range(n):
                _append(
                    area,
                    "strain_loads",
                    AreaStrainLoad(
                        pattern_name=str(load_pat[i]),
                        component=str(component[i]),
                        val=_safe_float(val[i]),
                    ),
                )

    except Exception:
        logger.debug(
            "No area strain loads: %s",
            name,
            exc_info=True,
        )

    # ----------------------------------------------------------------------
    # Reference temperature
    # ----------------------------------------------------------------------

    try:
        value, ret = (
            model.AreaObj.GetLoadRefTemperature(name)
        )

        if _ret_ok(ret):
            _append(
                area,
                "ref_temperature_loads",
                AreaRefTemperatureLoad(
                    temp=_safe_float(value)
                ),
            )

    except Exception:
        logger.debug(
            "No area reference temperature: %s",
            name,
            exc_info=True,
        )


def import_areas(
    sap,
    nodes: dict[str, Node],
    area_sections: dict[str, Any],
) -> dict[str, Area]:
    """SAP AreaObj -> CAD4 Area."""

    areas: dict[str, Area] = {}

    selected = sap.get_selected_objects()

    area_names = [
        item["name"]
        for item in selected
        if item.get("type") == "Area"
    ]

    for name in area_names:
        try:
            # cSap helper:
            # (point_count, point_names, coords)
            point_count, point_names, coords = (
                sap.get_area_points(name)
            )

            if not point_names:
                logger.warning(
                    "Area %s: no points found",
                    name,
                )
                continue

            area_nodes = []

            for point_name in point_names:
                node = nodes.get(point_name)

                if node is None:
                    logger.warning(
                        "Area %s: node not found: %s",
                        name,
                        point_name,
                    )
                    continue

                area_nodes.append(node)

            if len(area_nodes) < 3:
                logger.warning(
                    "Area %s has less than 3 valid nodes",
                    name,
                )
                continue

            # --------------------------------------------------------------
            # Section
            # --------------------------------------------------------------

            prop_name, ret = (
                sap.SapModel.AreaObj.GetProperty(name)
            )

            if not _ret_ok(ret):
                prop_name = ""

            section = area_sections.get(prop_name)

            # --------------------------------------------------------------
            # Area
            # --------------------------------------------------------------

            area = Area(
                nodes=area_nodes,
                thickness=section.thickness if section else 0.0,
                label=name,
            )

            _set_if(
                area,
                "propname",
                prop_name,
            )

            # Koordinatları ayrıca saklamak istersen:
            # geometrik doğrulama/debug için oldukça faydalı.
            _set_if(
                area,
                "coordinates",
                coords,
            )

            _set_if(
                area,
                "point_names",
                tuple(point_names),
            )

            _set_if(
                area,
                "point_count",
                point_count,
            )

            # --------------------------------------------------------------
            # Loads
            # --------------------------------------------------------------

            _import_area_loads(
                sap,
                area,
            )

            # --------------------------------------------------------------
            # Connectivity
            # --------------------------------------------------------------

            for node in area_nodes:
                node.add_connection(area)

            areas[name] = area

        except Exception:
            logger.exception(
                "Area import failed: %s",
                name,
            )

    return areas


# ============================================================================
# LINK
# ============================================================================

def _import_link_loads(
    sap,
    link,
) -> None:
    """
    Link yükleri.

    Link-specific load API'leri kullanılan SAP sürümüne göre değişebildiği
    için burada link geometrisi/property bağlantısı garanti edilir.
    """

    # Link'in mevcut domain sınıfında yük koleksiyonu varsa korunur.
    # İleride LinkObj.GetLoad... API'leri doğrulandığında buraya eklenebilir.
    return


def import_links(
    sap,
    nodes: dict[str, Node],
    link_properties: dict[str, Any],
) -> dict[str, Link]:
    """SAP LinkObj -> CAD4 Link."""

    model = sap.SapModel
    links: dict[str, Link] = {}

    selected = sap.get_selected_objects()

    link_names = [
        item["name"]
        for item in selected
        if item.get("type") == "Link"
    ]

    for name in link_names:
        try:
            point_i, point_j, ret = (
                model.LinkObj.GetPoints(name)
            )

            if not _ret_ok(ret):
                continue

            node_i = nodes.get(point_i)
            node_j = nodes.get(point_j)

            if node_i is None or node_j is None:
                logger.warning(
                    "Link %s: node not found (%s, %s)",
                    name,
                    point_i,
                    point_j,
                )
                continue

            prop_name, ret = (
                model.LinkObj.GetProperty(name)
            )

            if not _ret_ok(ret):
                prop_name = ""

            prop = link_properties.get(prop_name)

            link = Link(
                node_i=node_i,
                node_j=node_j,
                propname=prop_name,
                label=name,
            )

            # Property'yi ayrıca doğrudan bağla.
            _set_if(link, "property", prop)

            _import_link_loads(
                sap,
                link,
            )

            node_i.add_connection(link)
            node_j.add_connection(link)

            links[name] = link

        except Exception:
            logger.exception(
                "Link import failed: %s",
                name,
            )

    return links


# ============================================================================
# ANA IMPORT
# ============================================================================

def import_model(sap) -> dict[str, dict]:
    """
    SAP2000 modelini CAD4 domain nesnelerine dönüştürür.

    Dönüş:
        {
            "materials": ...,
            "sections": ...,
            "area_sections": ...,
            "link_properties": ...,
            "nodes": ...,
            "frames": ...,
            "areas": ...,
            "links": ...,
        }

    Import sırası önemlidir:

        1. Material
        2. Frame Section
        3. Area Section
        4. Link Property
        5. Node
        6. Frame
        7. Area
        8. Link
    """

    logger.info("SAP2000 -> CAD4 import başladı")
    selected = sap.get_selected_objects()
    # Seçili Frame/Area/Link'lerin kullandığı Point'leri de seç
    prepare_point_selection(sap, selected)

    # ----------------------------------------------------------------------
    # Properties
    # ----------------------------------------------------------------------

    materials = get_materials(sap)

    logger.info(
        "Materials: %d",
        len(materials),
    )

    sections = get_all_sections(
        sap,
        materials=materials,
    )

    logger.info(
        "Frame sections: %d",
        len(sections),
    )

    area_sections = get_area_sections(
        sap,
        materials=materials,
    )

    logger.info(
        "Area sections: %d",
        len(area_sections),
    )

    link_properties = get_link_properties(sap)

    logger.info(
        "Link properties: %d",
        len(link_properties),
    )

    # ----------------------------------------------------------------------
    # Geometry
    # ----------------------------------------------------------------------

    nodes = import_nodes(sap)

    logger.info(
        "Nodes: %d",
        len(nodes),
    )

    frames = import_frames(
        sap,
        nodes,
        sections,
    )

    logger.info(
        "Frames: %d",
        len(frames),
    )

    areas = import_areas(
        sap,
        nodes,
        area_sections,
    )

    logger.info(
        "Areas: %d",
        len(areas),
    )

    links = import_links(
        sap,
        nodes,
        link_properties,
    )

    logger.info(
        "Links: %d",
        len(links),
    )

    result = {
        "materials": materials,
        "sections": sections,
        "area_sections": area_sections,
        "link_properties": link_properties,
        "nodes": nodes,
        "frames": frames,
        "areas": areas,
        "links": links,
    }

    logger.info(
        "SAP2000 -> CAD4 import tamamlandı: "
        "%d node, %d frame, %d area, %d link",
        len(nodes),
        len(frames),
        len(areas),
        len(links),
    )

    return result