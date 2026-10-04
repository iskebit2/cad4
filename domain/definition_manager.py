# domain/definition_manager.py
from typing import Dict, Optional

from domain.definition import (
    Material, Section, LinkProp,
    LoadPattern, LoadCase, ModalCase, LoadCombination,
    SpectrumFunction, ResponseSpectrumCase, AutoSeismicTSC2018,
    GeneralProjectInfo, SiteInformation,
    SpectrumSourceType,
    get_tsc2018_site_coefficients,
)


class DuplicateNameError(ValueError):
    """Aynı isimde nesne zaten var."""
    pass


class DefinitionManager:
    def __init__(self):
        self.materials: Dict[str, Material] = {}
        self.sections: Dict[str, Section] = {}
        self.link_props: Dict[str, LinkProp] = {}
        self.load_patterns: Dict[str, LoadPattern] = {}
        self.load_cases: Dict[str, LoadCase] = {}
        self.modal_cases: Dict[str, ModalCase] = {}
        self.combinations: Dict[str, LoadCombination] = {}
        self.spectrum_functions: Dict[str, SpectrumFunction] = {}
        self.response_spectrum_cases: Dict[str, ResponseSpectrumCase] = {}
        self.auto_seismics: Dict[str, AutoSeismicTSC2018] = {}
        self.mass_source_map: Dict[str, float] = {}
        self.project_info: Dict[str, object] = {
            "gen": GeneralProjectInfo(),
            "site": SiteInformation(),
        }

    # ==================================================================
    # GENEL EKLEME — VARSA ÜZERİNE YAZAR (idempotent)
    # Importer, UI kaydet, varsayılan yükleme bu davranışı bekler.
    # ==================================================================
    def add_material(self, m: Material):
        self.materials[m.name] = m

    def add_section(self, s: Section):
        self.sections[s.name] = s

    def add_link_prop(self, p: LinkProp):
        self.link_props[p.name] = p

    def add_load_pattern(self, p: LoadPattern):
        self.load_patterns[p.name] = p

    def add_load_case(self, c: LoadCase):
        self.load_cases[c.name] = c

    def add_modal_case(self, c: ModalCase):
        self.modal_cases[c.name] = c

    def add_combination(self, c: LoadCombination):
        self.combinations[c.name] = c

    def add_spectrum_function(self, spec: SpectrumFunction):
        self.spectrum_functions[spec.name] = spec

    def add_response_spectrum_case(self, rs: ResponseSpectrumCase):
        self.response_spectrum_cases[rs.name] = rs

    def add_auto_seismic(self, a: AutoSeismicTSC2018):
        self.auto_seismics[a.load_pattern] = a

    # ==================================================================
    # STRICT EKLEME — çakışmada hata
    # Kullanıcı "yeni" oluştururken kullanılır.
    # ==================================================================
    def add_material_strict(self, m: Material):
        self._strict(self.materials, m.name, "Material")
        self.materials[m.name] = m

    def add_section_strict(self, s: Section):
        self._strict(self.sections, s.name, "Section")
        self.sections[s.name] = s

    def add_link_prop_strict(self, p: LinkProp):
        self._strict(self.link_props, p.name, "LinkProp")
        self.link_props[p.name] = p

    @staticmethod
    def _strict(collection: dict, name: str, kind: str):
        if name in collection:
            raise DuplicateNameError(
                f"{kind} '{name}' zaten kayıtlı. Farklı bir isim seçin "
                f"veya mevcut olanı düzenleyin."
            )

    # ==================================================================
    # İSİM DEĞİŞTİRME
    # ==================================================================
    def _rename(self, collection: dict, old: str, new: str, kind: str):
        if old not in collection:
            raise KeyError(f"{kind} '{old}' bulunamadı.")
        if new == old:
            return
        if new in collection:
            raise DuplicateNameError(f"{kind} '{new}' zaten var.")
        obj = collection.pop(old)
        obj.name = new
        collection[new] = obj

    def rename_material(self, old: str, new: str):
        self._rename(self.materials, old, new, "Material")

    def rename_section(self, old: str, new: str):
        self._rename(self.sections, old, new, "Section")

    def rename_link_prop(self, old: str, new: str):
        self._rename(self.link_props, old, new, "LinkProp")

    # ==================================================================
    # SORGULAMA
    # ==================================================================
    def has_material(self, name: str) -> bool:
        return name in self.materials

    def has_section(self, name: str) -> bool:
        return name in self.sections

    def has_link_prop(self, name: str) -> bool:
        return name in self.link_props

    def get_section_by_name(self, name: str) -> Optional[Section]:
        return self.sections.get(name)

    def get_material_by_name(self, name: str) -> Optional[Material]:
        return self.materials.get(name)

    def get_link_prop_by_name(self, name: str) -> Optional[LinkProp]:
        return self.link_props.get(name)

    # ==================================================================
    # SİLME
    # ==================================================================
    def remove_material(self, name: str):
        self.materials.pop(name, None)

    def remove_section(self, name: str):
        self.sections.pop(name, None)

    def remove_link_prop(self, name: str):
        self.link_props.pop(name, None)

    # ==================================================================
    # Spektrum / deprem
    # ==================================================================
    def create_tbdy2018_spectrum(
        self, name, ss, s1, site_class="ZC",
        r_coeff=1.0, d_coeff=1.0, i_coeff=1.0,
        tl=6.0, num_points=200,
    ) -> SpectrumFunction:
        fs, f1, points = self._build_tsc2018_points(
            ss, s1, site_class, r_coeff, d_coeff, i_coeff, tl, num_points
        )
        spec = SpectrumFunction(
            name=name, source_type=SpectrumSourceType.TSC_2018,
            ss=ss, s1=s1, tl=tl, site_class=site_class,
            fs=fs, f1=f1,
            r_coeff=r_coeff, d_coeff=d_coeff, i_coeff=i_coeff,
            points=points,
        )
        self.add_spectrum_function(spec)
        return spec

    @staticmethod
    def _build_tsc2018_points(ss, s1, site_class, r, d, i, tl, num_points):
        fs, f1 = get_tsc2018_site_coefficients(ss, s1, site_class)
        sds, sd1 = ss * fs, s1 * f1
        ta = 0.2 * sd1 / sds if sds > 0 else 0.0
        tb = sd1 / sds if sds > 0 else 0.0
        points = []
        max_t = max(tl + 2.0, 8.0)
        dt = max_t / num_points
        for k in range(num_points + 1):
            t = k * dt
            if ta > 0 and t < ta:
                sae = (0.4 + 0.6 * t / ta) * sds
            elif t <= tb:
                sae = sds
            elif t <= tl:
                sae = sd1 / t
            else:
                sae = sd1 * tl / (t * t)
            ra = (d + (r / i - d) * t / tb) if (t < tb and tb > 0) else r / i
            points.append((round(t, 4), round(sae / ra, 6)))
        return fs, f1, points

    def __inspector_tree__(self) -> dict:
        return {
            "Project Information": self.project_info,
            "Materials": self.materials,
            "Sections": self.sections,
            "Link Properties": self.link_props,
            "Load Patterns": self.load_patterns,
            "Load Cases": self.load_cases,
            "Modal Cases": self.modal_cases,
            "Load Combinations": self.combinations,
            "Spectrum Functions": self.spectrum_functions,
            "Response Spectrum Cases": self.response_spectrum_cases,
            "Auto Seismics (TBDY 2018)": self.auto_seismics,
        }