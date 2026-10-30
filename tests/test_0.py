from core.units import UnitSystem, convert_project_units
from data.enums import SectionType
from geometry.frame_builder import FrameBuilder
from geometry.profile_generator import ProfileGenerator
from tools.s2k.loader import S2KLoader
from tools.s2k_exporter import S2KExporter
p = S2KLoader(r"tests/merdiven_sap2000.s2k").load()
print(p)

