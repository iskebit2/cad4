#app/commands/analysis/validation.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


class AnalysisValidationError(ValueError):
    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        self.errors = list(errors)
        self.warnings = list(warnings or [])
        super().__init__("\n".join(self.errors))


@dataclass
class AnalysisValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_finite_number(val) -> bool:
    if val is None or isinstance(val, bool):
        return False
    return isinstance(val, (int, float, np.number)) and math.isfinite(float(val))


def _has_support(node) -> bool:
    r = getattr(node, "restraint", None)
    if r is not None:
        if any(bool(getattr(r, d, False)) for d in ("ux", "uy", "uz", "rx", "ry", "rz")):
            return True
    for s in ("spring_u1", "spring_u2", "spring_u3", "spring_r1", "spring_r2", "spring_r3"):
        val = getattr(node, s, 0.0)
        if _is_finite_number(val) and float(val) > 0.0:
            return True
    return False


def validate_model(
    math_model,
    project=None,
    *,
    length_tol: float = 1e-6,
    area_tol: float = 1e-4,
    strict: bool = True,
) -> AnalysisValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if math_model is None:
        errors.append("Analiz modeli (MathModel) tanımlı değil.")
        if strict:
            raise AnalysisValidationError(errors, warnings)
        return AnalysisValidationReport(errors=errors, warnings=warnings)

    nodes = getattr(math_model, "nodes", None) or {}
    frames = getattr(math_model, "frames", None) or {}
    areas = getattr(math_model, "areas", None) or {}
    links = getattr(math_model, "links", None) or {}

    if not nodes:
        errors.append("Modelde hiç düğüm (Node) yok.")
    if not frames and not areas and not links:
        errors.append("Modelde analiz edilecek yapısal eleman (Frame, Area, Link) yok.")

    valid_node_ids: set[int] = set()
    connected_node_ids: set[int] = set()
    support_count = 0

    for key, node in nodes.items():
        uid = getattr(node, "unique_id", key)
        label = getattr(node, "label", "") or f"Node#{uid}"
        coords = (getattr(node, "x", None), getattr(node, "y", None), getattr(node, "z", None))
        if not all(_is_finite_number(c) for c in coords):
            errors.append(f"{label}: geçersiz koordinat ({coords}).")
            continue
        valid_node_ids.add(uid)
        if _has_support(node):
            support_count += 1

    if nodes and support_count == 0:
        errors.append("Modelde mesnetli veya yaylı düğüm yok; sistem rijit cisim hareketine açık.")

    for key, frame in frames.items():
        uid = getattr(frame, "unique_id", key)
        label = getattr(frame, "label", "") or f"Frame#{uid}"
        ni = getattr(frame, "node_i", None)
        nj = getattr(frame, "node_j", None)

        if ni is None or nj is None:
            errors.append(f"{label}: uç düğümlerden biri eksik (node_i={ni}, node_j={nj}).")
            continue

        ni_id = getattr(ni, "unique_id", None)
        nj_id = getattr(nj, "unique_id", None)
        if ni_id not in valid_node_ids or nj_id not in valid_node_ids:
            errors.append(f"{label}: bağlı düğümler MathModel.nodes içinde kayıtlı değil.")
            continue

        if ni_id == nj_id:
            errors.append(f"{label}: başlangıç ve bitiş düğümü aynı ({ni_id}).")
            continue

        connected_node_ids.add(ni_id)
        connected_node_ids.add(nj_id)

        length = float(frame.get_length()) if hasattr(frame, "get_length") else math.dist(
            (ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z)
        )
        if not _is_finite_number(length) or length <= length_tol:
            errors.append(f"{label}: sıfır veya geçersiz uzunluk (L={length}).")

        sec = getattr(frame, "section", None)
        if sec is None:
            errors.append(f"{label}: kesit (section) atanmamış.")
            continue

        mat = getattr(sec, "material", None)
        if mat is None:
            errors.append(f"{label}: kesit malzemesi (material) atanmamış.")
        else:
            e1 = getattr(mat, "E1", None)
            g12 = getattr(mat, "G12", None)
            rho = getattr(mat, "density", 0.0)
            if not _is_finite_number(e1) or float(e1) <= 0.0:
                errors.append(f"{label}: geçersiz elastisite modülü E1={e1}.")
            if not _is_finite_number(g12) or float(g12) <= 0.0:
                errors.append(f"{label}: geçersiz kayma modülü G12={g12}.")
            if not _is_finite_number(rho) or float(rho) < 0.0:
                errors.append(f"{label}: negatif/geçersiz yoğunluk density={rho}.")
            elif float(rho) == 0.0:
                warnings.append(f"{label}: malzeme yoğunluğu 0; öz ağırlık kütleye katılmayacak.")

        params = getattr(sec, "profile_params", None) or {}
        for req_param in ("Area", "I33", "I22"):
            pval = params.get(req_param, None)
            if not _is_finite_number(pval) or float(pval) <= 0.0:
                errors.append(f"{label}: geçersiz kesit parametresi {req_param}={pval}.")

        j_val = params.get("J", 0.0)
        if not _is_finite_number(j_val) or float(j_val) < 0.0:
            errors.append(f"{label}: negatif/geçersiz burulma sabiti J={j_val}.")

        if getattr(frame, "auto_mesh", False):
            n_seg = getattr(frame, "mesh_num_segments", 0)
            max_len = getattr(frame, "mesh_max_length", 0.0)
            if (not _is_finite_number(n_seg) or int(n_seg) < 1) and (
                not _is_finite_number(max_len) or float(max_len) <= 0.0
            ):
                errors.append(f"{label}: auto_mesh aktif ancak geçerli bölme sayısı veya maksimum uzunluk tanımlı değil.")

    for key, area in areas.items():
        uid = getattr(area, "unique_id", key)
        label = getattr(area, "label", "") or f"Area#{uid}"
        area_nodes = getattr(area, "nodes", None) or []

        if len(area_nodes) < 3:
            errors.append(f"{label}: köşe düğüm sayısı 3'ten az ({len(area_nodes)}).")
            continue

        node_ids = [getattr(nd, "unique_id", None) for nd in area_nodes]
        if any(nid not in valid_node_ids for nid in node_ids):
            errors.append(f"{label}: köşe düğümlerinden biri MathModel.nodes içinde kayıtlı değil.")
            continue

        if len(set(node_ids)) < 3:
            errors.append(f"{label}: tekrarlayan köşe düğümleri nedeniyle dejenere alan.")
            continue

        for nid in node_ids:
            connected_node_ids.add(nid)

        pts = np.array([[nd.x, nd.y, nd.z] for nd in area_nodes], dtype=float)
        normal = np.zeros(3, dtype=float)
        for i in range(len(pts)):
            p1, p2 = pts[i], pts[(i + 1) % len(pts)]
            normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
            normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
            normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
        geom_area = float(np.linalg.norm(normal) * 0.5)
        if not _is_finite_number(geom_area) or geom_area <= area_tol:
            errors.append(f"{label}: sıfır veya dejenere yüzey alanı (A={geom_area}).")

        thickness = getattr(area, "thickness", 0.0)
        if not _is_finite_number(thickness) or float(thickness) <= 0.0:
            errors.append(f"{label}: geçersiz kabuk kalınlığı thickness={thickness}.")

        area_sec = getattr(area, "area_section", None)
        mat = getattr(area, "material", None) or (getattr(area_sec, "material", None) if area_sec else None)
        if mat is None:
            errors.append(f"{label}: malzeme (material) atanmamış.")
        else:
            e1 = getattr(mat, "E1", None)
            nu12 = getattr(mat, "nu12", 0.3)
            if not _is_finite_number(e1) or float(e1) <= 0.0:
                errors.append(f"{label}: geçersiz elastisite modülü E1={e1}.")
            if not _is_finite_number(nu12) or not (-0.99 < float(nu12) < 0.5):
                errors.append(f"{label}: geçersiz Poisson oranı nu12={nu12}.")

    link_props = getattr(project, "link_props", None) or {} if project is not None else {}
    for key, link in links.items():
        uid = getattr(link, "unique_id", key)
        label = getattr(link, "label", "") or f"Link#{uid}"
        ni = getattr(link, "node_i", None)
        nj = getattr(link, "node_j", None)

        if ni is None or nj is None:
            errors.append(f"{label}: uç düğümlerden biri eksik.")
            continue

        ni_id = getattr(ni, "unique_id", None)
        nj_id = getattr(nj, "unique_id", None)
        if ni_id not in valid_node_ids or nj_id not in valid_node_ids:
            errors.append(f"{label}: bağlı düğümler MathModel.nodes içinde kayıtlı değil.")
            continue

        connected_node_ids.add(ni_id)
        connected_node_ids.add(nj_id)

        propname = getattr(link, "propname", "")
        if not propname:
            errors.append(f"{label}: Link propname tanımlı değil.")
        elif link_props and propname not in link_props:
            errors.append(f"{label}: '{propname}' isimli LinkProp projede bulunamadı.")

    orphan_ids = valid_node_ids - connected_node_ids
    if orphan_ids:
        warnings.append(f"Modelde hiçbir elemana bağlı olmayan {len(orphan_ids)} boşta düğüm var.")

    if project is not None:
        patterns = getattr(project, "load_patterns", None) or {}
        if not patterns:
            warnings.append("Projede tanımlı LoadPattern bulunamadı.")

    report = AnalysisValidationReport(errors=errors, warnings=warnings)
    if strict and not report.ok:
        raise AnalysisValidationError(errors, warnings)
    return report


def validate_mass(asm, is_consistent: bool = True) -> list[str]:
    errors: list[str] = []
    M = asm.M_global

    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        errors.append(f"M_global kare değil: {M.shape}")
        return errors

    if not np.all(np.isfinite(M)):
        errors.append("M_global içinde NaN veya Inf değeri var.")
        return errors

    if not np.allclose(M, M.T, atol=1e-9):
        errors.append("M_global simetrik değil.")

    diag = np.diag(M)
    if np.any(diag < -1e-12):
        errors.append(f"M_global köşegeninde negatif kütle var (min={diag.min():.3e}).")

    if asm.total_kg <= 0.0:
        errors.append("Toplam yapı kütlesi sıfır veya negatif.")

    node_sum_kg = sum(asm.node_masses.values())
    if node_sum_kg > 0.0:
        for axis, label in ((0, "X"), (1, "Y"), (2, "Z")):
            r = np.zeros(asm.num_dofs, dtype=float)
            r[axis::6] = 1.0
            eff_kg = float(r @ M @ r) * 1000.0
            if abs(eff_kg - node_sum_kg) / node_sum_kg > 1e-3:
                errors.append(
                    f"Toplam yapısal kütle ({label} yönü: {eff_kg:.2f} kg) ile düğüm kütleleri ({node_sum_kg:.2f} kg) tutarsız."
                )

    return errors


def validate_stiffness(asm) -> list[str]:
    errors: list[str] = []
    K = asm.K_global

    if K.ndim != 2 or K.shape[0] != K.shape[1]:
        errors.append(f"K_global kare değil: {K.shape}")
        return errors

    if not np.all(np.isfinite(K)):
        errors.append("K_global içinde NaN veya Inf değeri var.")
        return errors

    if not np.allclose(K, K.T, atol=1e-6):
        errors.append("K_global simetrik değil.")

    diag = np.diag(K)
    if np.any(diag < -1e-9):
        errors.append(f"K_global köşegeninde negatif rijitlik var (min={diag.min():.3e}).")

    if asm.frame_count + asm.area_count + getattr(asm, "link_count", 0) == 0:
        errors.append("K_global içine hiçbir eleman monte edilemedi.")

    for label, reason in asm.skipped:
        errors.append(f"Atlanan eleman ({label}): {reason}")

    return errors