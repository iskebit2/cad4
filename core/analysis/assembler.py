# core/analysis/assembler.py
"""Global stiffness ve mass matrix montajı."""
import numpy as np
import logging

from core.analysis.element import local_stiffness, transformation_matrix

logger = logging.getLogger(__name__)


class ModelAssembler:
    """
    Scene'den global K ve M matrislerini üretir.
    
    Kullanım:
        asm = ModelAssembler(scene, node_map)
        asm.build_stiffness()
        asm.build_mass(mass_rules)
    """
    
    def __init__(self, scene, node_map, num_dofs):
        self.scene = scene
        self.node_map = node_map
        self.num_dofs = num_dofs
        
        self.K_global = np.zeros((num_dofs, num_dofs))
        self.M_global = np.zeros((num_dofs, num_dofs))
    
    # ---------------------------------------------------------
    # STIFFNESS
    # ---------------------------------------------------------
    
    def build_stiffness(self):
        """Tüm frame'lerden K_global üret."""
        self.K_global[:] = 0.0
        count = 0
        
        for f_id, frame in self.scene.frames.items():
            try:
                self._assemble_frame(frame)
                count += 1
            except Exception as e:
                logger.warning(f"Frame {f_id}: {e}")
        
        logger.info(f"[Assembler] {count} frame stiffness'e eklendi")
        return self.K_global
    
    def _assemble_frame(self, frame):
        """Tek frame için K_global'a katkı ekle."""
        sec = frame.section
        mat = sec.material if sec else None
        
        if not sec or not mat:
            return
        
        E = getattr(mat, 'E1', 2.1e5)
        G = getattr(mat, 'G12', 8.1e4)
        
        params = sec.profile_params
        A = params.get('Area', 1.0) * params.get('AMod', 1.0)
        J = params.get('J', 1.0) * params.get('JMod', 1.0)
        I33 = params.get('I33', 1.0) * params.get('I3Mod', 1.0)
        I22 = params.get('I22', 1.0) * params.get('I2Mod', 1.0)
        
        p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
        p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
        
        beta = getattr(frame, 'rotation_deg', 0.0)
        T, L = transformation_matrix(p1, p2, beta)
        
        k_loc = local_stiffness(
            E, G, A, J, I33, I22, L,
            release_i=getattr(frame, 'release_i', None),
            release_j=getattr(frame, 'release_j', None),
        )
        
        k_glob = T.T @ k_loc @ T
        
        dofs = frame.node_i.dof_indices + frame.node_j.dof_indices
        self.K_global[np.ix_(dofs, dofs)] += k_glob
    
    # ---------------------------------------------------------
    # MASS
    # ---------------------------------------------------------
    
    def build_mass(self, mass_source):
        """
        Mass source kuralına göre M_global üret.
        
        Parameters
        ----------
        mass_source : dict
            {
                'multipliers': {'D': 1.0, 'L': 0.3},
                'self_weight_mults': {'D': 1.0, 'L': 0.0},
                'frame_loads': {frame_id: [(pattern, value), ...]},
                'g': 9810.0,
            }
        """
        self.M_global[:] = 0.0
        
        multipliers = mass_source.get('multipliers', {})
        self_wt = mass_source.get('self_weight_mults', {})
        frame_loads = mass_source.get('frame_loads', {})
        g = mass_source.get('g', 9810.0)
        
        report = {'user': {}, 'self': {}}
        
        for f_id, frame in self.scene.frames.items():
            sec = frame.section
            mat = sec.material if sec else None
            if not sec or not mat:
                continue
            
            L = frame.get_length()
            s2k_id = frame.label[1:] if frame.label.startswith('F') else frame.label
            
            m_frame = 0.0
            
            # ---- Kullanıcı yayılı yükler ----
            for load in frame_loads.get(s2k_id, []):
                pattern = load['pattern']
                mult = multipliers.get(pattern, 0.0)
                if mult <= 0:
                    continue
                
                # Sadece düşey (Gravity/Z)
                d = load.get('direction', '').lower()
                if d not in ('gravity', 'z'):
                    continue
                
                force = load['value'] * L
                m_load = force / g
                
                m_frame += m_load * mult
                report['user'][pattern] = report['user'].get(pattern, 0.0) + m_load * mult
            
            # ---- Self weight ----
            rho = getattr(mat, 'density', 0.0)
            A = sec.profile_params.get('Area', 0.0)
            m_self = A * L * rho
            
            for pattern, swm in self_wt.items():
                if swm <= 0:
                    continue
                mult = multipliers.get(pattern, 0.0)
                if mult <= 0:
                    continue
                
                contribution = m_self * swm * mult
                m_frame += contribution
                report['self'][pattern] = report['self'].get(pattern, 0.0) + contribution
            
            # ---- Lump to nodes ----
            m_half = m_frame / 2.0
            for node in (frame.node_i, frame.node_j):
                if node.dof_indices is None:
                    continue
                for offset in (0, 1, 2):  # UX, UY, UZ
                    idx = node.dof_indices[offset]
                    self.M_global[idx, idx] += m_half
        
        total = sum(report['user'].values()) + sum(report['self'].values())
        logger.info(f"[Assembler] Toplam kütle: {total:.4f} ton")
        
        return self.M_global, report