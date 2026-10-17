# ui/widgets/polygon_info.py
import imgui
import math


class PolygonInfoWidget:

    @staticmethod
    def draw(poly, plane):
        """Poly bilgi kutusu."""
        imgui.text_colored("POLY BİLGİSİ", 0.8, 0.85, 0.95, 1.0)
        imgui.separator()

        # Tip
        poly_type = getattr(poly, "poly_type", None)
        type_str = getattr(poly_type, "name", str(poly_type))
        imgui.text(f"Tip:")
        imgui.same_line(140)
        imgui.text_colored(type_str, 0.9, 0.8, 0.5, 1.0)

        # ID
        imgui.text("Unique ID:")
        imgui.same_line(140)
        imgui.text(str(getattr(poly, "unique_id", "?")))

        # Label
        imgui.text("Label:")
        imgui.same_line(140)
        imgui.text(str(getattr(poly, "label", "")))

        # Node sayısı
        n_nodes = len(getattr(poly, "nodes", []))
        imgui.text("Node sayısı:")
        imgui.same_line(140)
        imgui.text(str(n_nodes))

        # Alan
        if plane and n_nodes >= 3:
            area = PolygonInfoWidget._compute_area(poly, plane)
            imgui.text("Alan:")
            imgui.same_line(140)
            imgui.text_colored(f"{area:.3f} m²", 0.6, 0.85, 0.6, 1.0)

        # Çevre
        if plane and n_nodes >= 3:
            perim = PolygonInfoWidget._compute_perimeter(poly, plane)
            imgui.text("Çevre:")
            imgui.same_line(140)
            imgui.text(f"{perim:.3f} m")

        # Normal
        if plane:
            n = plane.normal
            imgui.text("Normal:")
            imgui.same_line(140)
            imgui.text(f"({n[0]:+.3f}, {n[1]:+.3f}, {n[2]:+.3f})")

        # Assoc frame sayısı
        n_assoc = len(getattr(poly, "associated_frame_ids", []))
        imgui.text("Assoc frame:")
        imgui.same_line(140)
        col = (0.6, 0.85, 0.6, 1.0) if n_assoc > 0 else (0.9, 0.4, 0.4, 1.0)
        imgui.text_colored(str(n_assoc), *col)

    # ------------------------------------------------------------------
    @staticmethod
    def _compute_area(poly, plane):
        """Poly'nin 2D izdüşümünden alan hesapla (mm² → m²)."""
        poly_2d = plane.polygon_to_2d(poly)
        area_mm2 = 0.0
        n = len(poly_2d)
        for i in range(n):
            u1, v1 = poly_2d[i]
            u2, v2 = poly_2d[(i + 1) % n]
            area_mm2 += (u1 * v2 - u2 * v1)
        area_mm2 = abs(area_mm2) * 0.5
        return area_mm2 * 1e-6   # mm² → m²

    @staticmethod
    def _compute_perimeter(poly, plane):
        """Çevre (mm → m)."""
        poly_2d = plane.polygon_to_2d(poly)
        perim = 0.0
        n = len(poly_2d)
        for i in range(n):
            u1, v1 = poly_2d[i]
            u2, v2 = poly_2d[(i + 1) % n]
            perim += math.hypot(u2 - u1, v2 - v1)
        return perim * 1e-3   # mm → m