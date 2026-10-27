from math import isclose
import numpy as np

from structload.data.wind_data import TOL, WindRelation

def get_neighbors(surf, all_surfaces):
    neighbors = {}

    for edge in surf.edges.values():
        for shrd in edge.shared:
            if shrd["is_coplanar_shared"]:
                continue

            name = shrd["surface"]
            neighbors[name] = all_surfaces[name]

    return list(neighbors.values())


def has_global_leading_neighbor(surf, neighbors):
    for n in neighbors:
        if n.global_leading and n.wind_relation == surf.wind_relation:
            return True

    return False

def classify_surface(surf, all_surfaces):

    neighbors = get_neighbors(surf, all_surfaces)
    relations = {n.wind_relation for n in neighbors}

    if surf.wind_relation == WindRelation.WINDWARD:

        if WindRelation.PARALLEL in relations:
            return "HIPPED"

        if relations and relations <= {WindRelation.LEEWARD}:
            return "DUOPITCH"

        return "MONOPITCH"

    if surf.wind_relation == WindRelation.LEEWARD:

        if WindRelation.PARALLEL in relations:
            return "HIPPED"

        if relations and relations <= {WindRelation.WINDWARD}:
            return "DUOPITCH"

        return "MONOPITCH"

    if surf.wind_relation == WindRelation.PARALLEL:

        if not neighbors:
            return "MONOPITCH"

        if all(np.isclose(n.angle, surf.angle, atol=1e-6)
               for n in neighbors):
            return "MONOPITCH"

        if has_global_leading_neighbor(surf, neighbors):
            return "DUOPITCH"

        return "HIPPED"

    return None

def _analysis_classify_all_surface(surfaces_items):

    for surface in surfaces_items.values():
    
        if surface.surface_type.value != "ROOF":
            continue

        surface.roof_type = classify_surface(surface, surfaces_items)
        

def _analysis_global_edges(surfaces_items):

    global_leading = []

    for surface in surfaces_items.values():

        if surface.surface_type.value != "ROOF":
            continue

        # Her rüzgar analizinde sıfırla
        surface.global_leading = False

        for edge in surface.edges.values():

            edge._global = False

            if not edge.leading:
                continue

            # Shared değilse global
            if not edge.shared:
                edge._global = True
                surface.global_leading = True
                global_leading.append(edge)
                continue

            # Shared ise karşı edge'leri kontrol et
            # DÜZELTME
            is_global = True
            for shared in edge.shared:
                if shared.get("same_edge", False):
                    is_global = False
                    break

            if is_global:
                edge._global = True
                surface.global_leading = True
                global_leading.append(edge)

    return global_leading


def _are_edges_overlapping(e1, e2, tol: float = 1e-4) -> bool:
    p1a, p1b = np.array(e1.p1), np.array(e1.p2)
    p2a, p2b = np.array(e2.p1), np.array(e2.p2)
    same_dir = (np.linalg.norm(p1a - p2a) < tol and np.linalg.norm(p1b - p2b) < tol)
    opp_dir = (np.linalg.norm(p1a - p2b) < tol and np.linalg.norm(p1b - p2a) < tol)
    return same_dir or opp_dir

def _analyze_shared_edges(surfaces_items, w_dir, tol=1e-3) -> None:

    surfaces = list(surfaces_items.values())
    plane_data = []
    for surface in surfaces:
        if surface.surface_type.value != "ROOF":
            continue
        normal = surface.normal_unit
        if normal is None or not surface.edges:
            continue
        first_edge = next(iter(surface.edges.values()), None)
        if first_edge is None:
            continue
        d_const = -float(np.dot(normal, first_edge.p1))
        plane_data.append({
            "surface": surface,
            "normal": normal,
            "d": d_const,
        })

    n = len(plane_data)
    for i in range(n):
        surf_i = plane_data[i][
            "surface"
        ]
        ni = plane_data[i][
            "normal"
        ]
        di = plane_data[i][
            "d"
        ]

        for j in range(i + 1, n):
            surf_j = plane_data[j][
                "surface"
            ]
            nj = plane_data[j][
                "normal"
            ]
            dj = plane_data[j][
                "d"
            ]

            normal_dot = abs(float(np.dot(ni, nj)))
            is_coplanar = (
                abs(normal_dot - 1.0) < TOL
                and abs(abs(di) - abs(dj)) < TOL
            )


            for ei in surf_i.edges.values():
                for ej in surf_j.edges.values():
                    if not _are_edges_overlapping(ei, ej, TOL):
                        continue

                    entry_i = {
                        "surface": surf_j.name,
                        "surface_edge": ej.index,
                        "same_edge": True,
                        "is_coplanar_shared": is_coplanar,
                    }
                    entry_j = {
                        "surface": surf_i.name,
                        "surface_edge": ei.index,
                        "same_edge": True,
                        "is_coplanar_shared": is_coplanar,
                    }

                    ei.shared.append(entry_i)
                    ej.shared.append(entry_j)
                    ei.is_coplanar_shared = is_coplanar
                    ej.is_coplanar_shared = is_coplanar

    roof_surfaces = [s for s in surfaces_items.values() if s.surface_type.value == "ROOF"]

    # Öncelikle her yüzey için global_leading bayrağını set edelim
    for surface in roof_surfaces:
        surface.global_leading = any(getattr(edge, "_global", False) for edge in surface.edges.values())

    for surface in roof_surfaces:
        surface.any_shared = any(getattr(edge, "is_shared", False) for edge in surface.edges.values())

        # Listeleri güncelle
        surface.exposed_edge_list = [k for k, ed in surface.edges.items() if ed.exposed]
        surface.leading_edge_list = [k for k, ed in surface.edges.items() if ed.leading]