# windcalc/visualize.py
"""
Sadece görselleştirme. Analiz YAPMAZ, zone ÜRETMEZ.
Girdi: ZoneBundle / ZoneResult
"""
from typing import Dict, List, Optional, Any
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.lines import Line2D


# ---------------------------------------------------------------------------
# Renk haritası (mevcut kodunuzdan aynen)
# ---------------------------------------------------------------------------
ZONE_COLORS = {
    "A": 'purple',  "B": 'magenta', "C": 'violet',
    "D": 'yellow',  "E": 'orange',
    "Fl": 'red', "F": 'red', "Fu": 'darkred',
    "G": 'lightcoral', "H": 'indianred',
    "I": 'blue', "J": 'darkblue', "K": 'cornflowerblue',
    "L": 'lightsteelblue', "M": 'steelblue',
    "N": 'green',
    "DEFAULT": 'gray',
}

EDGE_STYLE = {
    # key: (color, linewidth, legend_label)
    "global":  ("red",       4.0, "GLOBAL LEADING"),
    "leading": ("orange",    3.0, "LEADING"),
    "exposed": ("limegreen", 2.0, "EXPOSED"),
    "normal":  ("gray",      0.7, None),
}


def _edge_kind(edge) -> str:
    if getattr(edge, "_global", False):
        return "global"
    if getattr(edge, "leading", False):
        return "leading"
    if getattr(edge, "exposed", False):
        return "exposed"
    return "normal"


# ---------------------------------------------------------------------------
# Tek eksene çizim
# ---------------------------------------------------------------------------
def draw_zone_result(
    ax,
    result,                           # ZoneResult
    title_suffix: str = "",
    show_points: bool = True,
    show_zone_labels: bool = True,
) -> Dict[str, Any]:
    """
    Tek bir ZoneResult'ı verilen 3D eksene çizer.
    Döner: {legend_label: color} sözlüğü.
    """
    legend: Dict[str, Any] = {}
    engine = result.engine
    all_surfaces = result.all_surfaces

    # --- Bina noktaları ---
    if show_points:
        pts = np.array(list(engine.points.values()))
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                   color="blue", s=20, alpha=0.6)

    # --- Zone poligonları ---
    for surf in all_surfaces.values():
        for zone in getattr(surf, "zones", []) or []:
            coords = zone.coords
            if coords is None or len(coords) < 3:
                continue

            color_name = ZONE_COLORS.get(zone.label, ZONE_COLORS["DEFAULT"])
            rgba = list(plt.cm.colors.to_rgb(color_name)) + [0.3]

            poly = Poly3DCollection([coords])
            poly.set_facecolor(rgba)
            poly.set_edgecolor("gray")
            poly.set_linewidth(0.1)
            ax.add_collection3d(poly)

            legend.setdefault(zone.label, color_name)

            if show_zone_labels:
                centroid = np.mean(coords, axis=0)
                ax.text(centroid[0], centroid[1], centroid[2],
                        zone.label, color="black", fontsize=7,
                        ha="center", va="center")

    # --- Kenarlar ---
    for surf in all_surfaces.values():
        for edge in surf.edges.values():
            kind = _edge_kind(edge)
            color, lw, lbl = EDGE_STYLE[kind]

            p1 = np.asarray(edge.p1, dtype=float)
            p2 = np.asarray(edge.p2, dtype=float)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color=color, linewidth=lw, solid_capstyle="round")

            if lbl is not None:
                legend.setdefault(lbl, color)

    # --- Başlık ---
    ax.set_title(f"Bina Yüzey Bölgeleri {title_suffix}", fontsize=10)
    ax.set_axis_off()

    # --- Eşit aspect ---
    _equalize_axes(ax, engine.points)

    return legend


def _equalize_axes(ax, points: Dict[str, tuple]) -> None:
    coords = np.array(list(points.values()))
    if len(coords) == 0:
        return
    mins, maxs = coords.min(axis=0), coords.max(axis=0)
    max_range = (maxs - mins).max() / 2.0
    mids = (mins + maxs) * 0.5
    ax.set_xlim(mids[0] - max_range, mids[0] + max_range)
    ax.set_ylim(mids[1] - max_range, mids[1] + max_range)
    ax.set_zlim(mids[2] - max_range, mids[2] + max_range)


# ---------------------------------------------------------------------------
# 2x2 grid (mevcut davranış)
# ---------------------------------------------------------------------------
def draw_bundle_grid(
    bundle,
    figsize=(12, 10),
    ncols: int = 2,
):
    """
    ZoneBundle'daki tüm sonuçları 2x2 grid üzerine çizer.
    Tek bir ortak legend üretir.
    """
    n = len(bundle.results)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize,
                             subplot_kw={'projection': '3d'})
    axes_flat = np.atleast_1d(axes).flatten()

    all_legend: Dict[str, Any] = {}
    for i, result in enumerate(bundle.results):
        ax = axes_flat[i]
        leg = draw_zone_result(ax, result,
                               title_suffix=f"Rüzgar: {result.w_key}")
        for k, v in leg.items():
            all_legend.setdefault(k, v)

    # Kullanılmayan eksenleri kapat
    for j in range(n, len(axes_flat)):
        axes_flat[j].set_axis_off()

    _attach_figure_legend(fig, all_legend)
    plt.tight_layout(rect=[0, 0, 0.95, 0.95])
    return fig


def _attach_figure_legend(fig, legend_map: Dict[str, Any]) -> None:
    if not legend_map:
        return
    handles = [
        Line2D([0], [0], color=color, marker='o', linestyle='None',
               markersize=8, label=label, alpha=0.3)
        for label, color in sorted(legend_map.items())
    ]
    ncol = max(1, len(handles) // 3)
    fig.legend(handles=handles, loc='upper right',
               bbox_to_anchor=(1.0, 1.0), fontsize=8, ncol=ncol)