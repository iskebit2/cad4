
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
    Category.FILE: "Dosya",
    Category.EDIT: "Düzen",
    Category.VIEW: "Görünüm",
    Category.DRAW: "Çizim",
    Category.LOADS: "Yükler",
    Category.MANAGEMENT: "Yönetim",
    Category.TOOLS: "Araçlar",
    Category.DEBUG: "Hata Ayıklama",
    Category.CONVERT: "Dönüştür",
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
