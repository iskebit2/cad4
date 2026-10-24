#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SAP2000 S2K Link Denetimi
- Kaynak S2K dosyasını değiştirmez.
- Link property, connectivity ve property assignment tablolarını denetler.
- Eksik/boş tabloları ve bağlantı referanslarını raporlar.
Kullanım:
    python s2k_link_audit.py "merdiven_s10_r_fixed.s2k"
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


TABLE_RE = re.compile(r'^\s*TABLE:\s*"([^"]+)"\s*$', re.IGNORECASE)
FIELD_RE = re.compile(r'(\w+)\s*=\s*("(?:[^"]|"")*"|\S+)')


def parse_tables(path: Path) -> dict[str, list[str]]:
    """S2K dosyasını tablo başlıklarına göre ayırır; satırları aynen korur."""
    tables: dict[str, list[str]] = {}
    current = None

    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                match = TABLE_RE.match(line)
                if match:
                    current = match.group(1).strip().upper()
                    tables.setdefault(current, [])
                elif current is not None:
                    stripped = line.strip()
                    if stripped and stripped != "END TABLE DATA":
                        tables[current].append(stripped)
    except OSError as exc:
        raise RuntimeError(f"Dosya okunamadı: {exc}") from exc

    return tables


def fields(line: str) -> dict[str, str]:
    """Bir S2K kayıt satırındaki alanları ayrıştırır."""
    result = {}
    for key, value in FIELD_RE.findall(line):
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('""', '"')
        result[key.upper()] = value
    return result


def find_table(tables: dict[str, list[str]], *fragments: str) -> tuple[str | None, list[str]]:
    for name, rows in tables.items():
        if all(fragment.upper() in name for fragment in fragments):
            return name, rows
    return None, []


def records(rows: list[str]) -> list[dict[str, str]]:
    return [fields(row) for row in rows if "=" in row]


def report(path: Path) -> int:
    tables = parse_tables(path)
    if not tables:
        logger.debug("HATA: Dosyada S2K tablo başlığı bulunamadı.")
        return 2

    logger.debug(f"Dosya: {path.resolve()}")
    logger.debug(f"Boyut: {path.stat().st_size:,} bayt")
    logger.debug(f"Bulunan tablo sayısı: {len(tables)}")

    link_conn_name, link_conn_rows = find_table(tables, "CONNECTIVITY", "LINK")
    link_assign_name, link_assign_rows = find_table(tables, "LINK", "PROPERTY", "ASSIGNMENTS")
    link_gen_name, link_gen_rows = find_table(tables, "LINK", "PROPERTY", "DEFINITIONS", "01")
    link_linear_name, link_linear_rows = find_table(tables, "LINK", "PROPERTY", "DEFINITIONS", "02")
    joints_name, joints_rows = find_table(tables, "JOINT COORDINATES")

    logger.debug("\n--- TABLO DURUMU ---")
    for label, name, rows in (
        ("Link bağlantıları", link_conn_name, link_conn_rows),
        ("Link özellik atamaları", link_assign_name, link_assign_rows),
        ("Link özellik tanımları", link_gen_name, link_gen_rows),
        ("Link doğrusal DOF tanımları", link_linear_name, link_linear_rows),
        ("Düğüm koordinatları", joints_name, joints_rows),
    ):
        logger.debug(f"{label}: {name or 'BULUNAMADI'} | kayıt={len(records(rows))}")

    conn = records(link_conn_rows)
    assignments = records(link_assign_rows)
    joint_records = records(joints_rows)

    joint_ids = {
        row.get("JOINT")
        for row in joint_records
        if row.get("JOINT")
    }

    logger.debug("\n--- LINK BAĞLANTI DENETİMİ ---")
    if not conn:
        logger.debug("SONUÇ: Dosyada tanımlı link bağlantısı yok.")
        logger.debug("Link malzemesi veya LINK_RIGID property tanımı tek başına eleman oluşturmaz.")
    else:
        logger.debug(f"Link bağlantı kaydı: {len(conn)}")
        missing_joints = []
        link_names = []

        for i, row in enumerate(conn, 1):
            link_name = row.get("LINK") or row.get("NAME") or f"<satır {i}>"
            ji = row.get("JOINTI") or row.get("JOINT_I") or row.get("JOINTI")
            jj = row.get("JOINTJ") or row.get("JOINT_J")
            link_names.append(link_name)

            if not ji or not jj:
                logger.debug(f"UYARI: {link_name}: I/J düğüm alanları tanınamadı: {row}")
                continue

            absent = [j for j in (ji, jj) if j not in joint_ids]
            if absent:
                missing_joints.append((link_name, ji, jj, absent))

        duplicates = [name for name, count in Counter(link_names).items() if count > 1]
        if duplicates:
            logger.debug(f"UYARI: Tekrarlanan link isimleri: {duplicates[:20]}")

        if missing_joints:
            logger.debug("UYARI: Koordinat tablosunda bulunamayan link düğümleri:")
            for item in missing_joints[:50]:
                logger.debug(f"  Link={item[0]} I={item[1]} J={item[2]} Eksik={item[3]}")
        else:
            logger.debug("Bağlantı satırlarında belirlenen I/J düğümleri koordinat tablosunda mevcut.")

    logger.debug("\n--- ÖZELLİK ATAMALARI ---")
    if not assignments:
        logger.debug("SONUÇ: Link property atama kaydı yok.")
    else:
        assigned_names = set()
        assigned_props = set()
        for row in assignments:
            name = row.get("LINK") or row.get("NAME")
            prop = row.get("PROPERTY") or row.get("LINKPROP") or row.get("LINKPROPERTY")
            if name:
                assigned_names.add(name)
            if prop:
                assigned_props.add(prop)
        logger.debug(f"Atama satırı: {len(assignments)}")
        if assigned_props:
            logger.debug("Atanan özellik adları:", ", ".join(sorted(assigned_props)))

    logger.debug("\n--- LINK PROPERTY TANIMLARI ---")
    if link_gen_rows:
        for row in link_gen_rows:
            if "=" in row:
                logger.debug("  " + row)
    else:
        logger.debug("UYARI: Genel link property tanım tablosu bulunamadı.")

    if link_linear_rows:
        logger.debug("Doğrusal DOF kayıtları:")
        for row in link_linear_rows:
            if "=" in row:
                logger.debug("  " + row)

    logger.debug("\n--- GENEL DEĞERLENDİRME ---")
    if not conn:
        logger.debug("Aktarımın geometri/nesne oluşturma aşaması bu S2K dosyasında tamamlanmamış.")
        logger.debug("Eksik link geometrisi, yalnızca bu dosyadan güvenilir biçimde üretilemez.")
        logger.debug("Kaynak model veya linkleri oluşturan Python kodu gerekir.")
        return 1

    if not assignments:
        logger.debug("Link geometrisi var, fakat özellik atamaları yok; atama tablosu ve ad eşleşmeleri incelenmeli.")
        return 1

    logger.debug("Link bağlantı ve atama kayıtları mevcut. Ayrıntılı geometri/özellik doğrulaması ayrıca yapılmalıdır.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SAP2000 S2K link aktarım denetimi")
    parser.add_argument("s2k", type=Path, help="Denetlenecek S2K dosyası")
    args = parser.parse_args()

    if not args.s2k.is_file():
        logger.debug(f"HATA: Dosya bulunamadı: {args.s2k}", file=sys.stderr)
        return 2

    try:
        return report(args.s2k)
    except Exception as exc:
        logger.debug(f"HATA: Denetim sırasında beklenmeyen sorun: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
