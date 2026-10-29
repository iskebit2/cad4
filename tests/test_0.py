from core.units import UnitSystem, convert_project_units
from data.enums import SectionType
from geometry.frame_builder import FrameBuilder
from geometry.profile_generator import ProfileGenerator
from tools.s2k.loader import S2KLoader
from tools.s2k_exporter import S2KExporter
p = S2KLoader(r"tests/merdiven_sap2000.s2k").load()

gen = ProfileGenerator()

v = gen._validate_params(SectionType.CUSTOM, {"h": 0.01, "b": 0.01})
print(f"validated: h={v.get('h')}, b={v.get('b')}")

link = p.sections["link"]
prof = gen.get_profile(link.profile_type, dict(link.profile_params))
print(f"link profile: {prof.tolist()}")