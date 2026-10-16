# tools/s2k_export_service.py
"""
S2K Export Service — Frame distributed load'ları SAP2000 formatında dışa aktarır.
"""
from typing import List

from domain.definition import SAP_DIR_CODES


class S2KExportService:

    # 10 yön SAP2000 kodları (Dir alanı için tam harita)
    type_to_sap_dir = {
        "1":  "1",   # Local 1
        "2":  "2",   # Local 2
        "3":  "3",   # Local 3
        "4":  "4",   # Global X
        "5":  "5",   # Global Y
        "6":  "6",   # Global Z
        "7":  "7",   # Gravity
        "8":  "8",   # Projected X
        "9":  "9",   # Projected Y
        "10": "10",  # Projected Z
    }

    # tools/s2k_export_service.py
    @classmethod
    def export_frame_distributed_loads_to_s2k(cls, frame_objects) -> str:
        lines = ['TABLE: "FRAME ASSIGN - DISTRIBUTED"']

        for frame in frame_objects:
            if not hasattr(frame, "dist_loads") or not frame.dist_loads:
                continue

            frame_id = (
                getattr(frame, "label", None)
                or getattr(frame, "name", None)
                or f"Frame_{getattr(frame, 'unique_id', id(frame))}"
            )

            for load in frame.dist_loads:
                # Güvenlik: points boş veya None olabilir
                pts = list(getattr(load, "points", None) or [])
                if not pts:
                    # Sessizce atla (SAP2000 default ile eşleşmez)
                    continue

                # Tek nokta varsa (tek nokta yükü) 2. noktayı ekle
                while len(pts) < 4:
                    pts.append(pts[-1])

                (d1, v1) = pts[0]
                (d2, v2) = pts[1]
                (d3, v3) = pts[2]
                (d4, v4) = pts[3]

                pattern = load.pattern_name
                coord_sys = getattr(load, "coord_sys", "Local")
                direction = cls.type_to_sap_dir.get(
                    str(getattr(load, "load_dir", "2")), "2"
                )
                dist_type = "Relative" if getattr(load, "is_relative", True) else "Absolute"
                opt = "Add" if load.mode == "ADD" else "Replace"

                line = (
                    f'   Frame="{frame_id}"  LoadPat="{pattern}"  '
                    f'CoordSys="{coord_sys}"  DistType="{dist_type}"  Dir="{direction}"  '
                    f'Dist1={d1:.4f}  V1={v1:.4f}  '
                    f'Dist2={d2:.4f}  V2={v2:.4f}  '
                    f'Dist3={d3:.4f}  V3={v3:.4f}  '
                    f'Dist4={d4:.4f}  V4={v4:.4f}  '
                    f'Opt="{opt}"'
                )
                lines.append(line)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    @classmethod
    def export_full_table(cls, frame_objects) -> str:
        """
        Tam s2k bloğu: header + default satır + tüm frame satırları.
        SAP2000'in okuduğu format.
        """
        header = [
            'TABLE: "FRAME ASSIGN - DISTRIBUTED"',
            '   Frame="DEFAULT"  LoadPat="DEFAULT"  CoordSys="Local"  '
            'DistType="Relative"  Dir="2"  V1=0  V2=0  Dist1=0  Dist2=0  Opt="Replace"',
        ]
        body = cls.export_frame_distributed_loads_to_s2k(frame_objects)
        # Body zaten ilk satırı TABLE ile başlatıyor, onu atlayalım
        body_lines = body.split("\n")[1:]
        return "\n".join(header + body_lines)