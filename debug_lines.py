from kivy.uix.widget import Widget
from kivy.graphics import Color, Line


def debug_layout(widget, depth=0):
    # Her widget için kendi sınırını çiz
    with widget.canvas.after:
        Color(0.2, 0.2, 0.2, 1.0)
        widget._debug_line = Line(
            rectangle=(*widget.pos, *widget.size),
            width=1
        )

    # Widget hareket ederse çizgi de güncellensin
    def update_line(instance, value):
        if hasattr(instance, "_debug_line"):
            instance._debug_line.rectangle = (
                *instance.pos,
                *instance.size
            )

    widget.bind(pos=update_line, size=update_line)

    for child in widget.children:
        debug_layout(child, depth + 1)