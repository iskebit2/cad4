# inspector/catalog_project.py
"""
Project'i Inspector'ın Catalog protokolüne uyarla.
"""

class ProjectCatalog:
    def __init__(self, project):
        self.project = project

    def list_sections(self):
        return sorted(self.project.sections.keys())

    def get_section(self, name):
        return self.project.sections.get(name)

    def get_link_prop(self, name):
        return self.project.link_props.get(name)

    def list_materials(self):
        return sorted(self.project.materials.keys())

    def get_material(self, name):
        return self.project.materials.get(name)

    def list_link_props(self):
        return sorted(self.project.link_props.keys())

    def list_load_patterns(self):
        return sorted(self.project.load_patterns.keys())

    def list_planes(self):
        return sorted(self.project.planes.values(), key=lambda p: p.name)