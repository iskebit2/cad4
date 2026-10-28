"""
Standalone demo — `python -m inspector.demo`

Küçük bir sahne yaratır, Inspector'ı açar. Scene'in gerçek sınıfları
kullanılabilir; burada sadece `scene.iter_elements(type=...)` çağrısı
varsayılıyor.
"""

import sys


def _make_demo_scene():
    """
    Gerçek domain'inden sahne üret. Aşağıdaki import'lar senin projene
    göre uyarlanacak.
    """
    try:
        from domain.project import Project
        project = Project()
        return project.scene
    except Exception as e:
        print(f"[demo] domain yüklenemedi, boş sahne: {e}")
        return None


def main():
    scene = _make_demo_scene()

    import glfw
    from imgui_bundle import imgui
    from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

    from inspector.window import InspectorWindow

    if not glfw.init():
        print("glfw.init başarısız")
        sys.exit(1)

    window = glfw.create_window(1200, 800, "Inspector Demo", None, None)
    if not window:
        glfw.terminate()
        sys.exit(1)

    glfw.make_context_current(window)
    imgui.create_context()
    impl = GlfwRenderer(window)

    inspector = InspectorWindow(scene=scene, standalone=True)
    inspector.open()

    # Sahne varsa tüm element'leri seçilebilir yap
    if scene is not None:
        first = None
        for t in ("Node", "Frame", "Area", "Polygon"):
            if hasattr(scene, "iter_elements"):
                items = list(scene.iter_elements(type=t))
                if items:
                    first = items[0]
                    break
        if first is not None:
            inspector.set_selection([first])

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()

        imgui.new_frame()
        inspector.draw()
        imgui.render()
        impl.render(imgui.get_draw_data())

        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()


if __name__ == "__main__":
    main()