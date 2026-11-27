# app/analysis/validation.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from scipy import sparse

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class AnalysisValidationError(Exception):

    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        self.errors = list(errors)
        self.warnings = list(warnings or [])
        n = len(self.errors)
        first = self.errors[0] if self.errors else "(bilinmiyor)"
        super().__init__(f"{n} doğrulama hatası: {first}")


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def merge(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


_EPS = 1e-9


def _label(obj, fallback: str = "?") -> str:
    lab = getattr(obj, "label", None)
    if lab:
        return str(lab)
    uid = getattr(obj, "unique_id", None)
    return f"{fallback}#{uid}" if uid is not None else fallback


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(v)) for v in values)


def _get_param(obj, name: str, default=0.0) -> float:
    val = getattr(obj, name, default)
    if val is None or isinstance(val, bool):
        return float(default)
    return float(val)


def _resolve_frame_mesh_plan(frame) -> tuple[int, str, bool]:
    L = 0.0
    if callable(getattr(frame, "get_length", None)):
        L = float(frame.get_length() or 0.0)

    auto = bool(getattr(frame, "auto_mesh", False))
    n_seg = int(_get_param(frame, "mesh_num_segments", 0))
    max_len = _get_param(frame, "mesh_max_length", 0.0)

    if auto and n_seg >= 2:
        return n_seg, "mesh_num_segments", False
    if auto and max_len > 0.0 and L > 0.0:
        return max(1, math.ceil(L / max_len)), "mesh_max_length", False

    sta_type = str(getattr(frame, "station_type", "MinNumSta") or "MinNumSta")
    max_spcg = _get_param(frame, "max_sta_spcg", 0.0)
    min_sta = int(_get_param(frame, "min_num_sta", 0))

    if sta_type == "MaxStaSpcg" and max_spcg > 0.0 and L > 0.0:
        return max(1, math.ceil(L / max_spcg)), "max_sta_spcg", auto
    if min_sta >= 2:
        return max(1, min_sta - 1), "min_num_sta", auto

    return 1, "single", auto


def _matrix_is_empty(mat) -> bool:
    if mat is None:
        return True
    if sparse.issparse(mat):
        return mat.shape[0] == 0 or mat.shape[1] == 0
    arr = np.asarray(mat)
    return arr.size == 0


def _matrix_all_finite(mat) -> tuple[bool, int]:
    if sparse.issparse(mat):
        data = mat.data
        if data.size == 0:
            return True, 0
        mask = ~np.isfinite(data)
        return not np.any(mask), int(mask.sum())
    arr = np.asarray(mat)
    mask = ~np.isfinite(arr)
    return not np.any(mask), int(mask.sum())


def _matrix_max_asymmetry(mat) -> float:
    if sparse.issparse(mat):
        diff = (mat - mat.T).tocsr()
        if diff.nnz == 0:
            return 0.0
        return float(np.abs(diff.data).max())
    arr = np.asarray(mat, dtype=float)
    return float(np.max(np.abs(arr - arr.T)))


def _matrix_is_all_zero(mat, atol: float = 1e-12) -> bool:
    if sparse.issparse(mat):
        if mat.nnz == 0:
            return True
        return bool(np.all(np.abs(mat.data) <= atol))
    arr = np.asarray(mat, dtype=float)
    return bool(np.allclose(arr, 0.0, atol=atol))


def _matrix_diagonal(mat) -> np.ndarray:
    if sparse.issparse(mat):
        return np.asarray(mat.diagonal(), dtype=float)
    return np.diag(np.asarray(mat, dtype=float))


class _ModelChecker:

    def __init__(self, model, project):
        self.model = model
        self.project = project
        self.report = ValidationReport()
        self._materials = dict(getattr(project, "materials", {}) or {})
        self._sections = dict(getattr(project, "sections", {}) or {})
        self._area_sections = dict(getattr(project, "area_sections", {}) or {})
        self._link_props = dict(getattr(project, "link_props", {}) or {})
        self._load_patterns = dict(getattr(project, "load_patterns", {}) or {})
        self._load_cases = dict(getattr(project, "load_cases", {}) or {})

    def run(self) -> ValidationReport:
        self._check_units()
        self._check_materials()
        self._check_frames()
        self._check_areas()
        self._check_links()
        self._check_nodes()
        self._check_loads()
        self._check_restraints()
        self._check_duplicates()
        return self.report

    def _check_units(self) -> None:
        units = getattr(self.project, "units", None)
        if units is None:
            self.report.add_warning(
                "Proje birim sistemi tanımsız; varsayılan N-mm kullanılacak."
            )

    def _check_materials(self) -> None:
        if not self._materials:
            self.report.add_error(
                "Hiç malzeme tanımlı değil. En az bir Material gerekli."
            )
            return

        for name, mat in self._materials.items():
            E = _get_param(mat, "E1", 0.0)
            rho = _get_param(mat, "density", 0.0)
            nu = _get_param(mat, "nu12", 0.0)

            if E <= 0.0:
                self.report.add_error(
                    f"Malzeme '{name}': E1={E} (pozitif olmalı)."
                )
            if not _finite(E, rho, nu):
                self.report.add_error(
                    f"Malzeme '{name}': E/ρ/ν sonlu değil."
                )
            if abs(nu) >= 0.5:
                self.report.add_warning(
                    f"Malzeme '{name}': ν={nu:.3f} fiziksel aralık dışında (|ν|<0.5)."
                )
            if rho <= 0.0:
                self.report.add_warning(
                    f"Malzeme '{name}': density={rho}; öz kütle hesaplanamayacak."
                )

    def _check_frames(self) -> None:
        frames = getattr(self.model, "frames", {}) or {}
        for frame in frames.values():
            self._check_frame(frame)

    def _check_frame(self, frame) -> None:
        label = _label(frame, "Frame")

        ni = getattr(frame, "node_i", None)
        nj = getattr(frame, "node_j", None)
        if ni is None or nj is None:
            self.report.add_error(f"{label}: node_i / node_j eksik.")
            return
        if ni is nj or getattr(ni, "unique_id", None) == getattr(nj, "unique_id", None):
            self.report.add_error(f"{label}: başlangıç ve bitiş düğümü aynı.")
            return

        L = float(frame.get_length() or 0.0) if hasattr(frame, "get_length") else 0.0
        if L <= _EPS:
            self.report.add_error(f"{label}: uzunluk sıfır ({L}).")
            return

        sec = getattr(frame, "section", None)
        if sec is None:
            self.report.add_error(f"{label}: kesit atanmamış.")
            return
        if sec not in self._sections.values() and getattr(sec, "name", None) not in self._sections:
            self.report.add_warning(
                f"{label}: kesit '{getattr(sec, 'name', '?')}' proje kayıtlarında yok."
            )
        params = getattr(sec, "profile_params", {}) or {}
        A = _get_param_from_dict(params, "Area")
        if A <= 0.0:
            self.report.add_error(f"{label}: kesit alanı (Area) tanımsız veya ≤0.")
        I33 = _get_param_from_dict(params, "I33")
        I22 = _get_param_from_dict(params, "I22")
        if I33 <= 0.0 and I22 <= 0.0:
            self.report.add_error(f"{label}: atalet momentleri (I22/I33) ≤0.")

        mat = getattr(sec, "material", None)
        if mat is None:
            self.report.add_error(f"{label}: kesite malzeme atanmamış.")
        elif _get_param(mat, "E1", 0.0) <= 0.0:
            self.report.add_error(f"{label}: malzeme E1 ≤0.")

        r_i = getattr(frame, "release_i", None)
        r_j = getattr(frame, "release_j", None)
        if _all_released(r_i) and _all_released(r_j):
            self.report.add_warning(
                f"{label}: her iki uçta tüm serbestlikler açık; eleman mekanizmada."
            )

        self._check_frame_mesh(frame, label)

    def _check_frame_mesh(self, frame, label: str) -> None:
        L = float(frame.get_length() or 0.0) if hasattr(frame, "get_length") else 0.0
        auto = bool(getattr(frame, "auto_mesh", False))
        n_seg, source, fallback = _resolve_frame_mesh_plan(frame)

        if n_seg <= 0:
            self.report.add_error(
                f"{label}: mesh planı geçersiz (n_segments={n_seg})."
            )
            return

        max_len = _get_param(frame, "mesh_max_length", 0.0)
        if auto and max_len > 0.0 and L > 0.0:
            min_seg = math.ceil(L / max_len)
            if min_seg > 200:
                self.report.add_warning(
                    f"{label}: mesh_max_length={max_len:.0f} → {min_seg} segment; "
                    f"çok ince mesh (performans riski)."
                )

        if auto and fallback:
            self.report.add_warning(
                f"{label}: auto_mesh açık fakat mesh_num_segments/mesh_max_length "
                f"tanımsız; '{source}' fallback kullanılacak (n_segments={n_seg})."
            )

    def _check_areas(self) -> None:
        for area in (getattr(self.model, "areas", {}) or {}).values():
            self._check_area(area)

    def _check_area(self, area) -> None:
        label = _label(area, "Area")
        nodes = list(getattr(area, "nodes", []) or [])
        if len(nodes) < 3:
            self.report.add_error(
                f"{label}: en az 3 düğüm gerekli, {len(nodes)} var."
            )
            return

        is_lt = _is_load_transfer(area)
        mat = getattr(area, "material", None)
        if mat is None:
            sec = getattr(area, "area_section", None)
            mat = getattr(sec, "material", None) if sec else None

        if not is_lt:
            if mat is None:
                self.report.add_error(f"{label}: malzeme atanmamış.")
            elif _get_param(mat, "E1", 0.0) <= 0.0:
                self.report.add_error(f"{label}: malzeme E1 ≤0.")

        th = _get_param(area, "thickness", 0.0)
        if th <= _EPS:
            if is_lt:
                self.report.add_warning(
                    f"{label}: kalınlık ≈0 → 'load transfer' alanı olarak "
                    f"yorumlanacak (K/M'ye katkısı yok)."
                )
            else:
                self.report.add_error(f"{label}: kalınlık ≤0 ({th}).")

        pts = [(n.x, n.y, n.z) for n in nodes]
        area_val = _polygon_area(pts)
        if area_val <= 1e-6 * max(1.0, th):
            self.report.add_error(
                f"{label}: poligon alanı ≈0 ({area_val:.3e}); geometri dejenere."
            )
        if _has_duplicate_points(pts):
            self.report.add_error(f"{label}: aynı koordinatta iki düğüm var.")

    def _check_links(self) -> None:
        for link in (getattr(self.model, "links", {}) or {}).values():
            label = _label(link, "Link")
            ni = getattr(link, "node_i", None)
            nj = getattr(link, "node_j", None)
            if ni is None or nj is None:
                self.report.add_error(f"{label}: düğümler eksik.")
                continue
            if getattr(ni, "unique_id", None) == getattr(nj, "unique_id", None):
                self.report.add_error(f"{label}: aynı düğüme bağlı.")
                continue
            L = math.dist(
                (ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z)
            )
            if L <= _EPS:
                self.report.add_error(f"{label}: uzunluk sıfır.")
                continue

            prop_name = getattr(link, "propname", "")
            if prop_name and prop_name not in self._link_props:
                self.report.add_error(
                    f"{label}: link özelliği '{prop_name}' proje kayıtlarında yok."
                )

    def _check_nodes(self) -> None:
        for node in (getattr(self.model, "nodes", {}) or {}).values():
            label = _label(node, "Node")
            x, y, z = _get_param(node, "x"), _get_param(node, "y"), _get_param(node, "z")
            if not _finite(x, y, z):
                self.report.add_error(
                    f"{label}: koordinatlar sonlu değil ({x},{y},{z})."
                )

            r = getattr(node, "restraint", None)
            if r is not None:
                for dof_name in ("ux", "uy", "uz", "rx", "ry", "rz"):
                    val = getattr(r, dof_name, False)
                    if not isinstance(val, bool):
                        self.report.add_warning(
                            f"{label}: restraint.{dof_name} bool değil ({val!r})."
                        )

            for sname in ("spring_u1", "spring_u2", "spring_u3",
                          "spring_r1", "spring_r2", "spring_r3"):
                v = _get_param(node, sname, 0.0)
                if v < 0.0:
                    self.report.add_warning(
                        f"{label}: {sname}={v} negatif (yorum belirsiz)."
                    )

    def _check_loads(self) -> None:
        if not self._load_patterns:
            self.report.add_warning("Hiç yük pattern'ı tanımlı değil.")

        if not self._load_cases:
            self.report.add_warning("Hiç yük kombinasyonu tanımlı değil.")

        for cname, lc in self._load_cases.items():
            for item in getattr(lc, "static_assignments", []) or []:
                lname = str(getattr(item, "load_name", "")).strip()
                ltype = str(getattr(item, "load_type", "")).strip().lower()
                if ltype in ("load pattern", "pattern", "load"):
                    if lname not in self._load_patterns:
                        self.report.add_error(
                            f"LoadCase '{cname}': pattern '{lname}' tanımlı değil."
                        )

        bad = 0
        for node in (getattr(self.model, "nodes", {}) or {}).values():
            for pl in getattr(node, "loads", []) or []:
                pat = str(getattr(pl, "pattern_name", "")).strip()
                if pat and pat not in self._load_patterns:
                    bad += 1
                    if bad <= 5:
                        self.report.add_warning(
                            f"Düğüm yükü: pattern '{pat}' tanımsız "
                            f"(düğüm {getattr(node, 'label', '?')})."
                        )
        if bad > 5:
            self.report.add_warning(
                f"... ve {bad - 5} düğüm yükü daha tanımsız pattern'e bağlı."
            )

    def _check_restraints(self) -> None:
        nodes = list((getattr(self.model, "nodes", {}) or {}).values())
        if not nodes:
            self.report.add_error("Hiç düğüm yok.")
            return

        n_fixed = sum(
            1 for n in nodes
            if getattr(n, "restraint", None) is not None
            and not _is_restraint_free(n.restraint)
        )
        if n_fixed == 0:
            self.report.add_error(
                "Hiç mesnetli (restrained) düğüm yok; sistem tekil."
            )
        elif n_fixed < 3:
            self.report.add_warning(
                f"Yalnızca {n_fixed} mesnetli düğüm; stabilite şüpheli."
            )

    def _check_duplicates(self) -> None:
        nodes = list((getattr(self.model, "nodes", {}) or {}).values())
        tol = 1e-4
        seen: dict[tuple[int, int, int], str] = {}
        dups = 0
        for n in nodes:
            key = (round(n.x / tol), round(n.y / tol), round(n.z / tol))
            lab = str(getattr(n, "label", ""))
            if key in seen:
                dups += 1
                if dups <= 5:
                    self.report.add_warning(
                        f"Aynı koordinatta iki düğüm: '{seen[key]}' ve '{lab}'."
                    )
            else:
                seen[key] = lab
        if dups > 5:
            self.report.add_warning(f"... ve {dups - 5} çakışan düğüm daha.")


def _is_load_transfer(area) -> bool:
    behavior = getattr(area, "behavior", None)
    if behavior is not None and str(getattr(behavior, "value", behavior)).lower() == "loadtransfer":
        return True
    th = float(getattr(area, "thickness", 0.0) or 0.0)
    return th <= 1e-9


def _get_param_from_dict(d: dict, key: str, default: float = 0.0) -> float:
    val = d.get(key, default)
    if val is None or isinstance(val, bool):
        return float(default)
    return float(val)


def _all_released(rel) -> bool:
    if rel is None:
        return False
    for dof in ("u1", "u2", "u3", "r1", "r2", "r3"):
        if not getattr(rel, dof, False):
            return False
    return True


def _is_restraint_free(restraint) -> bool:
    if restraint is None:
        return True
    for dof in ("ux", "uy", "uz", "rx", "ry", "rz"):
        if getattr(restraint, dof, False):
            return False
    return True


def _polygon_area(points: list[tuple[float, float, float]]) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    nx = ny = nz = 0.0
    for i in range(n):
        x1, y1, z1 = points[i]
        x2, y2, z2 = points[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def _has_duplicate_points(points: Iterable[tuple[float, float, float]],
                          tol: float = 1e-6) -> bool:
    pts = list(points)
    seen: set[tuple[int, int, int]] = set()
    for p in pts:
        key = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        if key in seen:
            return True
        seen.add(key)
    return False


def validate_model(model, project, strict: bool = True) -> ValidationReport:
    if model is None:
        raise AnalysisValidationError(
            ["Model (math_model) None; analiz başlatılamaz."], []
        )

    checker = _ModelChecker(model, project)
    report = checker.run()

    if report.warnings:
        for w in report.warnings:
            logger.info("[Validation/WARN] %s", w)

    if strict and report.errors:
        for e in report.errors:
            logger.error("[Validation/ERR] %s", e)
        raise AnalysisValidationError(report.errors, report.warnings)

    if not strict:
        for e in report.errors:
            logger.warning("[Validation/ERR, strict=False] %s", e)

    return report


def validate_mass(mass_assembly, is_consistent: bool = True) -> list[str]:
    warns: list[str] = []
    if mass_assembly is None:
        return ["Kütle montajı None."]

    total_kg = getattr(mass_assembly, "total_kg", 0.0)
    if total_kg <= 0.0:
        warns.append(
            "Toplam kütle 0; modal analiz sıfır özdeğer üretebilir."
        )

    M = getattr(mass_assembly, "M_global", None)
    if not _matrix_is_empty(M):
        if M.shape[0] != M.shape[1]:
            warns.append(f"M_global kare değil: {M.shape}.")
            return warns

        finite_ok, _ = _matrix_all_finite(M)
        if not finite_ok:
            warns.append("M_global içinde NaN veya Inf değeri var.")
            return warns

        if is_consistent:
            asym = _matrix_max_asymmetry(M)
            if asym > 1e-9:
                warns.append(f"M_global simetrik değil (max asimetri {asym:.3e}).")

        diag = _matrix_diagonal(M)
        if np.any(diag < -1e-12):
            warns.append(
                "M_global köşegeninde negatif değer(ler) var."
            )

        if _matrix_is_all_zero(M, atol=1e-12):
            warns.append("M_global tamamen sıfır.")

        node_sum_kg = sum(getattr(mass_assembly, "node_masses", {}).values())
        if node_sum_kg > 0.0:
            M_csc = M.tocsc() if sparse.issparse(M) else sparse.csc_matrix(np.asarray(M, dtype=float))
            for axis, label in ((0, "X"), (1, "Y"), (2, "Z")):
                r = np.zeros(M_csc.shape[0], dtype=float)
                r[axis::6] = 1.0
                eff_kg = float(r @ (M_csc @ r)) * 1000.0
                if abs(eff_kg - node_sum_kg) / node_sum_kg > 1e-3:
                    warns.append(
                        f"Toplam yapısal kütle ({label} yönü: {eff_kg:.2f} kg) ile düğüm kütleleri ({node_sum_kg:.2f} kg) tutarsız."
                    )

    contribs = getattr(mass_assembly, "contributions", []) or []
    if not contribs:
        warns.append("Kütle katkısı kaydı boş (mass_assembly.contributions).")
    else:
        bad = [
            c for c in contribs
            if not math.isfinite(getattr(c, "mass_kg", 0.0))
            or getattr(c, "mass_kg", 0.0) < 0.0
        ]
        if bad:
            warns.append(
                f"{len(bad)} kütle katkısı negatif veya NaN."
            )

    return warns


def validate_stiffness(
    stiffness_assembly,
    fixed_dofs=None,
    *,
    check_rank: bool = True,
    rank_tol: float = 1e-9,
) -> list[str]:
    warns: list[str] = []
    if stiffness_assembly is None:
        return ["StiffnessAssembly None; rijitlik montajı yapılmamış."]

    K = getattr(stiffness_assembly, "K_global", None)
    if _matrix_is_empty(K):
        return ["K_global boş veya None."]

    n_dof = K.shape[0]
    if K.shape[0] != K.shape[1]:
        warns.append(f"K_global kare değil: {K.shape}.")
        return warns

    finite_ok, n_bad = _matrix_all_finite(K)
    if not finite_ok:
        warns.append(f"K_global'de {n_bad} adet NaN/Inf eleman var.")

    asym = _matrix_max_asymmetry(K)
    if asym > 1e-6:
        warns.append(f"K_global simetrik değil (max asimetri {asym:.3e}).")

    diag = _matrix_diagonal(K)
    if np.any(diag < -1e-9):
        n_neg = int((diag < -1e-9).sum())
        warns.append(
            f"K_global köşegeninde {n_neg} negatif değer var "
            f"(min {float(diag.min()):.3e})."
        )
    if np.all(np.abs(diag) <= 1e-12):
        warns.append("K_global köşegeni tamamen sıfır.")

    pos_diag = diag[diag > 0]
    if pos_diag.size > 0:
        ratio = float(pos_diag.max() / pos_diag.min())
        if ratio > 1e12:
            warns.append(
                f"Köşegen ölçek oranı {ratio:.2e} (>1e12); kondisyon zayıf."
            )

    if sparse.issparse(K):
        row_max = np.abs(K.tocsr()).max(axis=1).toarray().ravel()
    else:
        row_max = np.max(np.abs(np.asarray(K, dtype=float)), axis=1)

    zero_rows = np.flatnonzero(row_max < 1e-12)
    if zero_rows.size > 0:
        warns.append(
            f"{zero_rows.size} DOF hiçbir elemanda bağlı değil "
            f"(örnek indeksler: {zero_rows[:5].tolist()})."
        )

    if check_rank:
        K_csc = K.tocsc() if sparse.issparse(K) else sparse.csc_matrix(np.asarray(K, dtype=float))
        fixed_arr = np.asarray(sorted(fixed_dofs), dtype=np.intp) if fixed_dofs else np.empty(0, dtype=np.intp)
        if fixed_arr.size > 0:
            all_dofs = np.arange(n_dof, dtype=np.intp)
            free = np.setdiff1d(all_dofs, fixed_arr)
            if free.size > 0:
                K_ff = K_csc[free, :][:, free].toarray()
                r_free = int(np.linalg.matrix_rank(K_ff, tol=rank_tol))
                if r_free < free.size:
                    defekt = free.size - r_free
                    warns.append(
                        f"Serbest alt matris tekil: rank {r_free}/{free.size} "
                        f"(eksik {defekt} bağımsız denklem). "
                        f"Yapıda mekanizma/eksik mesnet olabilir."
                    )
        else:
            r_full = int(np.linalg.matrix_rank(K_csc.toarray(), tol=rank_tol))
            if r_full < n_dof:
                warns.append(
                    f"K_global tekil: rank {r_full}/{n_dof}. "
                    f"Mesnetler yetersiz olabilir."
                )

    skipped = getattr(stiffness_assembly, "skipped", []) or []
    n_frames = getattr(stiffness_assembly, "frame_count", 0)
    n_areas = getattr(stiffness_assembly, "area_count", 0)
    n_links = getattr(stiffness_assembly, "link_count", 0)
    if n_frames == 0 and n_areas == 0 and n_links == 0:
        warns.append("Hiç eleman montaj edilmedi (frame/area/link = 0).")
    if skipped:
        warns.append(
            f"{len(skipped)} eleman atlandı "
            f"(örnek: {skipped[0] if len(skipped) == 1 else skipped[:3]})."
        )

    return warns


__all__ = [
    "AnalysisValidationError",
    "ValidationReport",
    "validate_model",
    "validate_mass",
    "validate_stiffness",
]