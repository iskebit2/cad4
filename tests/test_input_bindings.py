# tests/test_input_bindings.py
import glfw
from app.input_bindings import build_bindings
from app.commands import project_commands as PC


class FakeQueue:
    def __init__(self):
        self.items = []
    def put(self, cmd):
        self.items.append(cmd)


def test_key_f5_zooms_extents():
    q = FakeQueue()
    b = build_bindings(q)
    b[glfw.KEY_F5]()
    assert isinstance(q.items[0], PC.ZoomExtents)


def test_ctrl_z_undo():
    q = FakeQueue()
    b = build_bindings(q)
    b[(glfw.KEY_Z, glfw.MOD_CONTROL)]()
    assert isinstance(q.items[0], PC.Undo)


def test_no_app_reference():
    """build_bindings yalnızca command_queue alır."""
    import inspect
    sig = inspect.signature(build_bindings)
    assert list(sig.parameters) == ["command_queue"]