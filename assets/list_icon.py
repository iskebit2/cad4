import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from io import BytesIO
import base64
import re

ICON_DIR = Path(__file__).resolve().parent / "icons"
ICON_SIZE = 48
COLUMNS = 7

BG = "#202124"
CARD = "#303134"
BORDER = "#45464A"
FG = "#E8EAED"
SELECTED = "#356A9A"

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

# Seçim ve görsel referansları
selected = set()
image_refs = []
cards = {}

# Üst araç çubuğu
toolbar = tk.Frame(root, bg=BG)
toolbar.pack(fill="x", padx=10, pady=8)

selection_label = tk.Label(
    toolbar,
    text="Seçilen: 0",
    bg=BG,
    fg=FG,
)
selection_label.pack(side="left")

def update_selection():
    selection_label.config(text=f"Seçilen: {len(selected)}")

def toggle_selection(path):
    if path in selected:
        selected.remove(path)
        color = CARD
    else:
        selected.add(path)
        color = SELECTED

    frame = cards[path]
    frame.configure(bg=color, highlightbackground=color)

    for child in frame.winfo_children():
        child.configure(bg=color)

    update_selection()

def make_key(path):
    # Alt klasörleri de anahtara dahil et.
    relative = path.relative_to(ICON_DIR).with_suffix("")
    key = relative.as_posix().lower()
    key = re.sub(r"[^a-z0-9_]+", "_", key)
    return key.strip("_")

def generate_icon_data():
    if not selected:
        messagebox.showwarning("CAD4", "Önce ikon seçmelisin.")
        return

    entries = []

    for path in sorted(selected):
        key = make_key(path)

        with Image.open(path) as source:
            image = source.convert("RGBA")

            buffer = BytesIO()
            image.save(buffer, format="PNG")

            encoded = base64.b64encode(
                buffer.getvalue()
            ).decode("ascii")

        entries.append(f"    {key!r}: {encoded!r},")

    result = "ICON_DATA = {\n"
    result += "\n".join(entries)
    result += "\n}\n"

    root.clipboard_clear()
    root.clipboard_append(result)
    root.update()

    messagebox.showinfo(
        "CAD4",
        f"{len(entries)} ikon Base64'e dönüştürüldü.\n"
        "ICON_DATA panoya kopyalandı.",
    )

def clear_selection():
    for path in list(selected):
        toggle_selection(path)

tk.Button(
    toolbar,
    text="Seçimi temizle",
    command=clear_selection,
    bg=CARD,
    fg=FG,
    relief="flat",
    padx=12,
).pack(side="right", padx=4)

tk.Button(
    toolbar,
    text="ICON_DATA üret",
    command=generate_icon_data,
    bg=SELECTED,
    fg="white",
    relief="flat",
    padx=14,
).pack(side="right", padx=4)

# Kaydırılabilir ikon alanı
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
            cursor="hand2",
        )

        frame.grid(
            row=i // COLUMNS,
            column=i % COLUMNS,
            padx=4,
            pady=4,
            sticky="nsew",
        )

        cards[path] = frame

        image_label = tk.Label(
            frame,
            image=photo,
            bg=CARD,
            cursor="hand2",
        )
        image_label.pack(pady=(0, 5))

        name = path.relative_to(ICON_DIR).as_posix()

        name_label = tk.Label(
            frame,
            text=name,
            bg=CARD,
            fg=FG,
            wraplength=115,
            justify="center",
            cursor="hand2",
        )
        name_label.pack()

        # Kartın her yerine tıklanınca seçim değişsin.
        for widget in (frame, image_label, name_label):
            widget.bind(
                "<Button-1>",
                lambda event, p=path: toggle_selection(p),
            )

    except Exception as exc:
        print(f"Okunamadı: {path} - {exc}")

for col in range(COLUMNS):
    scroll_frame.grid_columnconfigure(col, weight=1)

def on_mousewheel(event):
    canvas.yview_scroll(
        -1 if event.delta > 0 else 1,
        "units",
    )

canvas.bind_all("<MouseWheel>", on_mousewheel)

if not files:
    tk.Label(
        root,
        text=f"PNG bulunamadı:\n{ICON_DIR}",
        bg=BG,
        fg="#FF6B6B",
    ).pack(pady=20)

root.mainloop()