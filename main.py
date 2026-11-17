# main.py
from __future__ import annotations

import time
import traceback

from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

from app.cad_app import CadApp
from app.cad_window import CadWindow
from logging_config import CadLogger
from ui.ui_host import UIHost

logger = CadLogger.get("main")


def main() -> int:
    CadLogger._configure_root_once()

    window = CadWindow(width=1280, height=800, title="CAD4")
    window.create()

    app = CadApp(window.fb_width, window.fb_height)
    app.init_engine()
    app.on_quit = window.request_close

    ui_host = UIHost(app)
    ui_host.init_context()
    imgui_backend = GlfwRenderer(window.window, attach_callbacks=False)
    app.attach_ui(ui_host)

    io = imgui.get_io()
    app.engine.input.set_capture_callbacks(
        mouse_fn=lambda: bool(io.want_capture_mouse),
        keyboard_fn=lambda: bool(io.want_text_input),
    )

    window.on_key = lambda k, s, a, m: (
        imgui_backend.keyboard_callback(window.window, k, s, a, m),
        ui_host.notify_key(k, a, m),
        app.engine.input.on_key(k, a, m),
    )
    window.on_char = lambda cp: imgui_backend.char_callback(window.window, cp)
    window.on_mouse_move = lambda x, y: (
        imgui_backend.mouse_callback(window.window, x, y),
        app.engine.input.on_mouse_move(x, y),
    )
    window.on_mouse_button = lambda b, a, m: (
        imgui_backend.mouse_button_callback(window.window, b, a, m),
        app.engine.input.on_mouse_button(b, a, m),
    )
    window.on_scroll = lambda xo, yo: (
        imgui_backend.scroll_callback(window.window, xo, yo),
        app.engine.input.on_scroll(yo),
    )
    window.on_resize = lambda w, h: app.resize(w, h)

    target_dt = 1.0 / 60.0
    last_time = time.time()

    try:
        while not window.should_close():
            now = time.time()
            dt = now - last_time
            last_time = now

            window.poll_events()
            app.tick(dt)

            glViewport(0, 0, window.fb_width, window.fb_height)
            glClearColor(0.08, 0.10, 0.14, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            if app.viewport_manager:
                app.viewport_manager.render_all()

            imgui_backend.process_inputs()
            imgui.new_frame()
            ui_host.draw_frame(dt)
            imgui.render()
            glViewport(0, 0, window.fb_width, window.fb_height)
            imgui_backend.render(imgui.get_draw_data())

            window.swap_buffers()

            elapsed = time.time() - now
            if elapsed < target_dt:
                time.sleep(target_dt - elapsed)
        return 0
    except Exception:
        logger.critical("Kritik hata:\n%s", traceback.format_exc())
        return 1
    finally:
        imgui_backend.shutdown()
        app.shutdown()
        window.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())