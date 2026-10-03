from __future__ import annotations

from io import BytesIO
from typing import Any, Optional

import pandas as pd


class ReportDataFrame(pd.DataFrame):
    _metadata = [
        "custom_title",
        "custom_desc",
        "column_descriptions",
        "column_units",
        "column_formats",
        "_table_style",
        "graphics",
    ]

    def __init__(self, *args, **kwargs):
        self.custom_title = kwargs.pop("custom_title", None)
        self.custom_desc = kwargs.pop("custom_desc", None)
        self.column_descriptions = kwargs.pop("column_descriptions", {})
        self.column_units = kwargs.pop("column_units", {})
        self.column_formats = kwargs.pop("column_formats", {})
        self._table_style = kwargs.pop("table_style", "Table Grid")
        self.graphics = kwargs.pop("graphics", []) or []

        super().__init__(*args, **kwargs)

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            df = ReportDataFrame(*args, **kwargs)
            df.custom_title = getattr(self, "custom_title", None)
            df.custom_desc = getattr(self, "custom_desc", None)
            df.column_descriptions = getattr(self, "column_descriptions", {}).copy()
            df.column_units = getattr(self, "column_units", {}).copy()
            df.column_formats = getattr(self, "column_formats", {}).copy()
            df._table_style = getattr(self, "_table_style", "Table Grid")
            df.graphics = [g.copy() for g in getattr(self, "graphics", [])]
            return df

        return _c

    def set_column_description(
        self, column: str, description: str
    ) -> ReportDataFrame:
        self.column_descriptions[column] = description
        return self

    def set_column_unit(self, column: str, unit: str) -> ReportDataFrame:
        self.column_units[column] = unit
        return self

    def set_column_format(self, column: str, fmt: str) -> ReportDataFrame:
        self.column_formats[column] = fmt
        return self

    def add_graphic(
        self,
        data: BytesIO | bytes | None = None,
        image: BytesIO | bytes | None = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        format: str = "png",
    ) -> ReportDataFrame:
        img_data = data if data is not None else image

        if isinstance(img_data, bytes):
            img_data = BytesIO(img_data)

        if not isinstance(img_data, BytesIO):
            raise TypeError("Görsel verisi BytesIO veya bytes türünde olmalıdır.")

        self.graphics.append(
            {
                "data": img_data,
                "image": img_data,
                "title": title,
                "description": description,
                "width": width,
                "height": height,
                "format": format,
            }
        )
        return self

    def clear_graphics(self) -> ReportDataFrame:
        self.graphics.clear()
        return self

    def _format_value(self, column: str, value: Any) -> str:
        if pd.isna(value):
            return ""

        fmt = self.column_formats.get(column)
        if fmt is None:
            return str(value)

        try:
            return format(value, fmt)
        except (TypeError, ValueError):
            return str(value)

    def _format_row(self, row: pd.Series) -> list[str]:
        return [
            self._format_value(column, val) for column, val in row.items()
        ]

    def round_numeric(self, decimals: int = 2) -> ReportDataFrame:
        numeric_cols = self.select_dtypes(include="number").columns
        self[numeric_cols] = self[numeric_cols].round(decimals)
        return self

    def _repr_html_(self) -> str:
        import base64
        from html import escape

        parts = []

        # 1. Başlık
        if getattr(self, "custom_title", None):
            parts.append(f"<h4 style='margin-bottom: 5px;'>{escape(str(self.custom_title))}</h4>")

        # 2. Açıklama
        if getattr(self, "custom_desc", None):
            parts.append(f"<p style='margin-top: 0; margin-bottom: 10px;'>{escape(str(self.custom_desc))}</p>")

        # 3. Görseller
        graphics = getattr(self, "graphics", [])
        for graphic in graphics:
            graphic_title = graphic.get("title")
            graphic_desc = graphic.get("description")

            if graphic_title:
                parts.append(f"<h5 style='margin-bottom: 3px;'>{escape(str(graphic_title))}</h5>")
            if graphic_desc:
                parts.append(f"<p style='margin-top: 0; margin-bottom: 8px; font-size: 0.9em;'>{escape(str(graphic_desc))}</p>")

            img_stream = graphic.get("image") or graphic.get("data")
            if img_stream:
                if hasattr(img_stream, "seek"):
                    img_stream.seek(0)
                    img_bytes = img_stream.read()
                elif isinstance(img_stream, bytes):
                    img_bytes = img_stream
                else:
                    img_bytes = None

                if img_bytes:
                    base64_img = base64.b64encode(img_bytes).decode("utf-8")
                    parts.append(
                        f'<div style="display: block; margin-bottom: 15px;">'
                        f'<img src="data:image/png;base64,{base64_img}" style="display: block; max-width: 100%; height: auto;" />'
                        f'</div>'
                    )

        # 4. Tablo
        if self.empty:
            parts.append("<p>Gösterilecek veri bulunamadı.</p>")
            return "".join(parts)

        html = ["<table border='1' style='border-collapse: collapse; width: 100%; display: table; clear: both; margin-top: 10px;'><thead>"]
        
        # Kolon Başlıkları
        html.append("<tr>")
        for col in self.columns:
            html.append(f"<th>{escape(str(col))}</th>")
        html.append("</tr>")

        # Birimler
        column_units = getattr(self, "column_units", None)
        if column_units:
            html.append("<tr>")
            for col in self.columns:
                unit = column_units.get(col, "") if isinstance(column_units, dict) else ""
                html.append(f"<th style='font-weight: normal; font-style: italic;'>{escape(str(unit))}</th>")
            html.append("</tr>")

        # Açıklamalar
        column_descriptions = getattr(self, "column_descriptions", None)
        if column_descriptions:
            html.append("<tr>")
            for col in self.columns:
                desc = column_descriptions.get(col, "") if isinstance(column_descriptions, dict) else ""
                html.append(f"<th style='font-weight: normal;'>{escape(str(desc))}</th>")
            html.append("</tr>")

        html.append("</thead><tbody>")

        # Veri Satırları
        for _, row in self.iterrows():
            html.append("<tr>")
            values = self._format_row(row) if hasattr(self, "_format_row") else row.values
            for val in values:
                html.append(f"<td>{escape(str(val))}</td>")
            html.append("</tr>")

        html.append("</tbody></table>")
        parts.append("".join(html))

        return "".join(parts)

    def save_to_docx(
        self,
        document,
        title: Optional[str] = None,
        desc: Optional[str] = None,
        level: int = 2,
    ) -> None:
        final_title = title if title is not None else getattr(self, "custom_title", None)
        final_desc = desc if desc is not None else getattr(self, "custom_desc", None)

        if final_title:
            if hasattr(document, "add_heading_numbered"):
                document.add_heading_numbered(final_title, level=level)
            else:
                document.add_heading(final_title, level=level)

        if final_desc:
            document.add_paragraph(final_desc)

        if self.empty:
            document.add_paragraph("Gösterilecek veri bulunamadı.")
            return

        column_units = getattr(self, "column_units", None)
        column_descriptions = getattr(self, "column_descriptions", None)

        has_units = bool(column_units)
        has_descriptions = bool(column_descriptions)
        extra_rows = int(has_units) + int(has_descriptions)

        raw_doc = getattr(document, "doc", document)

        table = raw_doc.add_table(
            rows=1 + extra_rows + len(self),
            cols=len(self.columns),
        )
        table.style = getattr(self, "_table_style", "Table Grid")

        rows_iter = iter(table.rows)

        # 1. Başlıklar
        header_cells = next(rows_iter).cells
        for col_index, col in enumerate(self.columns):
            cell = header_cells[col_index]
            cell.text = str(col)
            if cell.paragraphs[0].runs:
                cell.paragraphs[0].runs[0].bold = True

        # 2. Birimler
        if has_units:
            unit_cells = next(rows_iter).cells
            for col_index, col in enumerate(self.columns):
                val = column_units.get(col, "") if isinstance(column_units, dict) else ""
                unit_cells[col_index].text = str(val)

        # 3. Açıklamalar
        if has_descriptions:
            desc_cells = next(rows_iter).cells
            for col_index, col in enumerate(self.columns):
                val = column_descriptions.get(col, "") if isinstance(column_descriptions, dict) else ""
                desc_cells[col_index].text = str(val)

        # Veri Satırları
        for _, data_row in self.iterrows():
            row_cells = next(rows_iter).cells
            values = self._format_row(data_row) if hasattr(self, "_format_row") else data_row.values
            for col_index, value in enumerate(values):
                row_cells[col_index].text = str(value)

        # Görseller
        graphics = getattr(self, "graphics", [])
        for graphic in graphics:
            g_title = graphic.get("title")
            g_desc = graphic.get("description")

            if g_title:
                p = raw_doc.add_paragraph()
                p.add_run(g_title).bold = True
            if g_desc:
                raw_doc.add_paragraph(g_desc)

            img_stream = graphic.get("image") or graphic.get("data")
            if img_stream:
                if hasattr(img_stream, "seek"):
                    img_stream.seek(0)
                width_cm = graphic.get("width_cm", 15.0)
                if hasattr(document, "add_image"):
                    document.add_image(img_stream, width_cm=width_cm)
                else:
                    raw_doc.add_picture(img_stream, width=int(width_cm * 360000))

        raw_doc.add_paragraph()

    def print(self) -> None:
        if self.custom_title:
            print(f"\n{self.custom_title}")
            print("-" * len(self.custom_title))

        if self.custom_desc:
            print(f"{self.custom_desc}\n")

        if self.empty:
            print("Veri yok")
            return

        print(" | ".join(str(col) for col in self.columns))

        if self.column_descriptions:
            print(
                " | ".join(
                    self.column_descriptions.get(col, "") for col in self.columns
                )
            )

        if self.column_units:
            print(
                " | ".join(
                    self.column_units.get(col, "") for col in self.columns
                )
            )

        for _, row in self.iterrows():
            print(" | ".join(self._format_row(row)))
