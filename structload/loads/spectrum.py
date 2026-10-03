#spectrum.py

"""
TBDY 2018 Deprem Spektrumu Hesaplamaları
"""
from io import BytesIO
import numpy as np
from structload.utils.report_dataframe import ReportDataFrame



class Spectrum:
    TL = 6.0
    DEFAULT_CT = 0.10

    def __init__(self, data):
        self.config = data

        self.T1 = 0.0

        self.Sae_DD2 = None
        self.Sae_DD3 = None
        self.lambda_val = None
        self.table_parameters = None
        self.table_spectrum = None

        self.dd2 = data["dd2"]
        self.dd3 = data["dd3"]
        self.zemin_sinifi = data["zemin_sinifi"]
        self.Hn = data.get("Hn", 1)

        self._calculate_period_params()

    def _calculate_period_params(self):
        
        self.TA_DD2 = 0.2 * self.dd2["Sd1"] / self.dd2["Sds"]
        self.TB_DD2 = self.dd2["Sd1"] / self.dd2["Sds"]

        self.TA_DD3 = 0.2 * self.dd3["Sd1"] / self.dd3["Sds"]
        self.TB_DD3 = self.dd3["Sd1"] / self.dd3["Sds"]

        self.T_values = np.unique(np.concatenate([
            np.linspace(0.0001, 1.5, 31),
            np.linspace(1.6, 4.0, 13),
            [
                self.TA_DD2,
                self.TB_DD2,
                self.TA_DD3,
                self.TB_DD3
            ]
        ]))

    @staticmethod
    def sae(
        T: float,
        SDS: float,
        SD1: float,
        TA: float,
        TB: float,
        TL: float = 6.0
    ) -> float:

        if T <= TA:
            return (0.4 + 0.6 * T / TA) * SDS

        if T <= TB:
            return SDS

        if T <= TL:
            return SD1 / T

        return SD1 * TL / T**2

    def run(self, T1: float = 0) -> None:
        self.calculate_tpA()
        if T1==0:
            self.T1 = self.TpA
        else:
            self.T1 = float(T1)

        self._create_spectrum()
        self._calculate_lambda()
        self._create_tables()

    def calculate_tpA(self):
        ct_map = {"steel_frame": 0.08, "concrete_frame": 0.1, "other": 0.07}
        self.Ct = ct_map.get(self.config.get("structure_type"), 0.07)
        self.TpA = self.Ct * (float(self.config["Hn"]) ** 0.75)
        self.T_max = 1.4 * self.TpA

    def _create_spectrum(self) -> None:
        T = self.T_values

        self.Sae_DD2 = np.where(
            T <= self.TA_DD2,
            (0.4 + 0.6 * T / self.TA_DD2) * self.dd2["Sds"],
            np.where(
                T <= self.TB_DD2,
                self.dd2["Sds"],
                np.where(
                    T <= self.TL,
                    self.dd2["Sd1"] / T,
                    self.dd2["Sd1"] * self.TL / T**2
                )
            )
        )

        self.Sae_DD3 = np.where(
            T <= self.TA_DD3,
            (0.4 + 0.6 * T / self.TA_DD3) * self.dd3["Sds"],
            np.where(
                T <= self.TB_DD3,
                self.dd3["Sds"],
                np.where(
                    T <= self.TL,
                    self.dd3["Sd1"] / T,
                    self.dd3["Sd1"] * self.TL / T**2
                )
            )
        )

    def _calculate_lambda(self):
        if self.T1 <= 0:
            self.lambda_val = None
            return None

        sae_dd2_t1 = self.sae(
            self.T1,
            self.dd2["Sds"],
            self.dd2["Sd1"],
            self.TA_DD2,
            self.TB_DD2,
            self.TL
        )

        sae_dd3_t1 = self.sae(
            self.T1,
            self.dd3["Sds"],
            self.dd3["Sd1"],
            self.TA_DD3,
            self.TB_DD3,
            self.TL
        )

        self.lambda_val = (
            sae_dd3_t1 / sae_dd2_t1
            if sae_dd2_t1 != 0
            else None
        )

        return self.lambda_val

    def _create_tables(self) -> None:
        dd2_data = [
            {
                "Parametre": k,
                "DD-2": v,
                "DD-3": self.dd3[k]
            }
            for k, v in self.dd2.items()
            if k in self.dd3
        ]

        aciklama = (
            f"--- Deprem Parametreleri ---\n"
            f"DD2: Sds={self.config['dd2']['Sds']:.3f}, Sd1={self.config['dd2']['Sd1']:.3f}, "
            f"Tₚₐ={self.TA_DD2:.3f}s, Tₚᵦ={self.TB_DD2:.3f}s\n"
            f"DD3: Sds={self.config['dd3']['Sds']:.3f}, Sd1={self.config['dd3']['Sd1']:.3f}, "
            f"Tₚₐ={self.TA_DD3:.3f}s, Tₚᵦ={self.TB_DD3:.3f}s\n\n"
            f"--- Periyot Analizi (Denk. 4.27) ---\n"
            f"Hₙ={self.config['Hn']:.2f}m, Cₜ={self.Ct:.3f}\n"
            f"Tₚₐ (Ampirik)={self.TpA:.3f}s, Tₘₐₓ (1.4Tₚₐ)={self.T_max:.3f}s\n"
            f"Hesapta Kullanılan T₁={self.T1:.3f}s\n"
            f"λ (Sae_DD3/Sae_DD2)={self.lambda_val:.3f}"
        )
        

        self.table_parameters = ReportDataFrame(
            dd2_data,
            custom_title="Deprem Parametreleri",
            custom_desc= aciklama
        )

        

        sample_indices = np.linspace(
            0,
            len(self.T_values) - 1,
            20,
            dtype=int
        )

        spectrum_data = {
            "T": self.T_values[sample_indices],
            "Sae_DD2": self.Sae_DD2[sample_indices],
            "Sae_DD3": self.Sae_DD3[sample_indices]
        }

        self.table_spectrum = ReportDataFrame(
            spectrum_data,
            custom_title="Spektrum Değerleri",
            custom_desc="Seçili periyotlardaki spektral ivme değerleri",
            graphics=[{
            "image": self.spectrum_plot(),
            "title": "Tepki Spectrumu",
            "description": "DD2 ve DD3 aynı grafik üzerinde"
        }],
            column_descriptions={
                "T": "Periyod",
                "Sae_DD2": "DD2 spektrum katsayısı",
                "Sae_DD3": "DD3 spektrum katsayısı",
            },
            column_units={
                "T": "s",
                "Sae_DD2": "g",
                "Sae_DD3": "g",
            },

            column_formats={
                "T": ".3f",
                "Sae_DD2": ".3f",
                "Sae_DD3": ".3f",
            },
        )

    def spectrum_plot(self, save: bool = False, filename: str = "deprem_spektrumlari.png"):
        if self.Sae_DD2 is None or self.Sae_DD3 is None:
            raise ValueError("Önce run() çağrılmalıdır")

        from PIL import Image, ImageDraw, ImageFont

        width, height = 1200, 600

        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        left, right = 90, width - 40
        top, bottom = 60, height - 70

        plot_width = right - left
        plot_height = bottom - top

        y_max = max(
            float(np.max(self.Sae_DD2)),
            float(np.max(self.Sae_DD3))
        ) * 1.10

        def x(value):
            return left + value / 4.0 * plot_width

        def y(value):
            return bottom - value / y_max * plot_height

        colors = {
            "dd2": (31, 119, 180),
            "dd3": (44, 160, 44),
            "t1": (214, 39, 40),
            "grid": (210, 210, 210),
            "minor": (235, 235, 235),
            "axis": (50, 50, 50),
        }

        for i in range(41):
            value = i / 10
            px = x(value)

            draw.line(
                (px, top, px, bottom),
                fill=colors["grid"] if i % 5 == 0 else colors["minor"]
            )

            if i % 5 == 0:
                draw.text(
                    (px, bottom + 8),
                    f"{value:g}",
                    fill=colors["axis"],
                    font=font,
                    anchor="ma"
                )

        y_step = 0.1
        y_value = 0.0

        while y_value <= y_max:
            py = y(y_value)

            draw.line(
                (left, py, right, py),
                fill=colors["grid"]
            )

            draw.text(
                (left - 8, py),
                f"{y_value:.1f}",
                fill=colors["axis"],
                font=font,
                anchor="rm"
            )

            y_value += y_step

        draw.line(
            (left, top, left, bottom),
            fill=colors["axis"],
            width=2
        )

        draw.line(
            (left, bottom, right, bottom),
            fill=colors["axis"],
            width=2
        )

        def draw_curve(values, color):
            points = [
                (x(float(T)), y(float(Sae)))
                for T, Sae in zip(self.T_values, values)
            ]

            draw.line(
                points,
                fill=color,
                width=3
            )

        draw_curve(self.Sae_DD2, colors["dd2"])
        draw_curve(self.Sae_DD3, colors["dd3"])

        def draw_vertical(value, color, style):
            if value <= 0 or value > 4:
                return

            px = x(value)

            if style == "dashed":
                dash, gap = 10, 6
                position = top

                while position < bottom:
                    draw.line(
                        (px, position, px, min(position + dash, bottom)),
                        fill=color,
                        width=2
                    )
                    position += dash + gap

            elif style == "dotted":
                position = top

                while position < bottom:
                    draw.line(
                        (px, position, px, min(position + 2, bottom)),
                        fill=color
                    )
                    position += 7

            elif style == "dashdot":
                position = top

                while position < bottom:
                    draw.line(
                        (px, position, px, min(position + 10, bottom)),
                        fill=color,
                        width=2
                    )
                    position += 14

                    if position < bottom:
                        draw.line(
                            (px, position, px, min(position + 2, bottom)),
                            fill=color,
                            width=2
                        )
                        position += 8

            
        if self.T1 > 0:
            draw_vertical(self.T1, colors["t1"], "dashed")

        draw_vertical(self.TA_DD2, colors["dd2"], "dotted")
        draw_vertical(self.TB_DD2, colors["dd2"], "dashdot")
        draw_vertical(self.TA_DD3, colors["dd3"], "dotted")
        draw_vertical(self.TB_DD3, colors["dd3"], "dashdot")

        title = (
            f"TBDY 2018 Deprem Spektrum "
            f"(Zemin Sınıfı: {self.zemin_sinifi})"
        )

        

        legend = [
            ("DD-2 Spektrumu", colors["dd2"]),
            ("DD-3 Spektrumu", colors["dd3"]),
            (f"Hakim Periyot T1={self.T1:.3f}s", colors["t1"]),
            (f"DD-2: TA={self.TA_DD2:.3f}s  TB={self.TB_DD2:.3f}s", colors["dd2"]),
            (f"DD-3: TA={self.TA_DD3:.3f}s  TB={self.TB_DD3:.3f}s", colors["dd3"]),
        ]

        legend_x = right - 300
        legend_y = top + 15

        for label, color in legend:
            draw.line(
                (legend_x, legend_y, legend_x + 25, legend_y),
                fill=color,
                width=3
            )

            draw.text(
                (legend_x + 33, legend_y),
                label,
                fill=colors["axis"],
                font=font,
                anchor="lm"
            )

            legend_y += 20

        if save:
            image.save(filename, format="PNG")
            return image

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer