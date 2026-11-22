from tools.s2k import S2KLoader

loader = S2KLoader("tests/testmodel1.s2k")
project = loader.load()

print("LinkProp sayısı:", len(project.link_props))
for name, lp in project.link_props.items():
    print(name, type(lp).__name__, lp.prop_type, getattr(lp, "DOF", None), getattr(lp, "Ke", None), getattr(lp, "Ce", None))

print("Link eleman sayısı:", len(project.math_model.links))
for uid, link in project.math_model.links.items():
    print(uid, link.label, link.propname, link.node_i.label, link.node_j.label)