# tools/input_smoke_test.py
"""
InputManager + bindings + handler dispatch'in doğruluğunu GLFW penceresi olmadan test eder.
Kullanım:
    python -m tools.input_smoke_test
"""
import glfw
from core.input_manager import InputManager, LEFT, MIDDLE, RIGHT


class MockHandler:
    def __init__(self, name, active=True, swallow=True):
        self.name = name
        self.is_active = active
        self.swallow = swallow
        self.events = []

    def handle_click(self, x, y, button):
        self.events.append(("click", button, x, y))
        return self.swallow

    def handle_release(self, x, y, button):
        self.events.append(("release", button, x, y))
        return self.swallow

    def handle_move(self, x, y, dx, dy):
        self.events.append(("move", x, y, dx, dy))
        return self.swallow

    def handle_key(self, key, mods):
        self.events.append(("key", key, mods))
        return self.swallow

    def handle_scroll(self, delta):
        self.events.append(("scroll", delta))
        return self.swallow


def _test_dispatch_order():
    im = InputManager()
    h1 = MockHandler("h1")
    h2 = MockHandler("h2")
    im.register(h1)
    im.register(h2)

    im.on_mouse_button(LEFT, glfw.PRESS, 0)
    assert h1.events[0][0] == "click"
    assert h2.events == []  # h1 yuttu, h2 çağrılmadı
    print("✓ dispatch order (swallow)")


def _test_dispatch_skip_inactive():
    im = InputManager()
    h1 = MockHandler("h1", active=False)
    h2 = MockHandler("h2")
    im.register(h1)
    im.register(h2)

    im.on_mouse_button(LEFT, glfw.PRESS, 0)
    assert h1.events == []
    assert h2.events[0][0] == "click"
    print("✓ dispatch skip inactive")


def _test_double_click():
    im = InputManager()
    h = MockHandler("h")
    im.register(h)
    im.on_mouse_button(LEFT, glfw.PRESS, 0)
    im.on_mouse_button(LEFT, glfw.RELEASE, 0)
    im.on_mouse_button(LEFT, glfw.PRESS, 0)  # aynı frame, double
    # İlk tıklama → 1 click; ikinci tıklama double → click atlanır
    assert len(h.events) == 2  # click + release (double click release'i de engellemiyor)
    print("✓ double click")


def _test_binding():
    im = InputManager()
    called = []
    im.bind(glfw.KEY_F2, 0, lambda: called.append("F2"))
    im.on_key(glfw.KEY_F2, glfw.PRESS, 0)
    assert called == ["F2"]
    print("✓ key binding")


def _test_fallback():
    im = InputManager()
    fb_called = []

    class Fallback:
        def handle_click(self, x, y, b):
            fb_called.append("click")
            return True
        def handle_release(self, *a): return False
        def handle_move(self, *a): return False
        def handle_key(self, *a): return False
        def handle_scroll(self, *a): return False

    im.set_fallback(Fallback())
    im.on_mouse_button(LEFT, glfw.PRESS, 0)
    assert fb_called == ["click"]
    print("✓ fallback")


def _test_state():
    im = InputManager()
    im.on_mouse_move(100, 200)
    assert im.state.mouse_pos.x == 100
    assert im.state.mouse_pos.y == 200
    im.on_mouse_move(150, 250)
    assert im.state.mouse_delta.x == 50
    assert im.state.mouse_delta.y == 50
    print("✓ state update")


def _test_modifiers():
    im = InputManager()
    im.on_key(glfw.KEY_LEFT_SHIFT, glfw.PRESS, glfw.MOD_SHIFT)
    assert im.is_shift()
    assert not im.is_ctrl()
    print("✓ modifiers")


def main():
    _test_dispatch_order()
    _test_dispatch_skip_inactive()
    _test_double_click()
    _test_binding()
    _test_fallback()
    _test_state()
    _test_modifiers()
    print("\nTüm birim testleri geçti ✓")


if __name__ == "__main__":
    main()