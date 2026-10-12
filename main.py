# main.py


from app import CadWindow, CadApp
import builtins
_orig_import = builtins.__import__

def traced_import(name, *args, **kwargs):
    if name.startswith("kivy"):
        import traceback
        print(f"\n[KIVY IMPORT TESPİT] {name}")
        for line in traceback.format_stack()[:-1]:
            print(line.rstrip())
    return _orig_import(name, *args, **kwargs)

builtins.__import__ = traced_import

def main():
    window = CadWindow(width=1280, height=800, title="CAD4")
    window.create()

    app = CadApp(window)

    try:
        window.run(app.frame, target_fps=60)
    finally:
        app.shutdown()
        window.shutdown()


if __name__ == "__main__":
    main()
    