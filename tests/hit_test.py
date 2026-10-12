# ui/hit_test.py
"""ImGui pencerelerinin ekran dikdörtgenlerini takip eder."""
import imgui


class UiHitTest:
    """Her frame çizilen ImGui pencerelerinin dikdörtgenlerini kaydeder.

    Fare bir pencere üzerindeyse router event'i engellenir.
    """

    def __init__(self):
        self._rects = []   # her frame başında sıfırlanır

    def begin_frame(self):
        self._rects.clear()

    def register_window(self, title: str):
        """imgui.begin() başında çağrılır — pencerenin rect'ini kaydeder."""
        try:
            # begin() sonrası pencere konumu/boyutu okunabilir
            x, y = imgui.get_window_position()
            w, h = imgui.get_window_size()
            self._rects.append((x, y, x + w, y + h))
        except Exception:
            pass

    def is_over_ui(self, mouse_x: float, mouse_y: float) -> bool:
        """Fare kayıtlı pencerelerden birinin üzerinde mi?"""
        for x1, y1, x2, y2 in self._rects:
            if x1 <= mouse_x <= x2 and y1 <= mouse_y <= y2:
                return True
        return False