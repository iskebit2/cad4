from pathlib import Path
import resvg_py


src = Path("assets/icons")
dst = Path("assets/icons_png")
dst.mkdir(exist_ok=True)


for svg in sorted(src.glob("*.svg")):
    png = dst / f"{svg.stem}.png"

    try:
        data = resvg_py.svg_to_bytes(
            svg_path=str(svg),
            width=48,
            height=48,
        )

        png.write_bytes(data)
        print(f"OK  {svg.name} -> {png.name}")

    except Exception as e:
        print(f"ERR {svg.name}: {e}")


print("Bitti.")