"""field.kind -> Widget eşlemesi."""

from inspector.widgets.bool_widget import BoolWidget
from inspector.widgets.color_widget import ColorWidget
from inspector.widgets.enum_widget import EnumWidget
from inspector.widgets.float_widget import FloatWidget
from inspector.widgets.info_widget import InfoWidget
from inspector.widgets.int_widget import IntWidget
from inspector.widgets.link_prop_widget import LinkPropWidget
from inspector.widgets.list_object_widget import ListObjectWidget
from inspector.widgets.list_widget import ListWidget
from inspector.widgets.material_widget import MaterialWidget
from inspector.widgets.section_widget import SectionWidget
from inspector.widgets.string_widget import StringWidget

_WIDGETS = {
    "bool": BoolWidget,
    "float": FloatWidget,
    "int": IntWidget,
    "string": StringWidget,
    "str": StringWidget,
    "enum": EnumWidget,
    "color": ColorWidget,
    "list": ListWidget,
    "list_object": ListObjectWidget,
    "section_ref":  SectionWidget,
    "material_ref": MaterialWidget,
    "link_prop_ref": LinkPropWidget,
    "info":          InfoWidget,
}

_CACHE = {}


def widget_for_kind(kind: str):
    if kind in _CACHE:
        return _CACHE[kind]
    cls = _WIDGETS.get(kind)
    _CACHE[kind] = cls() if cls else None
    return _CACHE[kind]