
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

ICON_DIR = Path(__file__).resolve().parent / "icons"
ICON_SIZE = 48
COLUMNS = 7

BG = "#202124"
CARD = "#303134"
BORDER = "#45464A"
FG = "#E8EAED"

root = tk.Tk()
root.title("CAD4 - Icon Browser")
root.geometry("1000x800")
root.configure(bg=BG)

style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame", background=BG)
style.configure("TLabel", background=CARD, foreground=FG)
style.configure(
    "TScrollbar",
    background=CARD,
    troughcolor=BG,
    bordercolor=BG,
    arrowcolor=FG,
)

container = ttk.Frame(root)
container.pack(fill="both", expand=True, padx=8, pady=8)

canvas = tk.Canvas(
    container,
    bg=BG,
    highlightthickness=0,
)
scrollbar = ttk.Scrollbar(
    container,
    orient="vertical",
    command=canvas.yview,
)
scroll_frame = ttk.Frame(canvas)

window_id = canvas.create_window(
    (0, 0),
    window=scroll_frame,
    anchor="nw",
)

canvas.configure(yscrollcommand=scrollbar.set)

scroll_frame.bind(
    "<Configure>",
    lambda event: canvas.configure(
        scrollregion=canvas.bbox("all")
    ),
)

canvas.bind(
    "<Configure>",
    lambda event: canvas.itemconfigure(
        window_id, width=event.width
    ),
)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

image_refs = []

files = sorted(
    p for p in ICON_DIR.rglob("*")
    if p.is_file() and p.suffix.lower() == ".png"
)

for i, path in enumerate(files):
    try:
        with Image.open(path) as source:
            image = source.convert("RGBA")
            image.thumbnail((ICON_SIZE, ICON_SIZE))
            photo = ImageTk.PhotoImage(image)

        image_refs.append(photo)

        frame = tk.Frame(
            scroll_frame,
            bg=CARD,
            padx=6,
            pady=6,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        frame.grid(
            row=i // COLUMNS,
            column=i % COLUMNS,
            padx=4,
            pady=4,
            sticky="nsew",
        )

        tk.Label(
            frame,
            image=photo,
            bg=CARD,
        ).pack(pady=(0, 5))

        name = path.relative_to(ICON_DIR).as_posix()

        tk.Label(
            frame,
            text=name,
            bg=CARD,
            fg=FG,
            wraplength=115,
            justify="center",
        ).pack()

    except Exception as exc:
        pass(f"Okunamadı: {path} - {exc}")

for col in range(COLUMNS):
    scroll_frame.grid_columnconfigure(col, weight=1)

def on_mousewheel(event):
    canvas.yview_scroll(
        -1 if event.delta > 0 else 1,
        "units",
    )

canvas.bind_all("<MouseWheel>", on_mousewheel)

pass(f"ICON_DIR: {ICON_DIR}")
pass(f"Bulunan PNG sayısı: {len(files)}")

if not files:
    tk.Label(
        root,
        text=f"PNG bulunamadı:\n{ICON_DIR}",
        bg=BG,
        fg="#FF6B6B",
    ).pack(pady=20)

root.mainloop()
