import os
import ast

IGNORE = {".git","__pycache__", "test", ".venv", ".ipynb_checkpoints",".pytest_cache",".ruff_cache",".vscode"}


def classes(path):
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception:
        return []

    return [
        n.name
        for n in tree.body
        if isinstance(n, ast.ClassDef)
    ]


def tree(path, prefix=""):
    out = []

    entries = [
        e for e in sorted(os.listdir(path))
        if e not in IGNORE
    ]

    for i, name in enumerate(entries):
        full = os.path.join(path, name)
        last = i == len(entries) - 1
        mark = "└── " if last else "├── "

        if os.path.isdir(full):
            out.append(f"{prefix}{mark}{name}/")
            out += tree(
                full,
                prefix + ("    " if last else "│   ")
            )

        elif name.endswith(".py"):
            out.append(f"{prefix}{mark}{name}")

            for j, class_name in enumerate(classes(full)):
                clast = j == len(classes(full)) - 1
                cm = "└── " if clast else "├── "

                out.append(
                    f"{prefix}{'    ' if last else '│   '}"
                    f"{cm}{class_name}"
                )

    return out


if __name__ == "__main__":
    result = "\n".join(tree("."))

    with open("class_tree.txt", "w", encoding="utf-8") as f:
        f.write(result)