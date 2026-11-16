from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

OUTPUT_MAP = PROJECT_ROOT / "project_map.json"
OUTPUT_DEPS = PROJECT_ROOT / "dependencies.json"
OUTPUT_CONTEXT = PROJECT_ROOT / "PROJECT_CONTEXT.md"

BLACKLIST = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "node_modules",
    ".tox",
    ".nox",
}

# Projeye özgü mimari bilgileri buraya ekleyebilirsin.
ARCHITECTURE_NOTES = [
    "CAD4 is a structural engineering CAD application.",
    "The project uses Python and OpenGL.",
]


# ============================================================
# HELPERS
# ============================================================

def relative_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def module_name(path: Path) -> str:
    """Dosya yolundan Python modül adını üretir."""

    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(rel.parts)

    if parts and parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def get_docstring(node) -> str | None:
    return ast.get_docstring(node)


def get_signature(node) -> str:
    """Fonksiyon/metot imzasını üretir."""

    args = ast.unparse(node.args)

    if node.returns:
        args += f" -> {ast.unparse(node.returns)}"

    return f"({args})"


def get_base_names(node) -> list[str]:
    return [ast.unparse(base) for base in node.bases]


def read_python_file(path: Path):
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        return source, tree, None

    except Exception as exc:
        return None, None, str(exc)


# ============================================================
# DIRECTORY SCANNER
# ============================================================

def scan_project():
    """Projedeki Python dosyalarını tarar."""

    python_files = []

    for root, dirs, files in os.walk(PROJECT_ROOT):

        # Blacklist: klasörlere hiç girme.
        dirs[:] = sorted(
            d for d in dirs
            if d not in BLACKLIST
            and not d.startswith(".")
        )

        for filename in sorted(files):
            if filename.endswith(".py"):
                python_files.append(Path(root) / filename)

    return sorted(python_files)


# ============================================================
# AST ANALYSIS
# ============================================================

def analyze_file(path: Path):
    source, tree, error = read_python_file(path)

    result = {
        "path": relative_path(path),
        "module": module_name(path),
        "docstring": None,
        "classes": [],
        "functions": [],
        "imports": [],
        "parse_error": error,
    }

    if tree is None:
        return result

    result["docstring"] = get_docstring(tree)

    for node in tree.body:

        # ----------------------------------------------------
        # CLASSES
        # ----------------------------------------------------

        if isinstance(node, ast.ClassDef):

            cls = {
                "name": node.name,
                "line": node.lineno,
                "docstring": get_docstring(node),
                "bases": get_base_names(node),
                "methods": [],
            }

            for item in node.body:

                if isinstance(
                    item,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    cls["methods"].append({
                        "name": item.name,
                        "line": item.lineno,
                        "signature": get_signature(item),
                        "async": isinstance(
                            item, ast.AsyncFunctionDef
                        ),
                        "docstring": get_docstring(item),
                    })

            result["classes"].append(cls)

        # ----------------------------------------------------
        # MODULE FUNCTIONS
        # ----------------------------------------------------

        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            result["functions"].append({
                "name": node.name,
                "line": node.lineno,
                "signature": get_signature(node),
                "async": isinstance(
                    node, ast.AsyncFunctionDef
                ),
                "docstring": get_docstring(node),
            })

        # ----------------------------------------------------
        # IMPORTS
        # ----------------------------------------------------

        elif isinstance(node, ast.Import):

            for alias in node.names:
                result["imports"].append({
                    "type": "import",
                    "module": alias.name,
                    "name": None,
                    "alias": alias.asname,
                    "line": node.lineno,
                })

        elif isinstance(node, ast.ImportFrom):

            result["imports"].append({
                "type": "from",
                "module": node.module,
                "level": node.level,
                "names": [
                    {
                        "name": alias.name,
                        "alias": alias.asname,
                    }
                    for alias in node.names
                ],
                "line": node.lineno,
            })

    return result


# ============================================================
# DEPENDENCY ANALYSIS
# ============================================================

def resolve_imports(modules):
    """
    Import kayıtlarını yerel ve harici bağımlılıklar
    olarak sınıflandırır.
    """

    module_names = {
        item["module"]
        for item in modules
        if item["module"]
    }

    dependencies = []

    def find_local_module(name):
        if not name:
            return None

        if name in module_names:
            return name

        # Alt modülleri de kontrol et.
        matches = [
            m for m in module_names
            if m.startswith(name + ".")
        ]

        if matches:
            return name

        return None

    for item in modules:

        source_module = item["module"]
        source_package = (
            source_module
            if Path(item["path"]).name == "__init__.py"
            else source_module.rpartition(".")[0]
        )

        for imp in item["imports"]:

            if imp["type"] == "import":

                target = imp["module"]
                local = find_local_module(target)

                dependencies.append({
                    "source": source_module,
                    "target": target,
                    "type": "import",
                    "scope": "internal" if local else "external",
                    "line": imp["line"],
                })

            elif imp["type"] == "from":

                base = imp["module"] or ""

                if imp["level"]:
                    package_parts = source_package.split(".")
                    keep = max(0, len(package_parts) - imp["level"] + 1)
                    package_parts = package_parts[:keep]

                    base = ".".join(
                        package_parts + ([base] if base else [])
                    )

                for imported in imp["names"]:

                    if imported["name"] == "*":
                        target = base
                    else:
                        candidate = (
                            f"{base}.{imported['name']}"
                            if base else imported["name"]
                        )

                        target = (
                            candidate
                            if candidate in module_names
                            else base
                        )

                    local = find_local_module(target)

                    dependencies.append({
                        "source": source_module,
                        "target": target,
                        "type": "from",
                        "imported_name": imported["name"],
                        "scope": "internal" if local else "external",
                        "line": imp["line"],
                    })

    # Kalıtım ilişkileri
    inheritance = []

    for item in modules:
        for cls in item["classes"]:
            for base in cls["bases"]:
                inheritance.append({
                    "module": item["module"],
                    "class": cls["name"],
                    "base": base,
                })

    return {
        "dependencies": dependencies,
        "inheritance": inheritance,
    }


# ============================================================
# PROJECT TREE
# ============================================================

def build_tree(modules):
    root = {
        "name": PROJECT_ROOT.name,
        "type": "directory",
        "children": {},
    }

    for item in modules:
        parts = Path(item["path"]).parts
        current = root

        for part in parts[:-1]:
            current = current["children"].setdefault(
                part,
                {
                    "name": part,
                    "type": "directory",
                    "children": {},
                }
            )

        current["children"][parts[-1]] = {
            "name": parts[-1],
            "type": "python_file",
            "module": item["module"],
            "classes": [
                cls["name"] for cls in item["classes"]
            ],
            "functions": [
                fn["name"] for fn in item["functions"]
            ],
        }

    return root


# ============================================================
# JSON OUTPUT
# ============================================================

def save_json(path: Path, data):
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# MARKDOWN CONTEXT
# ============================================================

def build_context(modules, dependency_data):

    lines = [
        f"# {PROJECT_ROOT.name} - Project Context",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Project Overview",
        "",
        f"- Name: {PROJECT_ROOT.name}",
        f"- Python files: {len(modules)}",
        "",
        "## Architecture Notes",
        "",
    ]

    for note in ARCHITECTURE_NOTES:
        lines.append(f"- {note}")

    lines.extend([
        "",
        "## Module Structure",
        "",
    ])

    for item in modules:

        lines.extend([
            f"### `{item['module']}`",
            "",
            f"Path: `{item['path']}`",
            "",
        ])

        if item["docstring"]:
            lines.append(item["docstring"])
            lines.append("")

        if item["parse_error"]:
            lines.append(
                f"**Parse error:** {item['parse_error']}"
            )
            lines.append("")
            continue

        if item["classes"]:
            lines.extend([
                "#### Classes",
                "",
            ])

            for cls in item["classes"]:

                bases = (
                    f" ({', '.join(cls['bases'])})"
                    if cls["bases"] else ""
                )

                lines.append(
                    f"- **{cls['name']}**{bases} "
                    f"(line {cls['line']})"
                )

                if cls["docstring"]:
                    lines.append(
                        f"  - {cls['docstring'].splitlines()[0]}"
                    )

                for method in cls["methods"]:
                    lines.append(
                        f"  - `{method['name']}"
                        f"{method['signature']}`"
                    )

                    if method["docstring"]:
                        lines.append(
                            f"    - {method['docstring'].splitlines()[0]}"
                        )

            lines.append("")

        if item["functions"]:
            lines.extend([
                "#### Module Functions",
                "",
            ])

            for fn in item["functions"]:
                lines.append(
                    f"- `{fn['name']}{fn['signature']}`"
                )

                if fn["docstring"]:
                    lines.append(
                        f"  - {fn['docstring'].splitlines()[0]}"
                    )

            lines.append("")

    # Dependencies
    lines.extend([
        "## Internal Dependencies",
        "",
    ])

    for dep in dependency_data["dependencies"]:
        if dep["scope"] == "internal":
            lines.append(
                f"- `{dep['source']}` → `{dep['target']}`"
            )

    # Inheritance
    lines.extend([
        "",
        "## Inheritance",
        "",
    ])

    for item in dependency_data["inheritance"]:
        lines.append(
            f"- `{item['module']}.{item['class']}` "
            f"extends `{item['base']}`"
        )

    lines.extend([
        "",
        "## Important Notes",
        "",
        "- This document is generated using Python AST.",
        "- Import relationships are statically inferred.",
        "- Dynamic imports and runtime relationships may not appear.",
        "- Class ownership and architectural responsibilities "
        "require human documentation.",
        "- Refer to the source code for authoritative implementation details.",
        "",
    ])

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print(f"\nScanning: {PROJECT_ROOT}")

    python_files = scan_project()

    print(f"Found {len(python_files)} Python files.")

    modules = [
        analyze_file(path)
        for path in python_files
    ]

    dependency_data = resolve_imports(modules)

    project_map = {
        "project": {
            "name": PROJECT_ROOT.name,
            "root": str(PROJECT_ROOT),
            "language": "Python",
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "python_file_count": len(modules),
        },
        "tree": build_tree(modules),
        "modules": modules,
    }

    dependencies = {
        "project": PROJECT_ROOT.name,
        **dependency_data,
    }

    context = build_context(
        modules,
        dependency_data,
    )

    save_json(OUTPUT_MAP, project_map)
    save_json(OUTPUT_DEPS, dependencies)

    OUTPUT_CONTEXT.write_text(
        context,
        encoding="utf-8",
    )

    print("\nGenerated files:")

    print(f"  [OK] {OUTPUT_MAP.name}")
    print(f"  [OK] {OUTPUT_DEPS.name}")
    print(f"  [OK] {OUTPUT_CONTEXT.name}")

    print("\nProject mapping completed.")


if __name__ == "__main__":
    main()