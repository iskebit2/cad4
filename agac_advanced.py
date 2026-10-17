# import os
# import ast

# IGNORE = {".git","__pycache__", "test", ".venv", ".ipynb_checkpoints",".pytest_cache",".ruff_cache",".vscode"}


# def classes(path):
#     try:
#         with open(path, encoding="utf-8") as f:
#             tree = ast.parse(f.read())
#     except Exception:
#         return []

#     return [
#         n.name
#         for n in tree.body
#         if isinstance(n, ast.ClassDef)
#     ]


# def tree(path, prefix=""):
#     out = []

#     entries = [
#         e for e in sorted(os.listdir(path))
#         if e not in IGNORE
#     ]

#     for i, name in enumerate(entries):
#         full = os.path.join(path, name)
#         last = i == len(entries) - 1
#         mark = "└── " if last else "├── "

#         if os.path.isdir(full):
#             out.append(f"{prefix}{mark}{name}/")
#             out += tree(
#                 full,
#                 prefix + ("    " if last else "│   ")
#             )

#         elif name.endswith(".py"):
#             out.append(f"{prefix}{mark}{name}")

#             for j, class_name in enumerate(classes(full)):
#                 clast = j == len(classes(full)) - 1
#                 cm = "└── " if clast else "├── "

#                 out.append(
#                     f"{prefix}{'    ' if last else '│   '}"
#                     f"{cm}{class_name}"
#                 )

#     return out


# if __name__ == "__main__":
#     result = "\n".join(tree("."))

#     with open("class_tree.txt", "w", encoding="utf-8") as f:
#         f.write(result)


import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "main.py"

EXCLUDE = {
    ".venv", ".git", "__pycache__", "site-packages",
    ".ipynb_checkpoints", "tests", "build", "dist",
}

modules = {}

for path in ROOT.rglob("*.py"):
    rel = path.relative_to(ROOT)

    if any(part in EXCLUDE for part in rel.parts):
        continue

    parts = list(rel.with_suffix("").parts)

    if parts[-1] == "__init__":
        parts.pop()

    if parts:
        modules[".".join(parts)] = path

def module_name(path):
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)

def imports_from(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    found = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):
            level = node.level
            package = module_name(path).split(".")[:-1]

            if path.name == "__init__.py":
                package = module_name(path).split(".")

            if level:
                base = package[:len(package) - level + 1]
                if node.module:
                    base += node.module.split(".")
                name = ".".join(base)
            else:
                name = node.module or ""

            if name:
                found.append(name)

            found.extend(
                f"{name}.{alias.name}"
                for alias in node.names
                if name
            )

    return found

def resolve(name):
    while name:
        if name in modules:
            return name
        name = name.rpartition(".")[0]
    return None

entry = module_name(ENTRY)
visited = set()
todo = [entry]

while todo:
    current = todo.pop()
    if current in visited or current not in modules:
        continue

    visited.add(current)

    for name in imports_from(modules[current]):
        target = resolve(name)
        if target and target not in visited:
            todo.append(target)

print("\n--- MAIN.PY ÜZERİNDEN ULAŞILAN MODÜLLER ---")
for name in sorted(visited):
    print(modules[name].relative_to(ROOT))

print("\n--- ULAŞILAMAYAN MODÜLLER (SİLME ADAYI DEĞİL, İNCELEME LİSTESİ) ---")
for name in sorted(set(modules) - visited):
    print(modules[name].relative_to(ROOT))
