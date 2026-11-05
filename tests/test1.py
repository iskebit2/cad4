import glfw
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from domain.polygon import Polygon
from data.enums import PolygonType
from tools.s2k.loader import S2KLoader
from ui.load_manager_panel import LoadManagerPanel

# === Proje yükle ===
p = S2KLoader(r"tests/simple_steel3.s2k").load()
s = p.scene

#print(f"Node: {len(s.nodes)}, Frame: {len(s.frames)}")
#print(f"Node ID'ler: {sorted(s.nodes.keys())[:20]}")
#print(p.load_patterns)

def make_polygon(scene, node_ids, label):
    """Node ID listesinden polygon üret."""
    nodes = [scene.nodes[nid] for nid in node_ids if nid in scene.nodes]
    if len(nodes) < 3:
        #print(f"⚠ {label}: yetersiz node ({len(nodes)})")
        return None
    poly = Polygon(nodes, label=label, poly_type=PolygonType.GENERIC)
    scene.add_polygon(poly)
    #print(f"✓ {label}: {len(nodes)} node, id={poly.unique_id}")
    return poly


# === Polygon üret ===
polygons = []
if all(nid in s.nodes for nid in [2, 3, 8, 4]):
    p1 = make_polygon(s, [2, 3, 8, 4], "Poly_A")
    if p1:
        polygons.append(p1)

if all(nid in s.nodes for nid in [4, 8, 9, 5]):
    p2 = make_polygon(s, [4, 8, 9, 5], "Poly_B")
    if p2:
        polygons.append(p2)

#print(f"Toplam polygon: {len(polygons)}")


def main():
    glfw.init()
    window = glfw.create_window(1000, 900, "Load Manager Test", None, None)
    glfw.make_context_current(window)
    imgui.create_context()
    impl = GlfwRenderer(window)

    frames = list(s.frames.values())[:3]
    nodes = list(s.nodes.values())[:2]

    panel = LoadManagerPanel()
    panel.set_context({
        "project": p,
        "scene": s,
        "patterns": list(p.load_patterns.keys()),
        "selection_polygons": polygons,
        "selection_frames": frames,
        "selection_nodes": nodes,
        "renderer": None,
    })
    panel.visible = True

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()
        imgui.new_frame()
        panel.draw()
        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()