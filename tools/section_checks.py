# tools/section_checks.py
"""
Kesit özellikleri — derin doğrulama.

Katmanlar:
    1. Temel kontrol (core.units.validate_section_properties) — Area>0, r33 makul
    2. Analitik formüller (I, RECT, TUBE, PIPE) — profil boyutlarından I33/I22/J
    3. Katalog karşılaştırma — section.catalog_props varsa

Tüm fonksiyonlar saf: Section → list[str]. Yan etki yok, exception fırlatmaz.

Kullanım:
    from tools.section_checks import check_section
    for msg in check_section(section, strict=False):
        logger.debug("[SectionCheck] %s", msg)
"""
from __future__ import annotations

import math

from data.enums import SectionType
from domain.definition import Section

# ============================================================================
# SABİTLER
# ============================================================================
# Katalog/analitik karşılaştırma toleransları (relatif)
TOL_STRICT: float = 0.01    # %1 — strict mod
TOL_NORMAL: float = 0.10    # %10 — normal mod (yuvarlama, imalat toleransı)
TOL_LOOSE: float = 0.25     # %25 — J (torsiyon) için (yaklaşık formüller)

# Atalet yarıçapı makul aralığı (mm) — core.units ile aynı
R_MIN, R_MAX = 0.5, 500.0


# ============================================================================
# ANALİTİK KESİT FORMÜLLERİ
# ============================================================================
def analytical_i_section(
    h: float, b: float, tw: float, tf: float,
) -> dict[str, float]:
    """
    I-profile analitik özellikler (mm cinsinden giriş).

    h  : toplam yükseklik
    b  : flanş genişliği
    tw : gövde kalınlığı
    tf : flanş kalınlığı

    Dönen: {"Area", "I33", "I22", "J"}
    Not: J ince cidar yaklaşımı — SAP2000'den %10-20 sapabilir.
    """
    if h <= 0 or b <= 0 or tw <= 0 or tf <= 0:
        return {}
    if 2 * tf >= h:
        return {}  # flanşlar gövdeyi yutmuş

    hw = h - 2 * tf  # gövde yüksekliği
    A = 2 * b * tf + hw * tw
    # I33: güçlü eksen (y-yatay flanşlar)
    I33 = (b * h**3 - (b - tw) * hw**3) / 12.0
    # I22: zayıf eksen (düşey gövde + iki flanş)
    I22 = (2 * tf * b**3 + hw * tw**3) / 12.0
    # J: ince cidar torsiyon (yaklaşık)
    J = (2 * b * tf**3 + hw * tw**3) / 3.0
    return {"Area": A, "I33": I33, "I22": I22, "J": J}


def analytical_rect_section(h: float, b: float) -> dict[str, float]:
    """Dolu dikdörtgen. h: yükseklik (I33 ekseni), b: genişlik."""
    if h <= 0 or b <= 0:
        return {}
    A = h * b
    I33 = b * h**3 / 12.0
    I22 = h * b**3 / 12.0
    # Dolu dikdörtgen torsiyon (Timoshenko yaklaşımı)
    a, c = max(h, b), min(h, b)
    J = a * c**3 * (1.0 / 3.0 - 0.21 * (c / a) * (1.0 - (c / a) ** 4 / 12.0))
    return {"Area": A, "I33": I33, "I22": I22, "J": J}


def analytical_tube_section(
    h: float, b: float, t: float,
) -> dict[str, float]:
    """Dikdörtgen kutu (içi boş). t: et kalınlığı (tek)."""
    if h <= 0 or b <= 0 or t <= 0 or 2 * t >= min(h, b):
        return {}
    hi, bi = h - 2 * t, b - 2 * t
    A = h * b - hi * bi
    I33 = (b * h**3 - bi * hi**3) / 12.0
    I22 = (h * b**3 - hi * bi**3) / 12.0
    # İnce cidar kapalı kesit torsiyon (Bredt yaklaşımı)
    Am = (h - t) * (b - t)  # ortalama çevre alanı
    p = 2 * ((h - t) + (b - t))  # ortalama çevre
    J = 4 * Am**2 * t / p if p > 0 else 0.0
    return {"Area": A, "I33": I33, "I22": I22, "J": J}


def analytical_pipe_section(ro: float, ri: float) -> dict[str, float]:
    """Dairesel boru. ro: dış yarıçap, ri: iç yarıçap."""
    if ro <= 0 or ri < 0 or ri >= ro:
        return {}
    A = math.pi * (ro**2 - ri**2)
    I = math.pi * (ro**4 - ri**4) / 4.0
    J = math.pi * (ro**4 - ri**4) / 2.0
    return {"Area": A, "I33": I, "I22": I, "J": J}


# ============================================================================
# ANALİTİK DISPATCH
# ============================================================================
def analytical_properties(section) -> dict[str, float] | None:
    """
    Kesit tipine göre analitik özellikleri döndür.
    Bilinmeyen tip veya eksik parametre → None.
    """
    p = section.profile_params or {}
    t = section.profile_type

    def g(*keys) -> tuple[float, ...] | None:
        try:
            vals = tuple(float(p[k]) for k in keys)
        except (KeyError, TypeError, ValueError):
            return None
        return vals if all(v > 0 for v in vals) else None

    if t == SectionType.I:
        args = g("h", "b", "tw", "tf")
        return analytical_i_section(*args) if args else None

    if t == SectionType.RECT:
        args = g("h", "b")
        return analytical_rect_section(*args) if args else None

    if t == SectionType.TUBE:
        args = g("h", "b", "t")
        return analytical_tube_section(*args) if args else None

    if t == SectionType.PIPE:
        args = g("ro", "ri")
        return analytical_pipe_section(*args) if args else None

    # T, C, L, CUSTOM → atla (analitik formül karmaşık)
    return None


# ============================================================================
# KARŞILAŞTIRMA
# ============================================================================
_PROP_LABELS = {
    "Area": "Alan",
    "I33":  "I33 (güçlü eksen)",
    "I22":  "I22 (zayıf eksen)",
    "J":    "J (torsiyon)",
}

# J için tolerans daha gevşek (yaklaşık formüller)
_TOL_BY_PROP = {
    "Area": TOL_NORMAL,
    "I33":  TOL_NORMAL,
    "I22":  TOL_NORMAL,
    "J":    TOL_LOOSE,
}


def _compare(
    section,
    reference: dict[str, float],
    tol_by_prop: dict[str, float],
    source: str,
) -> list[str]:
    """
    section.profile_params ile reference sözlüğünü karşılaştır.
    Sadece reference'ta >0 olan anahtarlar kontrol edilir.
    """
    msgs: list[str] = []
    p = section.profile_params or {}

    for key, ref_val in reference.items():
        if ref_val <= 0:
            continue
        got = float(p.get(key, 0) or 0)
        if got <= 0:
            msgs.append(
                f"{section.name}: {_PROP_LABELS.get(key, key)} eksik/<=0 "
                f"({source} = {ref_val:.3e})"
            )
            continue
        rel = abs(got - ref_val) / ref_val
        tol = tol_by_prop.get(key, TOL_NORMAL)
        if rel > tol:
            msgs.append(
                f"{section.name}: {_PROP_LABELS.get(key, key)} = {got:.3e}, "
                f"{source} = {ref_val:.3e} (sapma %{rel*100:.2f}, tol %{tol*100:.0f})"
            )
    return msgs


# ============================================================================
# KESİT TİPİNE ÖZEL EK KONTROLLER
# ============================================================================
def _check_invariants(section) -> list[str]:
    """
    Genel kesit değişmezleri — analitik olmayan tipler için de geçerli.

    - I33 >= I22 (yapısal profil varsayımı; I-profile için her zaman doğru)
    - I33 + I22 >= J (torsiyon genelde ataletlerden küçük)
    - r33/r22 oranı profil tipine göre makul
    """
    msgs: list[str] = []
    p = section.profile_params or {}
    A   = float(p.get("Area", 0) or 0)
    I33 = float(p.get("I33", 0) or 0)
    I22 = float(p.get("I22", 0) or 0)
    J   = float(p.get("J", 0) or 0)

    if A <= 0 or I33 <= 0 or I22 <= 0:
        return msgs  # temel kontrol zaten yakalıyor

    # I33 vs I22 — I-profile, T, C, L için I33 > I22
    if section.profile_type in (SectionType.I, SectionType.T, SectionType.C):
        if I33 < I22 * 0.99:  # %1 tolerans
            msgs.append(
                f"{section.name}: {section.profile_type.name} için I33={I33:.2e} "
                f"< I22={I22:.2e} (beklenen I33 > I22)"
            )

    # Torsiyon J — genel olarak I33+I22'den küçük olmalı
    if J > 0 and J > (I33 + I22) * 1.05:
        msgs.append(
            f"{section.name}: J={J:.2e} > I33+I22={I33+I22:.2e} "
            f"(torsiyon sabiti çok büyük — birim hatası?)"
        )

    # Atalet yarıçapı
    r33 = math.sqrt(I33 / A)
    r22 = math.sqrt(I22 / A)
    if not (R_MIN <= r33 <= R_MAX):
        msgs.append(f"{section.name}: r33={r33:.2f} mm makul aralık dışında")
    if not (R_MIN <= r22 <= R_MAX):
        msgs.append(f"{section.name}: r22={r22:.2f} mm makul aralık dışında")

    return msgs


def _check_unit_suspicion(section) -> list[str]:
    """
    Birim hatası belirtileri — değerler tipik aralığın çok dışındaysa.

    Tipik çelik kesitler:
        A   : 100 .. 1e5 mm²
        I33 : 1e4 .. 1e10 mm⁴
        E   : 2.0e5 MPa (çelik), 3.0e4 MPa (beton)
    """
    msgs: list[str] = []
    p = section.profile_params or {}
    A   = float(p.get("Area", 0) or 0)
    I33 = float(p.get("I33", 0) or 0)

    if A > 0 and not (10.0 <= A <= 1e6):
        msgs.append(
            f"{section.name}: Area={A:.3e} mm² tipik aralık dışında "
            f"(10..1e6) — birim hatası olabilir"
        )
    if I33 > 0 and not (1e2 <= I33 <= 1e12):
        msgs.append(
            f"{section.name}: I33={I33:.3e} mm⁴ tipik aralık dışında "
            f"(1e2..1e12) — birim hatası olabilir"
        )

    # Malzeme E
    mat = section.material
    if mat is not None:
        E = float(getattr(mat, "E1", 0) or 0)
        if E > 0 and not (1e3 <= E <= 1e6):
            msgs.append(
                f"{section.name}: Material.E1={E:.3e} MPa tipik aralık dışında "
                f"(1e3..1e6) — birim hatası olabilir"
            )

    return msgs


# ============================================================================
# ANA GİRİŞ
# ============================================================================
def check_section(section, *, strict: bool = False) -> list[str]:
    """
    Tek kesit için tam doğrulama.

    Parameters
    ----------
    section : Section
    strict  : True → %1 tolerans (imalat/katalog için), False → %10

    Returns
    -------
    List[str] — boş ise OK, dolu ise uyarı/hata mesajları
    """
    if section is None:
        return ["Section None"]

    msgs: list[str] = []

    # 1. Değişmezler (analitik olmadan da geçerli)
    msgs.extend(_check_invariants(section))

    # 2. Birim şüphesi
    msgs.extend(_check_unit_suspicion(section))

    # 3. Analitik karşılaştırma
    anal = analytical_properties(section)
    if anal:
        base_tol = TOL_STRICT if strict else TOL_NORMAL
        tol_by_prop = {
            k: (TOL_STRICT if strict else _TOL_BY_PROP.get(k, base_tol))
            for k in anal
        }
        msgs.extend(_compare(section, anal, tol_by_prop, "analitik"))

    # 4. Katalog karşılaştırma (varsa)
    catalog = getattr(section, "catalog_props", None) or {}
    if catalog:
        base_tol = TOL_STRICT if strict else TOL_NORMAL
        tol_by_prop = {k: base_tol for k in catalog}
        msgs.extend(_compare(section, catalog, tol_by_prop, "katalog"))

    return msgs


# ============================================================================
# TOPLU DOĞRULAMA (isteğe bağlı)
# ============================================================================
def check_all_sections(
    sections: dict[str, Section],
    *,
    strict: bool = False,
    logger=None,
) -> dict[str, list[str]]:
    """
    Tüm kesitleri doğrula.

    Returns
    -------
    {section_name: [msgs]} — sadece uyarısı olanlar döner.
    """
    out: dict[str, list[str]] = {}
    for name, section in sections.items():
        msgs = check_section(section, strict=strict)
        if msgs:
            out[name] = msgs
            if logger is not None:
                for m in msgs:
                    logger.debug("[SectionCheck] %s", m)
    return out