
# app/settings/categories.py

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    FILE = "File"
    EDIT = "Edit"
    VIEW = "View"
    DRAW = "Draw"
    LOADS = "Loads"
    MANAGEMENT = "Management"
    TOOLS = "Tools"
    DEBUG = "Debug"
    CONVERT = "Convert"


# Merkezi kategori sıralaması
CATEGORY_ORDER: tuple[Category, ...] = tuple(Category)


# Kullanıcı arayüzünde gösterilecek etiketler
CATEGORY_LABELS: dict[Category, str] = {
    Category.FILE: "File",
    Category.EDIT: "Edit",
    Category.VIEW: "View",
    Category.DRAW: "Draw",
    Category.LOADS: "Loads",
    Category.MANAGEMENT: "Management",
    Category.TOOLS: "Tools",
    Category.DEBUG: "Debug",
    Category.CONVERT: "Convert",
}


# Varsayılan kategori
FALLBACK_CATEGORY: Category = Category.TOOLS


# Yardımcı fonksiyonlar
def category_label(category: Category | str) -> str:
    try:
        category = Category(category)
    except ValueError:
        return str(category)

    return CATEGORY_LABELS.get(category, category.value)


def category_order(category: Category | str) -> int:
    try:
        category = Category(category)
    except ValueError:
        return len(CATEGORY_ORDER)

    return CATEGORY_ORDER.index(category)
