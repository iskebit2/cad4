from pathlib import Path

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout


class IconButton(ButtonBehavior, Image):

    def __init__(self, icon_path, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(48), dp(48)))
        kwargs["source"] = str(icon_path)

        super().__init__(**kwargs)


class IconGallery(App):

    def build(self):

        root = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(10),
        )

        root.add_widget(
            Label(
                text="ICON GALLERY",
                size_hint_y=None,
                height=dp(40),
                font_size=20,
            )
        )

        scroll = ScrollView()

        grid = GridLayout(
            cols=6,
            spacing=dp(15),
            padding=dp(10),
            size_hint_y=None,
        )

        grid.bind(
            minimum_height=grid.setter("height")
        )

        icon_dir = Path("assets/icons")

        files = sorted(
            icon_dir.glob("*.png"),
            key=lambda p: p.stem.lower(),
        )

        for path in files:

            item = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(90),
                spacing=dp(4),
            )

            icon = IconButton(path)

            icon.bind(
                on_release=lambda btn, p=path:
                    print("SEÇİLDİ:", p)
            )

            item.add_widget(icon)

            item.add_widget(
                Label(
                    text=path.stem,
                    font_size=11,
                    text_size=(dp(90), None),
                    halign="center",
                    valign="middle",
                    shorten=True,
                    shorten_from="right",
                )
            )

            grid.add_widget(item)

        scroll.add_widget(grid)
        root.add_widget(scroll)

        print(f"{len(files)} ikon bulundu.")

        return root


IconGallery().run()