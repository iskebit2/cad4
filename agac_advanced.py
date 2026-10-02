import os
import ast

white_list= ["engine.py", "interaction.py", "camera.py","base_renderer.py","scene_renderer.py","base_element.py"]
IGNORE_DIRS = {"__pycache__", "test"}
EXTENSIONS = {".py"}

def get_classes_from_file(filepath):
    """Bir Python dosyasından sınıf isimleri, docstring ve metod docstring'lerini alır."""
    classes = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except Exception as e:
        return []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            class_doc = ast.get_docstring(node) or "No docstring"
            methods = []
            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    method_name = n.name
                    method_doc = ast.get_docstring(n) or "No docstring"
                    methods.append((method_name, method_doc))
            classes.append((class_name, class_doc, methods))
    return classes

def scan_directory(path, prefix=""):
    """Klasörleri tarar ve Markdown / ağaç formatında sınıf ağacını üretir."""
    result = ""
    entries = sorted(os.listdir(path))
    for i, entry in enumerate(entries):
        full_path = os.path.join(path, entry)
        is_last = i == len(entries) - 1
        branch = "└── " if is_last else "├── "
       
        if entry[:4] in IGNORE_DIRS:
            continue
        if os.path.isdir(full_path) and entry not in IGNORE_DIRS:
            result += f"{prefix}{branch}{entry}/\n"
            result += scan_directory(full_path, prefix + ("    " if is_last else "│   "))
        elif os.path.isfile(full_path) and os.path.splitext(entry)[1] in EXTENSIONS:
            classes = get_classes_from_file(full_path)
            result += f"{prefix}{branch}{entry}\n"
            
            for j, (cls_name, cls_doc, methods) in enumerate(classes):
                cls_last = j == len(classes) - 1
                cls_branch = "└── " if cls_last else "├── "
                result += f"{prefix}{'    ' if is_last else '│   '}{cls_branch}**{cls_name}**: {cls_doc}\n"
                # continue
                for k, (method, method_doc) in enumerate(methods):
                    method_last = k == len(methods) - 1
                    method_branch = "└── " if method_last else "├── "
                    result += f"{prefix}{'    ' if is_last else '│   '}{'    '}{method_branch}{method}: {method_doc}\n"
    return result

def proje_ozetle(hedef_klasor=".", cikis_dosyası="proje_baglami.txt"):
    # Atlanacak klasörler (gereksiz kalabalığı önler)
    ignore_list = {'.git', '__pycache__', '.venv', 'venv', '.idea', '.vscode'}
    ignore_files= {'agac_advanced.py'}
    
    with open(cikis_dosyası, 'w', encoding='utf-8') as f:
        for kok, klasorler, dosyalar in os.walk(hedef_klasor):
            # Gereksiz klasörleri ele
            klasorler[:] = [d for d in klasorler if d not in ignore_list]
            
            for dosya_adi in dosyalar:
                if dosya_adi in ignore_files:
                    continue
                if dosya_adi in white_list:
                    pass
                else:
                    continue
                if dosya_adi.endswith('.py'):
                    tam_yol = os.path.join(kok, dosya_adi)
                    bağıl_yol = os.path.relpath(tam_yol, hedef_klasor)
                    
                    f.write(f"\n{'='*60}\n")
                    f.write(f"file: {bağıl_yol}\n")
                    f.write(f"{'='*60}\n\n")
                    
                    try:
                        with open(tam_yol, 'r', encoding='utf-8') as py_dosyasi:
                            f.write(py_dosyasi.read())
                    except Exception as e:
                        f.write(f"HATA: Dosya okunamadı! {e}\n")
                    
                    f.write("\n\n")

    print(f"İşlem tamam! Tüm kodlar '{cikis_dosyası}' dosyasına kaydedildi.")

if __name__ == "__main__":
    root_dir = "D:\Program\cad4"  # Proje kökü
    tree_md = scan_directory(root_dir)
    print(tree_md)
    # # Markdown çıktısı olarak kaydet
    with open("D:\Program\cad4\class_tree.txt", "w", encoding="utf-8") as f:
        f.write("```text\n")
        f.write(tree_md)
        f.write("```\n")
    
    # print("class_tree.md üretildi! ✔")

    proje_ozetle()
