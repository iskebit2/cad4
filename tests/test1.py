import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.linalg import eigh
from tools.s2kloader import S2KLoader

# ==============================================================================
# 1. MATRİS YARDIMCI FONKSİYONLARI
# ==============================================================================

def get_3d_frame_local_stiffness(E, G, A, J, I33, I22, L,
                                   release_i=None, release_j=None):
    """
    3D çubuk eleman lokal rijitlik matrisi (12x12).
    
    release_i / release_j: dict {"R1": bool, ..., "R6": bool} veya None
      R1 = P   (eksenel)
      R2 = V2  (kesme Y)
      R3 = V3  (kesme Z)
      R4 = T   (burulma)
      R5 = M2  (moment Y)
      R6 = M3  (moment Z)
    """
    k = np.zeros((12, 12))
    EA_L = E * A / L
    GJ_L = G * J / L
    
    # Release flag'lerini kolaylaştır (default: False)
    def rel(d, code):
        return d is not None and d.get(code, False)
    
    ri = release_i or {}
    rj = release_j or {}
    
    # ---- Eksenel (UX - local 0, 6) ----
    if not (rel(ri, 'R1') or rel(rj, 'R1')):
        k[0, 0] = k[6, 6] = EA_L
        k[0, 6] = k[6, 0] = -EA_L
    
    # ---- Burulma (RX - local 3, 9) ----
    if not (rel(ri, 'R4') or rel(rj, 'R4')):
        k[3, 3] = k[9, 9] = GJ_L
        k[3, 9] = k[9, 3] = -GJ_L
    
    # ---- Local z etrafında eğilme (I22 → UY, RZ) ----
    # R6 = M3 (moment Z) → UY-RZ düzlemi
    rz_release_i = rel(ri, 'R6')
    rz_release_j = rel(rj, 'R6')
    
    if not (rz_release_i and rz_release_j):
        EIz_L3   = 12 * E * I22 / (L ** 3)
        EIz_L2   = 6  * E * I22 / (L ** 2)
        EIz_L    = 4  * E * I22 / L
        EIz_L_h  = 2  * E * I22 / L
        
        # Eğer sadece bir uç release ise → modified stiffness
        if rz_release_i and not rz_release_j:
            # i ucu pin, j ucu fixed → 3EI/L modifiye
            EIz_L3  = 3 * E * I22 / (L ** 3)
            EIz_L2  = 3 * E * I22 / (L ** 2)
            EIz_L   = 3 * E * I22 / L
            EIz_L_h = 0
        
        elif rz_release_j and not rz_release_i:
            EIz_L3  = 3 * E * I22 / (L ** 3)
            EIz_L2  = 3 * E * I22 / (L ** 2)
            EIz_L   = 3 * E * I22 / L
            EIz_L_h = 0
        
        k[1, 1] = k[7, 7] = EIz_L3
        k[1, 7] = k[7, 1] = -EIz_L3
        k[1, 5] = k[5, 1] = k[1, 11] = k[11, 1] = EIz_L2
        k[5, 7] = k[7, 5] = k[7, 11] = k[11, 7] = -EIz_L2
        k[5, 5] = k[11, 11] = EIz_L
        k[5, 11] = k[11, 5] = EIz_L_h
    
    # ---- Local y etrafında eğilme (I33 → UZ, RY) ----
    # R5 = M2 (moment Y) → UZ-RY düzlemi
    ry_release_i = rel(ri, 'R5')
    ry_release_j = rel(rj, 'R5')
    
    if not (ry_release_i and ry_release_j):
        EIy_L3   = 12 * E * I33 / (L ** 3)
        EIy_L2   = 6  * E * I33 / (L ** 2)
        EIy_L    = 4  * E * I33 / L
        EIy_L_h  = 2  * E * I33 / L
        
        if ry_release_i and not ry_release_j:
            EIy_L3  = 3 * E * I33 / (L ** 3)
            EIy_L2  = 3 * E * I33 / (L ** 2)
            EIy_L   = 3 * E * I33 / L
            EIy_L_h = 0
        
        elif ry_release_j and not ry_release_i:
            EIy_L3  = 3 * E * I33 / (L ** 3)
            EIy_L2  = 3 * E * I33 / (L ** 2)
            EIy_L   = 3 * E * I33 / L
            EIy_L_h = 0
        
        k[2, 2] = k[8, 8] = EIy_L3
        k[2, 8] = k[8, 2] = -EIy_L3
        k[2, 4] = k[4, 2] = k[2, 10] = k[10, 2] = -EIy_L2
        k[4, 8] = k[8, 4] = k[8, 10] = k[10, 8] = EIy_L2
        k[4, 4] = k[10, 10] = EIy_L
        k[4, 10] = k[10, 4] = EIy_L_h
    
    return k


def get_transformation_matrix_3d(node1, node2, beta_deg=0):
    """Lokal eksenlerden Global eksenlere dönüşüm matrisi (12x12)"""
    p1, p2 = np.array(node1), np.array(node2)
    v = p2 - p1
    L = np.linalg.norm(v)
    if L < 1e-9:
        raise ValueError("Sıfır uzunluklu çubuk eleman tespit edildi!")

    dx, dy, dz = v / L
    vx = np.array([dx, dy, dz])
    beta = np.radians(beta_deg)

    # Dikey elemanlar için özel durum (SAP2000 Uyumlu)
    if np.isclose(np.abs(dz), 1.0, atol=1e-5):
        sign = 1.0 if dz > 0 else -1.0
        vy0 = np.array([0, sign, 0])
        vz0 = np.array([-sign, 0, 0])
        R_0 = np.vstack([vx, vy0, vz0])
    else:
        D = np.sqrt(dx**2 + dy**2)
        vy0 = np.array([-dy / D, dx / D, 0])
        vz0 = np.array([-dx * dz / D, -dy * dz / D, D])
        R_0 = np.vstack([vx, vy0, vz0])

    R_beta = np.array([
        [1, 0, 0],
        [0, np.cos(beta), np.sin(beta)],
        [0, -np.sin(beta), np.cos(beta)]
    ])
    R_local = R_beta @ R_0

    T = np.zeros((12, 12))
    for i in range(4):
        T[i * 3:(i + 1) * 3, i * 3:(i + 1) * 3] = R_local

    return T, L


# ==============================================================================
# 2. MODEL YÜKLEME VE GLOBAL DOF ATAMASI
# ==============================================================================
file_path = "examples/testmodel.s2k"
app = S2KLoader(file_path)



df_mass = app.parser.get_table("MASS SOURCE")
df_lp = app.parser.get_table("LOAD PATTERN DEFINITIONS")
df_fl = app.parser.get_table("FRAME LOADS - DISTRIBUTED")
df_jl = app.parser.get_table("JOINT LOADS - FORCE")
df_al = app.parser.get_table("AREA LOADS - UNIFORM TO FRAME")


def run():
    results = app.load()

    points = results.nodes     # Dict[str/int, Node]
    frames = results.frames    # Dict[str/int, Frame]
    links = results.links      # Dict[str/int, Link]
    areas = results.areas      # Dict[str/int, Area]

    node_keys = list(points.keys())
    node_map = {key: i for i, key in enumerate(node_keys)}

    num_nodes = len(points)
    num_dofs = num_nodes * 6

    # Düğümlerin dof_indices attribute'unu dolduralım
    for key, node in points.items():
        base_idx = node_map[key] * 6
        node.dof_indices = list(range(base_idx, base_idx + 6))

    # ==============================================================================
    # 3. GLOBAL RİJİTLİK MATRİSİ MONTAJI
    # ==============================================================================
    K_global = np.zeros((num_dofs, num_dofs))
    sayac=0
    for f_id, frame in frames.items():
        sayac+=1
        
        # print(frame.label, frame.section.name, frame.section.profile_type)
        node_i = frame.node_i
        node_j = frame.node_j

        p1_coords = [node_i.x, node_i.y, node_i.z]
        p2_coords = [node_j.x, node_j.y, node_j.z]

        sec = frame.section
        mat = getattr(sec, 'material', None) if sec else None

        E = getattr(mat, 'E1', getattr(mat, 'E', 2.1e8))
        G = getattr(mat, 'G12', getattr(mat, 'G', 8.1e7))

        params = getattr(sec, 'profile_params', {}) if sec else {}
        # print("Area:", params.get('Area', 0.01), params)
        A  = params.get('Area', 0.01) * params.get('AMod', 1.0)
        J  = params.get('J', 1.0e-5) * params.get('JMod', 1.0)        # TorsConst doğrudan burada!
        I33 = params.get('I33', 1.0e-4) * params.get('I3Mod', 1.0)     # SAP2000 I33 = Local y etrafı
        I22 = params.get('I22', 1.0e-4) * params.get('I2Mod', 1.0)     # SAP2000 I22 = Local z etrafı

        beta = getattr(frame, 'beta', 0.0)
        T, L = get_transformation_matrix_3d(p1_coords, p2_coords, beta_deg=beta)

        k_loc = get_3d_frame_local_stiffness(
                                                E, G, A, J, I33, I22, L,
                                                release_i=frame.release_i,
                                                release_j=frame.release_j,
                                            )
        
        k_glob = T.T @ k_loc @ T

        dof_indices = node_i.dof_indices + node_j.dof_indices
        K_global[np.ix_(dof_indices, dof_indices)] += k_glob

        # 3D Beam Local Stiffness Diagonal (0..5):
        # 0: UX (Eksenel)    = A * E / L
        # 1: UY (Kesme Y)    = 12 * E * I33 / L**3  (veya Timoshenko katsayısı ile)
        # 2: UZ (Kesme Z)    = 12 * E * I22 / L**3
        # 3: RX (Burulma)    = G * J / L
        # 4: RY (Eğilme Z)   = 4 * E * I22 / L
        # 5: RZ (Eğilme Y)   = 4 * E * I33 / L
        # print(f"A = {A}, E= {E}, L= {L}, , J= {J}, I33= {I33}, I22= {I22}")
        # print(f"UX (Eksenel) = {A * E / L}")
        # print(f"UY (Kesme Y) = {12 * E * I33 / L**3}")
        # print(f"UZ (Kesme Z) = {12 * E * I22 / L**3}")
        # print(f"RX (Burulma) = {G * J / L}")
        # print(f"RY (Eğilme Z) = {4 * E * I22 / L}")
        # print(f"RZ (Eğilme Y) = {4 * E * I33 / L}")
        # print("Lokal k_loc diyagonali:", np.diag(k_loc))
        # print("Global k_glob diyagonali:", np.diag(k_glob))
        # print("DOF Indeksleri:", dof_indices)

        


        

    # Serbest dönme serbestliklerinde matris tekilliğini önlemek için zayıf tutma
    for i in range(num_nodes):
        for rx_ry_rz in [3, 4, 5]:
            dof_idx = i * 6 + rx_ry_rz
            K_global[dof_idx, dof_idx] += 1e-3

    print(f"--- SİSTEM BİLGİLERİ ---")
    print(f"Düğüm Sayısı: {num_nodes} | Çubuk Sayısı: {len(frames)} | DOFs: {num_dofs}")
    print(f"Simetri Doğrulaması: {np.allclose(K_global, K_global.T)}")

    # ==============================================================================
    # 4. RESTRAINT VE MESNET TESPİTİ
    # ==============================================================================
    fixed_node_keys = []
    fixed_dofs = []

    for key, node in points.items():
        if node.restraint:
            fixed_node_keys.append(key)
            base_idx = node_map[key] * 6
            for i, dof_name in enumerate(node.DOF_ORDER):
                if getattr(node.restraint, dof_name, False):
                    fixed_dofs.append(base_idx + i)

    all_dofs = set(range(num_dofs))
    free_dofs = sorted(list(all_dofs - set(fixed_dofs)))

    print(f"Kilitli Düğüm Sayısı: {len(fixed_node_keys)} | Kilitli DOF: {len(fixed_dofs)} | Serbest DOF: {len(free_dofs)}")

    # ==============================================================================
    # 5. STATİK ANALİZ
    # ==============================================================================
    F_static = np.zeros(num_dofs)

    # En üst kattaki ilk serbest düğüme 1 kN X yükü uygulaması
    z_coords = [n.z for n in points.values()]
    max_z = max(z_coords)
    top_nodes = [k for k, n in points.items() if np.isclose(n.z, max_z) and k not in fixed_node_keys]

    if top_nodes:
        top_dof = node_map[top_nodes[0]] * 6
        F_static[top_dof] = 1000.0  # N

    K_reduced = K_global[np.ix_(free_dofs, free_dofs)]

    # Solve işleminden hemen önce ekle:
    zero_diag = np.where(np.abs(np.diag(K_reduced)) < 1e-9)[0]
    if len(zero_diag) > 0:
        print(f"⚠️ DİKKAT: K_reduced matrisinde sıfır diyagonale sahip DOF indeksleri: {zero_diag}")

    print("\n--- RİJİTLİK MATRİSİ TEŞHİSİ ---")
    print("K max:", np.max(np.abs(K_reduced)))
    print("K min abs:", np.min(np.abs(K_reduced)))
    print("Sonlu değerler:", np.isfinite(K_reduced).all())
    print("Simetrik:", np.allclose(K_reduced, K_reduced.T))

    # Matrisin koşul sayısı
    print("Koşul sayısı:", np.linalg.cond(K_reduced))

    # Küçük sistemlerde değil, bu boyutta yalnızca teşhis amacıyla
    # simetrik matrisin en küçük özdeğerlerini incele
    eig_min = np.linalg.eigvalsh(K_reduced)[:10]
    print("En küçük 10 rijitlik özdeğeri:")
    print(eig_min)


    F_reduced = F_static[free_dofs]
    U_reduced = np.linalg.solve(K_reduced, F_reduced)

    U_static = np.zeros(num_dofs)
    U_static[free_dofs] = U_reduced

    print(f"\n--- STATİK ANALİZ SONUCU ---")
    if top_nodes:
        print(f"Tepe Düğüm ({top_nodes[0]}) UX Deplasmanı: {U_static[top_dof]:.4f} mm")

    # ==============================================================================
    # 6. KÜTLE MATRİSİ VE MODAL ANALİZ
    # ==============================================================================

    # # M_global'i sıfırla
    # # Kütle matrisini oluştur
    # M_global = np.zeros((num_dofs, num_dofs))

    # for f_id, frame in frames.items():
    #     sec = frame.section
    #     mat = getattr(sec, 'material', None) if sec else None
        
    #     # Yoğunluk (SAP2000'den gelen UnitMass)
    #     # SAP2000 UnitMass birimi genelde t/m³ veya kg/m³ — kontrol et!
    #     rho = getattr(mat, 'density', 7.85e-9)  # t/mm³
        
    #     # print(f"Material: {mat.name}, density={mat.density if mat else None}")
    #     params = getattr(sec, 'profile_params', {}) if sec else {}
    #     A = params.get('Area', 0.0)  # mm²
        
    #     # Çubuk uzunluğu
    #     L = frame.get_length()  # mm
        
    #     # Elemanın toplam kütlesi (ton)
    #     m_element = A * L * rho  # mm² × mm × t/mm³ = t
        
    #     # Yarısı her uca (lumped mass)
    #     m_half = m_element / 2.0
        
    #     # DOF indeksleri doğrudan node'dan
    #     for node in (frame.node_i, frame.node_j):
    #         if node.dof_indices is None:
    #             continue
    #         for dof_offset in (0, 1, 2):  # UX, UY, UZ
    #             idx = node.dof_indices[dof_offset]
    #             M_global[idx, idx] += m_half

    # total_mass = 0.0
    # for f_id, frame in frames.items():
    #     sec = frame.section
    #     mat = getattr(sec, 'material', None) if sec else None
    #     rho = getattr(mat, 'UnitMass', 7.85e-9)
    #     A = sec.profile_params.get('Area', 0)
    #     L = frame.get_length()
    #     total_mass += A * L * rho

        
    #     # print(f"f_id:{f_id}, rho= {rho}, A= {A}, L= {L}, mass={A * L * rho:.2f} ton")
    # print(f"Toplam yapı kütlesi: {total_mass:.2f} ton")

    # # Kütle matrisinin kontrolü
    # diag_mass = np.diag(M_global)
    # print(f"Toplam M diyagonal (UX): {diag_mass[0::6].sum():.2f} ton")
    # print(f"Toplam M diyagonal (UY): {diag_mass[1::6].sum():.2f} ton")
    # print(f"Toplam M diyagonal (UZ): {diag_mass[2::6].sum():.2f} ton")
    # print(f"Sıfır kütleli UX DOF sayısı: {np.sum(diag_mass[0::6] == 0)}")



    # ============================================================
    # KÜTLE MATRİSİ — SAP2000 MASS SOURCE KURALI
    # ============================================================
    # 
    # SAP2000 mass source:
    #   Elements: No       (eleman öz kütlesi kullanılmıyor)
    #   Loads:    Yes      (yükten kütle)
    #   D × 1.0
    #   L × 0.3

    print("\n=== MASS SOURCE ANALİZİ ===")
    df_mass = app.parser.get_table("MASS SOURCE")
    print(df_mass)

    # Mass source multipliers
    mass_multipliers = {}
    if not df_mass.empty:
        for _, row in df_mass.iterrows():
            pattern = str(row.get('LoadPat', '')).strip()
            mult = row.get('Multiplier')
            if pattern and mult is not None:
                try:
                    mass_multipliers[pattern] = float(mult)
                except (ValueError, TypeError):
                    pass
    print(f"Kütle çarpanları: {mass_multipliers}")

    # Load pattern SelfWtMult
    print("\n=== LOAD PATTERN DEFINITIONS ===")
    df_lp = app.parser.get_table("LOAD PATTERN DEFINITIONS")
    print(df_lp[['LoadPat', 'DesignType', 'SelfWtMult']] if not df_lp.empty else "BOŞ")

    self_wt_mults = {}   # {pattern: SelfWtMult}
    if not df_lp.empty:
        for _, row in df_lp.iterrows():
            pattern = str(row.get('LoadPat', '')).strip()
            swm = row.get('SelfWtMult', 0.0)
            try:
                self_wt_mults[pattern] = float(swm)
            except (ValueError, TypeError):
                self_wt_mults[pattern] = 0.0
    print(f"SelfWtMult: {self_wt_mults}")

    # Frame yayılı yükleri
    df_dist_loads = app.parser.get_table("FRAME LOADS - DISTRIBUTED")

    # Frame ID → [(pattern, dir, value), ...]
    frame_loads = {}
    if not df_dist_loads.empty:
        for _, row in df_dist_loads.iterrows():
            frame_id = str(row.get('Frame', '')).strip()
            pattern = str(row.get('LoadPat', '')).strip()
            direction = str(row.get('Dir', '')).strip()
            
            # FOverLA ve FOverLB → yayılı yük (N/mm)
            foverA = row.get('FOverLA')
            foverB = row.get('FOverLB')
            
            try:
                value = float(foverA) if foverA is not None and str(foverA) != 'nan' else 0.0
            except (ValueError, TypeError):
                value = 0.0
            
            if frame_id and pattern:
                frame_loads.setdefault(frame_id, []).append({
                    'pattern': pattern,
                    'direction': direction,
                    'value': value,
                })

    # ============================================================
    # KÜTLE HESABI
    # ============================================================
    g_mm_s2 = 9810.0   # mm/s²

    M_global = np.zeros((num_dofs, num_dofs))

    # Debug sayaçlar
    m_total_by_pattern_user = {}    # Kullanıcı yükünden
    m_total_by_pattern_self = {}    # Self weight'ten

    print("\n=== KÜTLE HESABI ===")

    # ---------- Adım 1: Her frame için kütle ----------
    for f_id, frame in frames.items():
        sec = frame.section
        mat = sec.material if sec else None
        if not sec or not mat:
            continue
        
        L = frame.get_length()   # mm
        
        # Frame'in S2K ID'si
        label = frame.label
        s2k_frame_id = label[1:] if label.startswith('F') else label
        
        # Bu frame'in yükleri
        loads = frame_loads.get(s2k_frame_id, [])
        
        # Bu frame'in toplam kütlesi (ton)
        m_frame_total = 0.0
        
        # --- Kullanıcı yayılı yükleri ---
        for load in loads:
            pattern = load['pattern']
            mult = mass_multipliers.get(pattern, 0.0)
            if mult <= 0:
                continue
            
            # Kütle sadece düşey yönde (Gravity / Z)
            if load['direction'].lower() not in ('gravity', 'z'):
                continue
            
            force = load['value'] * L   # N
            m_load = force / g_mm_s2    # ton
            
            m_frame_total += m_load * mult
            m_total_by_pattern_user[pattern] = (
                m_total_by_pattern_user.get(pattern, 0.0) + m_load * mult
            )
        
        # --- Self weight (eleman öz ağırlığı) ---
        # Her pattern için SelfWtMult × self_mass katkısı
        rho = getattr(mat, 'density', 0.0)   # t/mm³
        A = sec.profile_params.get('Area', 0.0)   # mm²
        m_self = A * L * rho   # ton
        
        for pattern, swm in self_wt_mults.items():
            if swm <= 0:
                continue
            mult = mass_multipliers.get(pattern, 0.0)
            if mult <= 0:
                continue
            
            m_self_contribution = m_self * swm * mult
            m_frame_total += m_self_contribution
            m_total_by_pattern_self[pattern] = (
                m_total_by_pattern_self.get(pattern, 0.0) + m_self_contribution
            )
        
        # Yarısı her uca
        m_half = m_frame_total / 2.0
        for node in (frame.node_i, frame.node_j):
            if node.dof_indices is None:
                continue
            for dof_offset in (0, 1, 2):
                idx = node.dof_indices[dof_offset]
                M_global[idx, idx] += m_half

    # ---------- Rapor ----------
    print(f"\nKullanıcı yükünden:")
    for pat, m in m_total_by_pattern_user.items():
        print(f"  {pat}: {m:.4f} ton")

    print(f"\nSelf weight'ten:")
    for pat, m in m_total_by_pattern_self.items():
        print(f"  {pat}: {m:.4f} ton")

    toplam = sum(m_total_by_pattern_user.values()) + sum(m_total_by_pattern_self.values())
    print(f"\nToplam yapı kütlesi: {toplam:.4f} ton")

    diag_mass = np.diag(M_global)
    print(f"Toplam M diyagonal (UX): {diag_mass[0::6].sum():.4f} ton")

    zero_mass_ux = np.sum(diag_mass[0::6] == 0)
    print(f"Sıfır kütleli UX DOF sayısı: {zero_mass_ux}")




    # Modal analize yalnızca öteleme serbestlikleri (UX, UY, UZ) girer
    free_dofs_modal = [dof for dof in free_dofs if dof % 6 in [0, 1, 2]]

    K_modal = K_global[np.ix_(free_dofs_modal, free_dofs_modal)]
    M_modal = M_global[np.ix_(free_dofs_modal, free_dofs_modal)]

    eigenvalues, eigenvectors = eigh(K_modal, M_modal)

    omega = np.sqrt(np.maximum(1e-9, eigenvalues))
    freqs = omega / (2 * np.pi)
    periods = np.where(freqs > 1e-4, 1.0 / freqs, 0.0)


    print("Kilitli DOF sayısı:", len(fixed_dofs))
    print("Serbest DOF sayısı:", len(free_dofs))

    # Sıfıra yakın özdeğerlerin sayısı
    eigvals = np.linalg.eigvalsh(K_reduced)
    tol = max(np.max(np.abs(eigvals)) * 1e-10, 1e-12)

    print("En küçük özdeğer:", eigvals[0])
    print("En büyük özdeğer:", eigvals[-1])
    print("Tolerans:", tol)
    print("Tolerans altındaki özdeğer sayısı:", np.sum(eigvals < tol))



    print("\n--- MODAL ANALİZ SONUÇLARI ---")
    for i in range(min(5, len(freqs))):
        print(f"Mod {i+1}: Frekans = {freqs[i]:.3f} Hz | Periyot = {periods[i]:.4f} s")




    # ==============================================================================
    # GUYAN KONDANSASYON (SAYISAL OLARAK KARARLI KOD)
    # ==============================================================================

    master_dofs = [dof for dof in free_dofs if dof % 6 in [0, 1, 2]]  # UX, UY, UZ
    slave_dofs  = [dof for dof in free_dofs if dof % 6 in [3, 4, 5]]  # RX, RY, RZ

    K_tt = K_global[np.ix_(master_dofs, master_dofs)]
    K_tr = K_global[np.ix_(master_dofs, slave_dofs)]
    K_rt = K_global[np.ix_(slave_dofs, master_dofs)]
    K_rr = K_global[np.ix_(slave_dofs, slave_dofs)]

    # K_rr matrisinin sıfır/zayıf kalmasını engellemek için küçük düzenleme (Regularization)
    # pinv KULLANMADAN doğrudan solve yapıyoruz ki çıkarım matrisi pozitif kalabilsin
    diag_addition = np.eye(K_rr.shape[0]) * 1.0  # 1.0 N.mm/rad mertebesinde hafif stabilization
    K_rr_stiff = K_rr + diag_addition

    # Kondansasyon işlemi
    K_rr_inv_K_rt = np.linalg.solve(K_rr_stiff, K_rt)
    K_condensed = K_tt - (K_tr @ K_rr_inv_K_rt)

    # Kütle matrisi (sadece master)
    M_condensed = M_global[np.ix_(master_dofs, master_dofs)]

    # Özdeğer çözümü
    eigenvalues, eigenvectors = eigh(K_condensed, M_condensed)

    # Sadece POZİTİF olan gerçek modları al (Sayısal gürültü/rijit modları ele)
    valid_mask = eigenvalues > 0.1  # w^2 > 0.1 rad^2/s^2 altı sayısal çöp
    valid_eig = eigenvalues[valid_mask]

    omega = np.sqrt(valid_eig)
    freqs = omega / (2 * np.pi)
    periods = 1.0 / freqs

    print("\n--- GUYAN KONDANSASYONLU MODAL ANALİZ SONUÇLARI ---")
    for i in range(min(5, len(periods))):
        print(f"Mod {i+1}: Frekans = {freqs[i]:.3f} Hz | Periyot = {periods[i]:.4f} s")



    # ==============================================================================
    # 7. TBDY 2018 PARAMETRİK SPEKTRUM VE SPEKTRAL ANALİZ (SRSS)
    # ==============================================================================

    # S2K tablolarından spektrum ve katsayı çekimi
    df_spec = app.parser.get_table("FUNCTION - RESPONSE SPECTRUM - TSC-2018")
    df_seismic = app.parser.get_table("AUTO SEISMIC - TSC-2018")

    # Varsayılan parametreler (Tablo boşsa fallback)
    Ss, S1 = 0.905, 0.254
    Fs, F1 = 1.138, 2.092
    R, D_coef, I_coef = 4.0, 2.5, 1.2
    TL = 6.0

    if not df_seismic.empty:
        row = df_seismic.iloc[0]
        Ss = float(row.get('Ss', Ss))
        S1 = float(row.get('S1', S1))
        Fs = float(row.get('Fs', Fs))
        F1 = float(row.get('F1', F1))
        R  = float(row.get('R', R))
        D_coef = float(row.get('D', D_coef))
        I_coef = float(row.get('I', I_coef))
        TL = float(row.get('TL', TL))

    # TBDY 2018 İvme Katsayıları ve Köşe Periyotları
    S_DS = Ss * Fs    # SDS = 0.905 * 1.138 = 1.0299
    S_D1 = S1 * F1    # SD1 = 0.254 * 2.092 = 0.5314

    T_B = S_D1 / S_DS  # TB köşe periyodu
    T_A = 0.2 * T_B    # TA köşe periyodu
    g = 9810.0         # mm/s²

    print("\n=== TBDY 2018 DEPREM PARAMETRELERİ ===")
    print(f"S_DS: {S_DS:.4f} | S_D1: {S_D1:.4f}")
    print(f"T_A : {T_A:.4f} s | T_B : {T_B:.4f} s | T_L : {TL:.1f} s")
    print(f"R   : {R:.1f}    | D   : {D_coef:.1f}   | I   : {I_coef:.1f}")

    def get_S_ra(T):
        """TBDY 2018 Denklem 2.1 ve 4.1'e göre Azaltılmış Tasarım Spektral İvmesi"""
        if T <= 0.0:
            T = 1e-4

        # 1. Yatay Tasarım Spektral İvmesi Sae(T) (TBDY 2018 Denklem 2.1)
        if T <= T_A:
            S_ae = (0.4 + 0.6 * (T / T_A)) * S_DS
        elif T <= T_B:
            S_ae = S_DS
        elif T <= TL:
            S_ae = S_D1 / T
        else:
            S_ae = (S_D1 * TL) / (T**2)

        # 2. Deprem Yükü Azaltma Katsayısı Ra(T) (TBDY 2018 Denklem 4.1)
        if T <= T_B:
            R_a = D_coef + (R / I_coef - D_coef) * (T / T_B)
        else:
            R_a = R / I_coef

        # 3. Azaltılmış Spektral İvme Sra(T)
        return S_ae / R_a

    # --- MODAL SPEKTRAL BİRLEŞTİRME (SRSS) ---
    # Master DOFs (UX, UY, UZ) üzerinden mod şekillerini kullanıyoruz
    r_x_modal = np.zeros(len(master_dofs))
    for idx, dof in enumerate(master_dofs):
        if dof % 6 == 0:  # X yönü ötelemeleri
            r_x_modal[idx] = 1.0

    U_modes = []
    num_modes_to_use = min(6, len(periods))

    for n in range(num_modes_to_use):
        phi_n = eigenvectors[:, n]  # Master DOF seviyesindeki mod şekli
        T_n = periods[n]
        
        # Mod kütlesi ve katılım çarpanı
        M_n = phi_n.T @ M_condensed @ phi_n
        L_n = phi_n.T @ M_condensed @ r_x_modal
        Gamma_n = L_n / M_n if M_n > 0 else 0.0

        # Spektral ivme (g biriminde -> mm/s²)
        S_ra = get_S_ra(T_n)
        S_a_mms2 = S_ra * g

        # Moda ait öteleme vektörü
        w_n2 = (2 * np.pi / T_n)**2 if T_n > 0 else 1.0
        u_n_master = Gamma_n * (S_a_mms2 / w_n2) * phi_n

        # Full DOF'a geri genişletme
        u_n_full = np.zeros(num_dofs)
        u_n_full[master_dofs] = u_n_master
        U_modes.append(u_n_full)

    # SRSS Birleştirme
    U_SRSS = np.sqrt(np.sum([u**2 for u in U_modes], axis=0))

    print("\n--- SPEKTRAL ANALİZ SONUÇLARI (TBDY 2018 SRSS) ---")
    if top_nodes:
        top_ux_idx = node_map[top_nodes[0]] * 6
        print(f"Tepe Düğümü Maksimum Deprem Ötelemesi (UX): {U_SRSS[top_ux_idx]:.2f} mm")

    # ==============================================================================
    # 8. TBDY 2018 EŞDEĞER DEPREM YÜKÜ YÖNTEMİ
    # ==============================================================================

    print("\n=== EŞDEĞER DEPREM YÜKÜ HESABI (TBDY 2018) ===")

    # 1. Birinci Mod Periyodu T1 (Guyan veya Modal Analizden)
    T1 = periods[0] if len(periods) > 0 else 0.25

    # 2. Toplam Yapı Kütlesi (ton)
    m_total = np.sum(np.diag(M_condensed))  # Master DOF kütle toplamı (UX/UY/UZ bağımsız tekil kütle) / 3
    # Ya da M_global üzerinden X yönündeki kütlelerin toplamı:
    m_total_x = np.sum(np.diag(M_global)[0::6])   # ton

    # 3. Birinci Periyoda Karşılık Gelen Azaltılmış Spektral İvme Sra(T1)
    S_ra_T1 = get_S_ra(T1)

    # 4. Taban Kesme Kuvveti Vt = m * Sra(T1) * g (N biriminde)
    V_t = m_total_x * S_ra_T1 * g   # ton * g_mm_s2 = N

    # TBDY 2018 Min. Taban Kesme Kuvveti Kontrolü (Denklem 4.19)
    # Vt_min = 0.04 * m * SDS * I * g
    V_t_min = 0.04 * m_total_x * S_DS * I_coef * g

    V_t_design = max(V_t, V_t_min)

    print(f"Birinci Mod Periyodu (T1): {T1:.4f} s")
    print(f"Toplam Etkin Kütle (m)  : {m_total_x:.4f} ton")
    print(f"S_ra(T1) İvme Katsayısı : {S_ra_T1:.4f} g")
    print(f"Hesaplanan Vt           : {V_t / 1000.0:.2f} kN")
    print(f"Minimum Vt Sınırı       : {V_t_min / 1000.0:.2f} kN")
    print(f"Tasarım Taban Kesmesi   : {V_t_design / 1000.0:.2f} kN")

    # 5. Kat/Düğüm Seviyelerine Yük Dağıtımı (F_i)
    # F_i = (V_t - ΔV_tn) * (m_i * z_i) / Σ(m_j * z_j)
    # (Çatı için ΔV_tn = 0.007 * N_kat * V_t, tek katlı veya alçak yapılarda genelde 0 alınır)

    # Düğümlerin z yüksekliklerini ve kütlelerini eşleme
    F_equivalent = np.zeros(num_dofs)

    # Sadece serbest öteleme düğümlerinin X yönüne kütle × yükseklik oranında dağıtım
    node_mass_z = {}
    for key, node in points.items():
        if key in fixed_node_keys:
            continue
        base_idx = node_map[key] * 6
        node_m = M_global[base_idx, base_idx]  # Bu düğümdeki kütle (ton)
        if node_m > 0 and node.z > 0:
            node_mass_z[key] = node_m * node.z

    sum_m_z = sum(node_mass_z.values())

    if sum_m_z > 0:
        for key, m_z in node_mass_z.items():
            base_idx = node_map[key] * 6
            # X yönündeki düğüm eşdeğer deprem yükü (N)
            F_equivalent[base_idx] = V_t_design * (m_z / sum_m_z)

    # 6. Eşdeğer Deprem Yükü Altında Statik Deplasman Hesabı
    F_eq_reduced = F_equivalent[free_dofs]
    U_eq_reduced = np.linalg.solve(K_reduced, F_eq_reduced)

    U_eq_static = np.zeros(num_dofs)
    U_eq_static[free_dofs] = U_eq_reduced

    print("\n--- EŞDEĞER DEPREM YÜKÜ DEPLASMAN SONUÇLARI ---")
    if top_nodes:
        top_ux_idx = node_map[top_nodes[0]] * 6
        print(f"Tepe Düğümü Eşdeğer Deprem Ötelemesi (UX): {U_eq_static[top_ux_idx]:.2f} mm")


run()
# print("\n=== Yüklü Tablolar (LOAD içeren) ===")
# for name in sorted(app.parser.tables.keys()):
#     if 'LOAD' in name.upper() or 'MASS' in name.upper():
#         n = len(app.parser.tables[name])
#         print(f"  {name}: {n} rows")


# for table_key in ["FUNCTION - RESPONSE SPECTRUM - TSC-2018", "AUTO SEISMIC - TSC-2018"]:
#     print(f"=== {table_key} ===")
#     df = app.parser.get_table(table_key)
#     print(df.columns.tolist())
#     print(df.head(5))

