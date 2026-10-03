#load_manager.py

from typing import Iterable

from structload.loads.load_definition import LoadDefinition


class LoadManager:
    """
    Projedeki G/Q yük tanımlarını ve eleman atamalarını yönetir.

    assignments:
        {
            element_id: {
                "G": ["G01", "G02"],
                "Q": ["Q01"]
            }
        }
    """

    def __init__(
        self,
        material_weights: dict[str, float] | None = None
    ):
        self.material_weights = material_weights or {}

        self.definitions: dict[str, LoadDefinition] = {}

        self.assignments: dict[int | str, dict[str, list[str]]] = {}

    # ---------------------------------------------------------
    # YÜK TANIMLARI
    # ---------------------------------------------------------

    def add_definition(self, definition: LoadDefinition):

        if definition.load_type not in ("G", "Q"):
            raise ValueError(
                "load_type yalnızca 'G' veya 'Q' olabilir."
            )

        if definition.id in self.definitions:
            raise ValueError(
                f"Aynı ID zaten mevcut: {definition.id}"
            )

        self.definitions[definition.id] = definition

    def get_definition(self, load_id: str) -> LoadDefinition:

        try:
            return self.definitions[load_id]
        except KeyError:
            raise KeyError(
                f"Tanımlı yük bulunamadı: {load_id}"
            )

    def get_value(self, load_id: str) -> float:

        definition = self.get_definition(load_id)

        return definition.calculate(
            self.material_weights
        )

    # ---------------------------------------------------------
    # ELEMAN ATAMALARI
    # ---------------------------------------------------------

    def assign(
        self,
        element_id: int | str,
        load_id: str
    ):

        definition = self.get_definition(load_id)

        load_type = definition.load_type

        if element_id not in self.assignments:
            self.assignments[element_id] = {
                "G": [],
                "Q": []
            }

        if load_id not in self.assignments[element_id][load_type]:
            self.assignments[element_id][load_type].append(load_id)

    def remove(
        self,
        element_id: int | str,
        load_id: str
    ):

        if element_id not in self.assignments:
            return

        definition = self.get_definition(load_id)

        load_type = definition.load_type

        if load_id in self.assignments[element_id][load_type]:
            self.assignments[element_id][load_type].remove(load_id)

    def clear_element(
        self,
        element_id: int | str,
        load_type: str | None = None
    ):

        if element_id not in self.assignments:
            return

        if load_type is None:
            self.assignments[element_id] = {
                "G": [],
                "Q": []
            }

        else:
            self.assignments[element_id][load_type] = []

    # ---------------------------------------------------------
    # ELEMAN YÜKLERİ
    # ---------------------------------------------------------

    def get_element_loads(
        self,
        element_id: int | str
    ) -> dict[str, list[LoadDefinition]]:

        result = {
            "G": [],
            "Q": []
        }

        assignment = self.assignments.get(
            element_id,
            {"G": [], "Q": []}
        )

        for load_type in ("G", "Q"):

            for load_id in assignment[load_type]:

                result[load_type].append(
                    self.get_definition(load_id)
                )

        return result

    def get_element_total(
        self,
        element_id: int | str,
        load_type: str
    ) -> float:

        if load_type not in ("G", "Q"):
            raise ValueError(
                "load_type G veya Q olmalıdır."
            )

        assignment = self.assignments.get(
            element_id,
            {"G": [], "Q": []}
        )

        return sum(
            self.get_value(load_id)
            for load_id in assignment[load_type]
        )

    # ---------------------------------------------------------
    # PROJEDE KULLANILANLAR
    # ---------------------------------------------------------

    def used_definitions(
        self,
        load_type: str | None = None
    ) -> list[LoadDefinition]:

        used_ids = set()

        for assignment in self.assignments.values():

            for kind in ("G", "Q"):

                if load_type is not None and kind != load_type:
                    continue

                used_ids.update(
                    assignment[kind]
                )

        result = []

        for load_id in used_ids:

            definition = self.get_definition(load_id)

            result.append(definition)

        return sorted(
            result,
            key=lambda x: x.id
        )

    # ---------------------------------------------------------
    # RAPOR VERİSİ
    # ---------------------------------------------------------

    def definition_rows(
        self,
        load_type: str | None = None
    ) -> list[dict]:

        rows = []

        for definition in self.used_definitions(load_type):

            rows.append({
                "ID": definition.id,
                "Yük": definition.name,
                "Tip": definition.load_type,
                "Değer (kN/m²)": round(
                    definition.calculate(
                        self.material_weights
                    ),
                    3
                ),
                "Kaynak": definition.source,
            })

        return rows

    def assignment_rows(self) -> list[dict]:

        rows = []

        for element_id, assignment in self.assignments.items():

            g = [
                self.get_definition(load_id).name
                for load_id in assignment["G"]
            ]

            q = [
                self.get_definition(load_id).name
                for load_id in assignment["Q"]
            ]

            rows.append({
                "Eleman": element_id,
                "G yükleri": ", ".join(g),
                "G toplam (kN/m²)": round(
                    self.get_element_total(element_id, "G"),
                    3
                ),
                "Q yükleri": ", ".join(q),
                "Q toplam (kN/m²)": round(
                    self.get_element_total(element_id, "Q"),
                    3
                ),
            })

        return rows

if __name__ == "__main__":
    from structload.data.material_data import MATERIAL_WEIGHTS, LIVE_LOADS

    from structload.loads.load_definition import (
        LoadDefinition,
        LoadComponent
    )

    from structload.loads.load_manager import LoadManager


    manager = LoadManager(
        material_weights=MATERIAL_WEIGHTS
    )

    manager.add_definition(
    LoadDefinition(
        id="G01",
        name="Konut Döşemesi",
        load_type="G",
        components=[
            LoadComponent(
                name="Seramik",
                material="seramik",
                thickness=0.01
            ),
            LoadComponent(
                name="Şap",
                material="şap",
                thickness=0.05
            ),
            LoadComponent(
                name="Asma tavan",
                value=0.30
            )
        ],
        source="user"
    )
)
    manager.add_definition(
    LoadDefinition(
        id="G02",
        name="Karo Kaplama",
        load_type="G",
        value=2.079,
        source="TS 498"
    )
)

    hareketli = LoadDefinition(
    id="Q01",
    name=LIVE_LOADS["konut"]["name"],
    load_type="Q",
    value=LIVE_LOADS["konut"]["value"],
    source="TS 498"
)
    
    manager.add_definition(hareketli)
    manager.assign(101, "G01")
    manager.assign(101, "Q01")

    manager.assign(102, "G01")
    manager.assign(102, "Q01")

    manager.assign(103, "G02")
    manager.assign(103, "Q01")
    print(manager.definition_rows("Q"))