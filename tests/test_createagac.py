
import os
import ast

# Taranmayacak klasörler
BLACKLIST = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "node_modules",
}


def get_classes_in_file(file_path):
    """Dosyadaki sınıfları ve docstring'lerini bulur."""
    classes = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=file_path)
    except Exception:
        return classes

    for item in node.body:
        if isinstance(item, ast.ClassDef):
            doc = ast.get_docstring(item)
            classes.append((item.name, doc))

    return classes


def print_tree(root_path, prefix=""):
    entries = sorted(
        e for e in os.listdir(root_path)
        if e not in BLACKLIST and not e.startswith("__")
    )

    for i, entry in enumerate(entries):
        path = os.path.join(root_path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "

        if os.path.isdir(path):
            print(f"{prefix}{connector}{entry}/")

            new_prefix = prefix + (
                "    " if i == len(entries) - 1 else "│   "
            )
            print_tree(path, new_prefix)

        elif os.path.isfile(path) and entry.endswith(".py"):
            print(f"{prefix}{connector}{entry}", end="")

            classes = get_classes_in_file(path)

            if classes:
                print()

                for j, (cls_name, doc) in enumerate(classes):
                    cls_connector = (
                        "└── " if j == len(classes) - 1 else "├── "
                    )
                    doc_summary = (
                        doc.splitlines()[0][:60] + "..."
                        if doc else ""
                    )

                    print(
                        f"{prefix}    {cls_connector}"
                        f"{cls_name}: {doc_summary}"
                    )
            else:
                print(" (no classes)")


if __name__ == "__main__":
    project_path = r"D:\Program\cad4"
    print_tree(project_path)
