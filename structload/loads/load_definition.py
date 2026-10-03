#load_definition.py

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoadComponent:
    """
    Bir G yükünün bileşeni.

    İki tip bileşen olabilir:

    1. Doğrudan alan yükü:
       value=0.30, unit='kN/m²'

    2. Malzeme + kalınlık:
       material='seramik', thickness=0.01
    """

    name: str
    value: float | None = None
    material: str | None = None
    thickness: float | None = None
    unit: str = "kN/m²"

    def calculate(self, material_weights: dict[str, float]) -> float:

        # Doğrudan alan yükü
        if self.value is not None:
            return self.value

        # Malzeme + kalınlık
        if self.material is not None and self.thickness is not None:

            if self.material not in material_weights:
                raise KeyError(
                    f"Tanımsız malzeme: {self.material}"
                )

            gamma = material_weights[self.material]

            return gamma * self.thickness

        raise ValueError(
            f"Geçersiz yük bileşeni: {self.name}"
        )


@dataclass
class LoadDefinition:
    """
    Projede kullanılabilecek G veya Q yük tanımı.
    """

    id: str
    name: str
    load_type: str          # G veya Q

    # Basit yüklerde doğrudan değer
    value: float | None = None

    unit: str = "kN/m²"

    # G yükünün bileşenleri
    components: list[LoadComponent] = field(default_factory=list)

    source: str = "user"
    description: str = ""

    def calculate(self, material_weights) -> float:
        if self.components:
            return sum(c.calculate(material_weights) for c in self.components)
        return self.value or 0.0

    def as_dict(
        self,
        material_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:

        return {
            "id": self.id,
            "name": self.name,
            "load_type": self.load_type,
            "value": self.calculate(material_weights),
            "unit": self.unit,
            "source": self.source,
            "description": self.description,
        }