# app/commands/analysis/validation.py
"""Model doğrulama katmanı.

Tasarım ilkeleri
----------------
1. **Sadece analizi fiilen imkânsız kılan durumlar ``errors``'a yazılır.**
   (eksik malzeme, sıfır uzunluklu eleman, tekil sistem, vs.)
2. **Kullanıcının bilmesi gereken ama analizi engellemeyen durumlar**
   ``warnings``'e yazılır (auto_mesh paramsız + fallback, düşük yoğunluk, vs.)
3. ``strict=True`` yalnızca ``errors`` doluysa ``AnalysisValidationError``
   fırlatır. ``warnings`` her zaman sessizce raporlanır.
4. Her kontrol kendi alt fonksiyonunda; ``_Checker`` sınıfı state'i taşır.
   Bu, yeni kural eklemeyi ve test etmeyi kolaylaştırır.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from logging_config import CadLogger

logger = CadLogger.get(__name__)


# =============================================================================
# Hata / Rapor tipleri
# =============================================================================
class AnalysisValidationError(Exception):
    """``strict=True`` modunda, düzeltilmesi zorunlu hatalar bulunduğunda."""

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


# =============================================================================
# Yardımcılar
# =============================================================================
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
    try:
        return float(getattr(obj, name, default) or default)
    except (TypeError, ValueError):
        return default


# =============================================================================
# Frame mesh planı (mesher._frame_station_ratios ile aynı mantık)
# =============================================================================
def _resolve_frame_mesh_plan(frame) -> tuple[int, str, bool]:
    """Mesher'ın gerçekte kullanacağı segmentasyonu çözer.

    Dönen: (n_segments, kaynak, fallback_kullanıldı_mı)
    - kaynak: "mesh_num_segments" | "mesh_max_length" | "max_sta_spcg"
              | "min_num_sta" | "single"
    """
    L = _get_param(frame, "get_length", 0.0)
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


# =============================================================================
# Kontrolör
# =============================================================================
class _ModelChecker:
    """Model + proje üzerinde tüm alt kontrolleri koordine eder."""

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

    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 1) Birim sistemi
    # ------------------------------------------------------------------
    def _check_units(self) -> None:
        units = getattr(self.project, "units", None)
        if units is None:
            self.report.add_warning(
                "Proje birim sistemi tanımsız; varsayılan N-mm kullanılacak."
            )

    # ------------------------------------------------------------------
    # 2) Malzemeler
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 3) Frame'ler
    # ------------------------------------------------------------------
    def _check_frames(self) -> None:
        frames = getattr(self.model, "frames", {}) or {}
        for frame in frames.values():
            self._check_frame(frame)

    def _check_frame(self, frame) -> None:
        label = _label(frame, "Frame")

        # Düğümler
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

        # Kesit + malzeme
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

        # Serbestlik / mesnet kombinasyonu
        r_i = getattr(frame, "release_i", None)
        r_j = getattr(frame, "release_j", None)
        if _all_released(r_i) and _all_released(r_j):
            self.report.add_warning(
                f"{label}: her iki uçta tüm serbestlikler açık; eleman mekanizmada."
            )

        # Mesh planı
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

    # ------------------------------------------------------------------
    # 4) Area'lar
    # ------------------------------------------------------------------
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

        # --- Malzeme: load transfer ise zorunlu değil ---
        is_lt = True
        mat = getattr(area, "material", None)
        if mat is None:
            sec = getattr(area, "area_section", None)
            mat = getattr(sec, "material", None) if sec else None

        if not is_lt:
            if mat is None:
                self.report.add_error(f"{label}: malzeme atanmamış.")
            elif _get_param(mat, "E1", 0.0) <= 0.0:
                self.report.add_error(f"{label}: malzeme E1 ≤0.")

        # --- Kalınlık ---
        th = _get_param(area, "thickness", 0.0)
        if th <= _EPS:
            if is_lt:
                # Bilinçli kullanım: yapısal katkı yok, yalnızca yük dağıtımı
                self.report.add_warning(
                    f"{label}: kalınlık ≈0 → 'load transfer' alanı olarak "
                    f"yorumlanacak (K/M'ye katkısı yok)."
                )
            else:
                # Material/section varsa ama kalınlık 0 → gerçek hata
                self.report.add_error(f"{label}: kalınlık ≤0 ({th}).")

        # --- Geometri ---
        pts = [(n.x, n.y, n.z) for n in nodes]
        area_val = _polygon_area(pts)
        if area_val <= 1e-6 * max(1.0, th):
            self.report.add_error(
                f"{label}: poligon alanı ≈0 ({area_val:.3e}); geometri dejenere."
            )
        if _has_duplicate_points(pts):
            self.report.add_error(f"{label}: aynı koordinatta iki düğüm var.")


    def _is_load_transfer(area) -> bool:
        """Area yük dağıtım elemanı mı (yapısal katkısı yok)?"""
        # Explicit davranış alanı varsa
        behavior = getattr(area, "behavior", None)
        if behavior is not None and str(getattr(behavior, "value", behavior)).lower() == "loadtransfer":
            return True
        # Fallback: kalınlık ≈ 0
        try:
            th = float(getattr(area, "thickness", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
        return th <= 1e-9

    # ------------------------------------------------------------------
    # 5) Link'ler
    # ------------------------------------------------------------------
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
            ) if all(hasattr(n, "x") for n in (ni, nj)) else 0.0
            if L <= _EPS:
                self.report.add_error(f"{label}: uzunluk sıfır.")
                continue

            prop_name = getattr(link, "propname", "")
            if prop_name and prop_name not in self._link_props:
                self.report.add_error(
                    f"{label}: link özelliği '{prop_name}' proje kayıtlarında yok."
                )

    # ------------------------------------------------------------------
    # 6) Düğümler
    # ------------------------------------------------------------------
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

            # Yay/spring değerleri pozitif mi
            for sname in ("spring_u1", "spring_u2", "spring_u3",
                          "spring_r1", "spring_r2", "spring_r3"):
                v = _get_param(node, sname, 0.0)
                if v < 0.0:
                    self.report.add_warning(
                        f"{label}: {sname}={v} negatif (yorum belirsiz)."
                    )

    # ------------------------------------------------------------------
    # 7) Yükler
    # ------------------------------------------------------------------
    def _check_loads(self) -> None:
        # Yük pattern'ları
        if not self._load_patterns:
            self.report.add_warning("Hiç yük pattern'ı tanımlı değil.")

        # Yük case'leri
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

        # Yüklerin pattern'ları mevcut mu
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

    # ------------------------------------------------------------------
    # 8) Mesnetler
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 9) Duplicate düğümler
    # ------------------------------------------------------------------
    def _check_duplicates(self) -> None:
        nodes = list((getattr(self.model, "nodes", {}) or {}).values())
        tol = 1e-4
        seen: dict[tuple[int, int, int], str] = {}
        dups = 0
        for n in nodes:
            try:
                key = (round(n.x / tol), round(n.y / tol), round(n.z / tol))
            except (TypeError, AttributeError):
                continue
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


# =============================================================================
# Yardımcı fonksiyonlar (modül seviyesi)
# =============================================================================
def _get_param_from_dict(d: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key, default) or default)
    except (TypeError, ValueError):
        return default


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


# =============================================================================
# Public API
# =============================================================================
def validate_model(model, project, strict: bool = True) -> ValidationReport:
    """Modeli analiz öncesi doğrular.

    Parameters
    ----------
    model : MathModel
        Düğüm, frame, area, link koleksiyonlarını içeren model.
    project : Project
        Malzeme, kesit, pattern, case, birim bilgilerini içeren proje.
    strict : bool
        ``True`` ise ``report.errors`` dolu olduğunda
        ``AnalysisValidationError`` fırlatır. ``False`` ise sadece
        raporu döndürür.

    Returns
    -------
    ValidationReport
    """
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
    """``MassAssembly`` üzerinde tutarlılık kontrolleri.

    Bu fonksiyon ``build_mass`` sonunda çağrılır. Sadece uyarı üretir
    (kütle problemi analizi fiilen durdurmaz).
    """
    warns: list[str] = []
    if mass_assembly is None:
        return ["Kütle montajı None."]

    total_kg = getattr(mass_assembly, "total_kg", 0.0)
    if total_kg <= 0.0:
        warns.append(
            "Toplam kütle 0; modal analiz sıfır özdeğer üretebilir."
        )

    # M_global: simetri + PSD kontrolü (yalnızca consistent modda)
    if is_consistent:
        import numpy as np
        M = getattr(mass_assembly, "M_global", None)
        if M is not None and M.size > 0:
            if not np.allclose(M, M.T, atol=1e-9, rtol=1e-6):
                warns.append("M_global simetrik değil.")
            diag = np.diag(M)
            if np.any(diag < -1e-12):
                warns.append(
                    "M_global köşegeninde negatif değer(ler) var."
                )
            if np.allclose(M, 0.0):
                warns.append("M_global tamamen sıfır.")

    # Katkı özeti
    contribs = getattr(mass_assembly, "contributions", []) or []
    if not contribs:
        warns.append("Kütle katkısı kaydı boş (mass_assembly.contributions).")
    else:
        bad = [c for c in contribs
               if not math.isfinite(getattr(c, "mass_kg", 0.0))
               or getattr(c, "mass_kg", 0.0) < 0.0]
        if bad:
            warns.append(
                f"{len(bad)} kütle katkısı negatif veya NaN."
            )

    return warns

# app/commands/analysis/validation.py
# ... (mevcut refactor kodu) ...

import numpy as np


def validate_stiffness(
    stiffness_assembly,
    fixed_dofs: list[int] | None = None,
    *,
    check_rank: bool = True,
    rank_tol: float = 1e-9,
) -> list[str]:
    """``StiffnessAssembly`` üzerinde montaj sonrası tutarlılık kontrolleri.

    Bu fonksiyon ``build_stiffness`` sonunda çağrılır. Dönen liste **uyarı**
    niteliğindedir; ancak boş olmayan liste, çözümün tekil/hatalı olma
    riskini gösterir. Çözücü (``StructuralSolver``) yine de çalışabilir;
    nihai karar çağıranındır.

    Parametreler
    ------------
    stiffness_assembly : StiffnessAssembly
        ``K_global`` (N/mm), ``frame_count``, ``area_count``, ``link_count``,
        ``skipped``, ``warnings`` alanlarını taşıyan nesne.
    fixed_dofs : list[int] | None
        Mesnetli DOF endeksleri. Verilirse, serbest (free) alt matrisin
        rank'ı kontrol edilir. Verilmezse yalnızca global K kontrol edilir.
    check_rank : bool
        Rank testi yapılsın mı (büyük modellerde pahalı olabilir).
    rank_tol : float
        ``np.linalg.matrix_rank`` için göreli tolerans.

    Returns
    -------
    list[str]
        Uyarı listesi. Boşsa montaj sağlıklı.
    """
    warns: list[str] = []
    if stiffness_assembly is None:
        return ["StiffnessAssembly None; rijitlik montajı yapılmamış."]

    K = getattr(stiffness_assembly, "K_global", None)
    if K is None or K.size == 0:
        return ["K_global boş veya None."]

    n_dof = K.shape[0]
    if K.shape[0] != K.shape[1]:
        warns.append(f"K_global kare değil: {K.shape}.")
        return warns

    # 1) Sonluluk
    if not np.all(np.isfinite(K)):
        n_bad = int((~np.isfinite(K)).sum())
        warns.append(f"K_global'de {n_bad} adet NaN/Inf eleman var.")

    # 2) Simetri
    if not np.allclose(K, K.T, atol=1e-6, rtol=1e-6):
        max_asym = float(np.max(np.abs(K - K.T)))
        warns.append(f"K_global simetrik değil (max asimetri {max_asym:.3e}).")

    # 3) Köşegen işareti
    diag = np.diag(K)
    if np.any(diag < -1e-9):
        n_neg = int((diag < -1e-9).sum())
        warns.append(
            f"K_global köşegeninde {n_neg} negatif değer var "
            f"(min {float(diag.min()):.3e})."
        )
    if np.allclose(diag, 0.0, atol=1e-12):
        warns.append("K_global köşegeni tamamen sıfır.")

    # 4) Ölçek / kondisyon
    if np.any(diag > 0):
        ratio = float(diag[diag > 0].max() / diag[diag > 0].min())
        if ratio > 1e12:
            warns.append(
                f"Köşegen ölçek oranı {ratio:.2e} (>1e12); kondisyon zayıf."
            )

    # 5) Sıfır satır/sütun → hiçbir elemanda bağlanmamış DOF
    zero_rows = np.where(np.all(np.abs(K) < 1e-12, axis=1))[0]
    if zero_rows.size > 0:
        warns.append(
            f"{zero_rows.size} DOF hiçbir elemanda bağlı değil "
            f"(örnek indeksler: {zero_rows[:5].tolist()})."
        )

    # 6) Rank / tekil kontrol
    if check_rank:
        try:
            if fixed_dofs:
                all_dofs = np.arange(n_dof)
                free = np.setdiff1d(all_dofs, np.asarray(fixed_dofs))
                if free.size > 0:
                    K_ff = K[np.ix_(free, free)]
                    r_free = int(np.linalg.matrix_rank(K_ff, tol=rank_tol))
                    if r_free < free.size:
                        defekt = free.size - r_free
                        warns.append(
                            f"Serbest alt matris tekil: rank {r_free}/{free.size} "
                            f"(eksik {defekt} bağımsız denklem). "
                            f"Yapıda mekanizma/eksik mesnet olabilir."
                        )
            else:
                r_full = int(np.linalg.matrix_rank(K, tol=rank_tol))
                if r_full < n_dof:
                    warns.append(
                        f"K_global tekil: rank {r_full}/{n_dof}. "
                        f"Mesnetler yetersiz olabilir."
                    )
        except np.linalg.LinAlgError as exc:
            warns.append(f"Rank hesabı başarısız: {exc}")

    # 7) Montaj istatistikleri
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
    "validate_stiffness"
]