import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from shapely.geometry import Polygon, LineString, Point

def plot_grid_geometry(grid_data):
    """
    Hesaplanmış geometri verilerini görselleştirir.
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    boundary_coords = grid_data['boundary_coords']
    z_levels = grid_data['z_levels']
    lines = grid_data['lines']

    # Poligon sınırlarını her Z seviyesinde kesikli gri çizgi olarak çizelim
    for z in z_levels:
        x_h = [p[0] for p in boundary_coords]
        y_h = [p[1] for p in boundary_coords]
        ax.plot(x_h, y_h, [z]*len(x_h), color='gray', linestyle='--', linewidth=2.5)

    # Tüm çizgileri, uzantıları ve etiket balonlarını çizelim
    for line in lines:
        xs, ys, zs = line['start']
        xe, ye, ze = line['end']
        x_ext, y_ext, z_ext = line['extension_end']

        # Ana kesilmiş çizgi
        ax.plot([xs, xe], [ys, ye], [zs, ze], color=line['color'], linestyle=line['style'])

        # Ortogonal kılavuz çizgisi ve bubble uzantısı
        ax.plot([xe, x_ext], [ye, y_ext], [ze, z_ext], color='black', linestyle='-', linewidth=1)

        # İçi boş dairesel bubble çizimi
        if line['bubble_pos']:
            bx, by, bz = line['bubble_pos']
            ax.scatter(bx, by, bz, facecolors='none', edgecolors='black', s=350, linewidths=1.5, zorder=5)
            ax.text(bx, by, bz, line['label'], color='black',
                    ha='center', va='center', fontsize=7, weight='bold', zorder=6)

    ax.set_xlabel('X Ekseni')
    ax.set_ylabel('Y Ekseni')
    ax.set_zlabel('Z Ekseni')
    ax.set_title('Tüm Uzantıları ve Balonları Ortogonal Hizalanmış 3D Grid Tasarımı')

    all_pts = np.array(boundary_coords)
    ax.set_xlim(all_pts[:, 0].min() - 2, all_pts[:, 0].max() + 2)
    ax.set_ylim(all_pts[:, 1].min() - 2, all_pts[:, 1].max() + 2)
    ax.set_zlim(min(z_levels) - 1, max(z_levels) + 1)

    plt.show()

def generate_grid_geometry(x_coords, y_coords, z_coords, x_labels=None, y_labels=None, eğik_akslar=None, boundary_coords=[], bubble_offset=0.6):
    """
    3D grid sisteminin geometrik hesaplamalarını yapar.
    Tüm etiket balonları ve leader kılavuz çizgileri her zaman kesinlikle ortogonaldir.
    """
    boundary_polygon = Polygon(boundary_coords)

    z_sorted = sorted(list(set(z_coords)))
    x_sorted = sorted(list(set(x_coords)))
    y_sorted = sorted(list(set(y_coords)))

    all_pts = np.array(boundary_coords)
    min_x, max_x = all_pts[:, 0].min(), all_pts[:, 0].max()
    min_y, max_y = all_pts[:, 1].min(), all_pts[:, 1].max()

    # Sınır poligonunun sol-alt köşesini dinamik referans olarak bulalım
    left_bottom_idx = np.argmin(all_pts[:, 0] + all_pts[:, 1])
    ref_x, ref_y = boundary_coords[left_bottom_idx]

    lines_data = []
    z_points_set = set()  # Düşey kolonların yerleştirileceği benzersiz (X, Y) koordinatları

    # Sınır poligonundaki tüm köşeleri Z doğrultusunda kolon olarak extrude etmek üzere koordinat listesine ekleyelim
    for pt in boundary_coords:
        z_points_set.add((round(pt[0], 6), round(pt[1], 6)))

    def process_line(p1, p2, z, label, line_color, line_style, axis_type, is_z_direction=False):
        if is_z_direction:
            lines_data.append({
                'start': (p1[0], p1[1], z_sorted[0]),
                'end': (p1[0], p1[1], z_sorted[-1]),
                'extension_end': (p1[0], p1[1], z_sorted[-1]),
                'bubble_pos': None,
                'label': '',
                'color': line_color,
                'style': line_style
            })
            return

        line = LineString([p1, p2])
        intersection = line.intersection(boundary_polygon)

        if not intersection.is_empty:
            sub_lines = []
            if intersection.geom_type == 'LineString':
                sub_lines = [intersection]
            elif intersection.geom_type == 'MultiLineString':
                sub_lines = list(intersection.geoms)

            for idx, item in enumerate(sub_lines):
                coords = list(item.coords)
                start_pt, end_pt = coords[0], coords[-1]
                xs, ys = start_pt[0], start_pt[1]
                xe, ye = end_pt[0], end_pt[1]

                # Sınır çizgileri ile aksların kesişim noktalarını (uç noktaları) Z sütun listesine ekle
                z_points_set.add((round(xs, 6), round(ys, 6)))
                z_points_set.add((round(xe, 6), round(ye, 6)))

                # Lider çizgileri ve uzantıları istisnasız daima ortogonal (X veya Y yönünde) hizalanır
                if axis_type == 'X':
                    x_ext = max_x + bubble_offset
                    y_ext = ye
                elif axis_type == 'Y':
                    x_ext = xe
                    y_ext = max_y + bubble_offset
                else:
                    if abs(xe - max_x) < abs(ye - max_y):
                        x_ext = max_x + bubble_offset
                        y_ext = ye
                    else:
                        x_ext = xe
                        y_ext = max_y + bubble_offset

                show_bubble = (z == z_sorted[0])
                item_label = f"{label}_{idx+1}" if len(sub_lines) > 1 else label

                lines_data.append({
                    'start': (xs, ys, z),
                    'end': (xe, ye, z),
                    'extension_end': (x_ext, y_ext, z),
                    'bubble_pos': (x_ext, y_ext, z) if show_bubble else None,
                    'label': item_label if show_bubble else '',
                    'color': line_color,
                    'style': line_style
                })

    # 1. Ortogonal Grid Hatları (Tüm sınır içi çizgiler '-.' formatında, X: kırmızı, Y: yeşil)
    for y in y_sorted:
        custom_label = y_labels.get(y, f"Y:{y}") if y_labels else f"Y:{y}"
        for z in z_sorted:
            process_line((-100, y), (100, y), z, custom_label, 'red', '-.', 'X')

    for x in x_sorted:
        custom_label = x_labels.get(x, f"X:{x}") if x_labels else f"X:{x}"
        for z in z_sorted:
            process_line((x, -100), (x, 100), z, custom_label, 'green', '-.', 'Y')

    # 2. Eğik Akslar (Eğik akslar için de kırmızı/yeşil/cyan gruplaması dışında genel aks rengi veya isteğe göre magenta/purple atanabilir, varsayılan kırmızı atıyoruz)
    if eğik_akslar:
        for ad, p1, p2 in eğik_akslar:
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = np.sqrt(dx**2 + dy**2)
            if length > 0:
                ux, uy = dx / length, dy / length
                p1_large = (p1[0] - ux * 100, p1[1] - uy * 100)
                p2_large = (p2[0] + ux * 100, p2[1] + uy * 100)
            else:
                p1_large, p2_large = p1, p2
            for z in z_sorted:
                process_line(p1_large, p2_large, z, ad, 'red', '-.', 'SKEW')

    # 3. Klasik Grid İç Kesişim Noktalarını da ekleyelim
    for x in x_sorted:
        for y in y_sorted:
            if boundary_polygon.contains(Point(x, y)) or boundary_polygon.touches(Point(x, y)):
                z_points_set.add((round(x, 6), round(y, 6)))

    # 4. Tüm Benzersiz Kesişim, Köşe ve Sınır Teğet Noktalarında Z Sütunları Çizilir (Z'ler: cyan)
    for pt in z_points_set:
        process_line((pt[0], pt[1]), (pt[0], pt[1]), None, '', 'cyan', '-.', 'Z', is_z_direction=True)

    # Z etiketlerini, sınır poligonunun dinamik sol-alt referans köşesine dayandırarak çiziyoruz
    for z in z_sorted:
        lines_data.append({
            'start': (ref_x, ref_y, z),
            'end': (ref_x, ref_y, z),
            'extension_end': (ref_x - bubble_offset, ref_y, z),
            'bubble_pos': (ref_x - bubble_offset, ref_y, z),
            'label': f"Z:{z}",
            'color': 'cyan',
            'style': '-.'
        })

    return {
        'boundary_coords': boundary_coords,
        'z_levels': z_sorted,
        'lines': lines_data
    }

# --- Test Verileri ve Çalıştırma ---
x_giriş = [0, 2, 4]
y_giriş = [1, 2, 3, 5]
z_giriş = [0, 2]

custom_x_labels = {0: "A", 2: "B", 4: "C"}
custom_y_labels = {1: "1", 2: "2", 3: "3", 5: "4"}

eğik_akslar = [
    ("S1", (-0.5, 0.5), (3.8, 4.8))
]

geometri_verisi = generate_grid_geometry(
    x_coords=x_giriş,
    y_coords=y_giriş,
    z_coords=z_giriş,
    x_labels=custom_x_labels,
    y_labels=custom_y_labels,
    eğik_akslar=eğik_akslar,
    boundary_coords = [
            (-1.0, 0.2),
            (5.2, 0.5),
            (3.5, 5.5),
            (-0.8, 5.0),
            (-1.0, 0.2)
        ],
    bubble_offset=1.0
)

plot_grid_geometry(geometri_verisi)