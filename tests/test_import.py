from tools.s2k.loader import S2KLoader
loader = S2KLoader("tests/merdiven_sap2000.s2k")
project = loader.load()

# Kütle
found = False
for n in project.scene.nodes.values():
    if n.added_mass_1 or n.added_mmi_1:
        print(f"Node {n.label}: M1={n.added_mass_1}, MMI3={n.added_mmi_3}")
        found = True
print("Kütle atandı ✅" if found else "Kütle YOK ❌")

# Constraint
found = False
for n in project.scene.nodes.values():
    if n.constraint_name:
        print(f"Node {n.label}: constraint={n.constraint_name}")
        found = True
print("Constraint atandı ✅" if found else "Constraint YOK ❌")