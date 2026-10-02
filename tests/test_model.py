# tests/test_model.py
import logging
logger = logging.getLogger(__name__)

from geometry.scenebuilder import SceneBuilder
from domain.definition import MatType, SectionType, LinkPropType

class TestModelBuilder:
    @staticmethod
    def build(builder: SceneBuilder):
        """Test modeli oluştur"""
        
        # ===== MALZEMELER =====
        steel = builder.create_material(
            name="STEEL",
            mat_type=MatType.STEEL,
            E=2.1e8,
            density=7850,
            color=(0.7, 0.7, 0.7)
        )
        
        concrete = builder.create_material(
            name="CONCRETE",
            mat_type=MatType.CONCRETE,
            E=3.0e7,
            density=2500,
            color=(0.5, 0.5, 0.5)
        )
        
        # ===== KESİTLER =====
        # IPE300
        ipe300 = builder.create_section(
            name="IPE300",
            profile_type=SectionType.I,
            profile_params={"b": 150, "h": 300, "tw": 10, "tf": 14},
            material=steel,
            color=(1.0, 1.0, 1.0)
        )
        
        # Kutu kesit
        box400 = builder.create_section(
            name="BOX400x15",
            profile_type=SectionType.BOX,
            profile_params={"b": 400, "h": 200, "t": 15},
            material=steel,
            color=(0.33, 1.0, 0.8)
        )
        
        # Boru kesit
        pipe200 = builder.create_section(
            name="PIPE200",
            profile_type=SectionType.PIPE,
            profile_params={"ro": 200, "ri": 180, "n": 24},
            material=steel,
            color=(1.0, 0.0, 1.0)
        )
        
        # DEBUG: Section'lar eklendi mi kontrol et
        logger.info(f"DEBUG: Sections in def_mgr: {list(builder.def_mgr.sections.keys())}")
        logger.info(f"DEBUG: Section names: {[s.name for s in builder.def_mgr.sections.values()]}")
        
        # ===== LINK PROPERTIES =====
        link1 = builder.create_link_prop(
            name="LINK1",
            prop_type=LinkPropType.LINEAR,
            Ke={"U1": 1000, "U2": 1000, "U3": 1000,
                "R1": 0, "R2": 0, "R3": 0}
        )
        
        # ===== NODELAR =====
        nodes = {}
        node_data = [
            (0, 0, 0, "N1", {"ux": True, "uy": True, "uz": True}),
            (5000, 0, 0, "N2", {"ux": True, "uy": True, "uz": True, "rx": True, "ry": True, "rz": True}),
            (0, 4000, 0, "N3", None),
            (5000, 4000, 0, "N4", {"uz": True}),
            (0, 0, 3000, "N5", None),
            (5000, 0, 3000, "N6", None),
            (0, 4000, 3000, "N7", None),
            (5000, 4000, 3000, "N8", None),
        ]
        
        for x, y, z, label, restraint in node_data:
            nodes[label] = builder.create_node(x, y, z, label, restraint)
        
        # ===== FRAMELER =====
        frame_data = [
            ("N5", "N6", "IPE300", 0, "B1"),
            ("N7", "N8", "IPE300", 0, "B2"),
            ("N1", "N5", "BOX400x15", 90, "C1"),
            ("N2", "N6", "BOX400x15", 90, "C2"),
            ("N3", "N7", "BOX400x15", 90, "C3"),
            ("N4", "N8", "BOX400x15", 90, "C4"),
        ]
        
        for i, j, sect, rot, label in frame_data:
            builder.create_frame(nodes[i], nodes[j], sect, rot, label)
        
        # ===== AREA =====
        builder.create_area(
            nodes=[nodes["N2"], nodes["N4"], nodes["N8"], nodes["N6"]],
            thickness=300,
            label="A1"
        )
        
        # ===== LINK =====
        builder.create_link(
            node_i=nodes["N5"],
            node_j=nodes["N8"],
            prop_name="LINK1",
            label="L1"
        )
        

        # ============================================================
        # GEÇİCİ — POLYGON RENDER TESTİ
        # ============================================================
        # Alt tabanda (Z=0) bir dörtgen poligon
        # Köşeler: N1(0,0,0), N2(5000,0,0), N4(5000,4000,0), N3(0,4000,0)
        from domain.element import Polygon
        
        test_poly = Polygon(
            [nodes["N1"], nodes["N2"], nodes["N4"], nodes["N3"], nodes["N8"]],
            label="TEST-POLYGON"
        )
        builder.scene.add_polygon(test_poly)
        # logger.debug(f"DEBUG: Test polygon eklendi - {len(test_poly.nodes)} köşe")

        return builder.scene

if __name__ == '__main__':
    from geometry.scenebuilder import SceneBuilder
    
    b = SceneBuilder()
    TestModelBuilder.build(b)