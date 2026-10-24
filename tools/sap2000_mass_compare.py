# tools/sap2000_mass_compare.py — TEMİZ

import re
from pathlib import Path
from typing import Dict

import numpy as np


# ============================================================================
# PARSER
# ============================================================================
def _find_table_block(text: str, table_name: str) -> str | None:
    """
    SAP2000 metin çıktısında 'Table: <table_name>' bloğunu bul.
    Blok, bir sonraki 'Table:' veya dosya sonuna kadar.
    """
    pattern = re.compile(
        rf'Table:\s*"?{re.escape(table_name)}"?\s*\n(.*?)(?=\n\s*Table:|\Z)',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1) if m else None


def _parse_numeric_row(line: str) -> list[float] | None:
    """
    Bir satırdaki sayısal değerleri çıkar (virgül → nokta).
    """
    tokens = line.split()
    out = []
    for tok in tokens:
        t = tok.replace(",", ".")
        try:
            out.append(float(t))
        except ValueError:
            return None
    return out if out else None


def parse_sap2000_mass_table(path: str) -> Dict[int, dict]:
    """
    SAP2000 'Assembled Joint Masses' tablosunu parse et.

    Dönüş:
        {joint_id: {"U1": ton, "U2": ton, "U3": ton,
                    "R1": ton·mm², ..., "X": mm, "Y": mm, "Z": mm}}
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SAP2000 mass tablosu yok: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    block = _find_table_block(text, "Assembled Joint Masses")
    if not block:
        return {}

    out: Dict[int, dict] = {}
    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # İlk token integer mı?
        parts = stripped.split()
        if not parts or not parts[0].lstrip("+-").isdigit():
            continue   # başlık / SumAccel satırı
        if len(parts) < 10:
            continue
        try:
            jid = int(parts[0])
            # parts[1] = MassSource, parts[2:] = 9 sayısal (U1,U2,U3,R1,R2,R3,X,Y,Z)
            vals = [float(p.replace(",", ".")) for p in parts[2:11]]
        except (ValueError, IndexError):
            continue
        if len(vals) != 9:
            continue
        out[jid] = {
            "U1": vals[0], "U2": vals[1], "U3": vals[2],
            "R1": vals[3], "R2": vals[4], "R3": vals[5],
            "X": vals[6], "Y": vals[7], "Z": vals[8],
        }
    return out


def parse_sap2000_modal_periods(path: str) -> Dict[int, float]:
    """
    SAP2000 'Modal Periods And Frequencies' tablosunu parse et.

    Dönüş: {step_num: period_s}
    """
    path = Path(path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="ignore")
    block = _find_table_block(text, "Modal Periods And Frequencies")
    if not block:
        return {}

    out: Dict[int, float] = {}
    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        # Satır: MODAL Mode 1 0.582567 ...
        if len(parts) < 4:
            continue
        if parts[0].upper() != "MODAL":
            continue
        if parts[1].upper() != "MODE":
            continue
        try:
            step = int(parts[2])
            period = float(parts[3].replace(",", "."))
        except (ValueError, IndexError):
            continue
        if step > 0:
            out[step] = period
    return out


# ============================================================================
# KARŞILAŞTIRMA
# ============================================================================
def compare_with_sap2000(
    sap_file: str,
    scn,
    mass,
    *,
    tol_warn: float = 0.05,
    tol_bad: float = 0.20,
) -> bool:
    """
    SAP2000 mass tablosu ile Cad4 modelini karşılaştır.
    """
    sap_data = parse_sap2000_mass_table(sap_file)
    if not sap_data:
        print(f"❌ SAP2000 mass tablosu boş veya parse edilemedi: {sap_file}")
        return False

    label_to_key = {}
    for key, node in scn.nodes.items():
        try:
            jid = int(str(node.label).strip())
            label_to_key[jid] = key
        except (ValueError, TypeError):
            continue

    print("\n--- SAP2000 Joint Mass Karşılaştırma ---")
    print(f"{'J':>3} {'X':>7} {'Y':>7} {'Z':>7} "
          f"{'SAP-U1(t)':>10} {'Cad4-U1(t)':>10} {'Fark%':>8} {'Durum':>6}")
    print("-" * 75)

    sap_total = 0.0
    cad_total = 0.0
    n_ok = n_warn = n_bad = 0
    all_ok = True

    for jid in sorted(sap_data.keys()):
        sap = sap_data[jid]
        m_sap_ton = sap["U1"]
        key = label_to_key.get(jid)
        if key is None:
            print(f"{jid:>3} {'?':>7} {'?':>7} {'?':>7} "
                  f"{m_sap_ton:>10.4f} {'—':>10} {'—':>8} {'YOK':>6}")
            n_bad += 1
            all_ok = False
            continue
        node = scn.nodes[key]
        m_cad_ton = mass.node_masses.get(key, 0.0) / 1000.0
        sap_total += m_sap_ton
        cad_total += m_cad_ton
        if m_sap_ton > 1e-6:
            rel = abs(m_cad_ton - m_sap_ton) / m_sap_ton
            if rel < tol_warn:
                status, n_ok = "✅", n_ok + 1
            elif rel < tol_bad:
                status, n_warn = "⚠️", n_warn + 1
                all_ok = False
            else:
                status, n_bad = "❌", n_bad + 1
                all_ok = False
        else:
            rel, status = float("nan"), "—"
        print(f"{jid:>3} {node.x:>7.0f} {node.y:>7.0f} {node.z:>7.0f} "
              f"{m_sap_ton:>10.4f} {m_cad_ton:>10.4f} "
              f"{rel*100:>7.2f}% {status:>6}")

    print("-" * 75)
    delta = cad_total - sap_total
    print(f"{'TOP':>3} {'':>7} {'':>7} {'':>7} "
          f"{sap_total:>10.4f} {cad_total:>10.4f} "
          f"{abs(delta)/max(sap_total, 1e-9)*100:>7.2f}%")
    print(f"\n✅ Uyumlu: {n_ok}, ⚠️ Uyarı: {n_warn}, ❌ Uyumsuz: {n_bad}")
    print(f"SAP2000 SumAccelUX = {sap_total:.4f} ton = {sap_total*1000:.2f} kg")
    print(f"Cad4     toplam    = {cad_total:.4f} ton = {cad_total*1000:.2f} kg")
    print(f"Fark: {delta*1000:+.2f} kg ({delta/max(sap_total,1e-9)*100:+.2f}%)")
    return all_ok


def compare_modal_periods(
    sap_file: str,
    modal,
    *,
    tol_warn: float = 0.10,
    tol_bad: float = 0.30,
) -> bool:
    """SAP2000 modal periyotları ile Cad4 periyotlarını karşılaştır."""
    sap_periods = parse_sap2000_modal_periods(sap_file)
    if not sap_periods:
        print("\n⚠️  SAP2000 modal tablosu bulunamadı, atlandı")
        return True

    print("\n--- SAP2000 Modal Period Karşılaştırma ---")
    print(f"{'Mod':>3} {'SAP T(s)':>10} {'Cad4 T(s)':>10} "
          f"{'Fark%':>8} {'Durum':>6}")
    print("-" * 50)

    n_ok = n_warn = n_bad = 0
    all_ok = True
    max_mod = min(len(modal.periods), max(sap_periods.keys()))

    for i in range(max_mod):
        mod_no = i + 1
        T_sap = sap_periods.get(mod_no)
        if T_sap is None:
            continue
        T_cad = float(modal.periods[i])
        rel = abs(T_cad - T_sap) / T_sap if T_sap > 0 else float("nan")
        if rel < tol_warn:
            status, n_ok = "✅", n_ok + 1
        elif rel < tol_bad:
            status, n_warn = "⚠️", n_warn + 1
            all_ok = False
        else:
            status, n_bad = "❌", n_bad + 1
            all_ok = False
        print(f"{mod_no:>3} {T_sap:>10.4f} {T_cad:>10.4f} "
              f"{rel*100:>7.2f}% {status:>6}")

    print(f"\n✅ Uyumlu: {n_ok}, ⚠️ Uyarı: {n_warn}, ❌ Uyumsuz: {n_bad}")
    return all_ok