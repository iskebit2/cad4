import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import math

# ----------------------------
# Birim şekiller (XY düzlemi, z=0)
# ----------------------------

segments = 16
radius = 1/2

shapes = {
    "triangle": np.array([[0,radius,0],[radius,-radius,0],[-radius,-radius,0]], dtype=np.float32),
    "square": np.array([[-radius,radius,0],[radius,radius,0],[radius,-radius,0],[-radius,-radius,0]], dtype=np.float32),
    "circle": np.array([[radius * np.cos(a), radius * np.sin(a), 0] 
                         for a in np.linspace(0, 2*np.pi, segments, endpoint=False)] + [[0,0,0]], dtype=np.float32)
}

# ----------------------------
# Rotation matrisleri
# ----------------------------
def local_matrix(x_= 0, y_= 0, z_= 0):
    theta_x = np.radians(x_)
    theta_y = np.radians(y_)
    theta_z = np.radians(z_)
    Rx = np.array([[1,0,0], [0,np.cos(theta_x),-np.sin(theta_x)], [0,np.sin(theta_x), np.cos(theta_x)]])
    Ry = np.array([[np.cos(theta_y),0,np.sin(theta_y)], [0,1,0], [-np.sin(theta_y),0,np.cos(theta_y)]])
    Rz = np.array([[np.cos(theta_z),-np.sin(theta_z),0], [np.sin(theta_z), np.cos(theta_z),0], [0,0,1]])
    return Rz @ Ry @ Rx # X→Y→Z dönüşümü

# ----------------------------
# Şekli döndür ve node pozisyonuna taşı
# ----------------------------
def transform_shape(shape, matrix, pos, z_offset=0):
    return (shape @ matrix.T) + pos + np.array([0,0,z_offset], dtype=np.float32)

# ----------------------------
# Restraint -> şekil belirleme fonksiyonu
# ----------------------------
def determine_support_symbols(restraint):
    symbols = {"x": None, "y": None, "z": None}
    if restraint is None or not restraint.get("uz", True):
        return symbols
    
    # X ekseni
    if not restraint.get("ux", True):
        symbols["x"] = "circle"
    else:
        symbols["x"] = "triangle" if not restraint.get("ry", False) else "square"
    
    # Y ekseni
    if not restraint.get("uy", True):
        symbols["y"] = "circle"
    else:
        symbols["y"] = "triangle" if not restraint.get("rx", False) else "square"
    
    # Z ekseni
    if restraint.get("uz", True):
        symbols["z"] = "square" if restraint.get("rz", False) else "circle"
    
    return symbols

# ----------------------------
# Node verisi
# ----------------------------
node_data = [
    (0, 0, 0, "N1", {"ux": True, "uy": False, "uz": True, "rz": True}),
    (2, 0, 0, "N2", {"ux": False, "uy": False, "uz": True, "rz": True}),
    (4, 0, 0, "N3", {"ux": False, "uy": False, "uz": True}),
    (6, 0, 0, "N4", {"ux": True, "uy": True, "uz": True}),
    (0, 2, 0, "N12", {"ux": True, "uy": False, "uz": True, "rx": True, "ry": True, "rz": True}),
    (2, 2, 0, "N22", {"ux": False, "uy": False, "uz": True, "rx": True, "ry": True, "rz": True}),
    (4, 2, 0, "N32", {"ux": False, "uy": False, "uz": True, "rx": True, "ry": True, "rz": True}),
    (6, 2, 0, "N42", {"ux": True, "uy": True, "uz": True, "rx": True, "ry": True, "rz": True}),
    (0, -2, 0, "N43", {"ux": False, "uy": False, "uz": False, "rx": False, "ry": False, "rz": False}),
    (2, -2, 0, "N44", {"ux": True, "uy": True, "uz": False, "rx": True, "ry": True, "rz": True}),
    (4, -2, 0, "N45", None)
]

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')



for x, y, z, name, restraint in node_data:
    pos = np.array([x, y, z], dtype=np.float32)
    symbols = determine_support_symbols(restraint)
    
    for axis, shape_name in symbols.items():
        if shape_name is None:
            continue
        if axis=="x":
            matrix = local_matrix(x_=90)
            offset= -0.5
        elif axis=="y":
            matrix = local_matrix(x_=90, z_=90)
            offset= -0.5
        else:
            matrix = local_matrix()
            offset= -1
        # Z ekseni sembolü altına taşı
        
        geom = transform_shape(shapes[shape_name], matrix, pos, z_offset=offset)
        ax.add_collection3d(Poly3DCollection([geom], alpha=0.5))

    # Node pozisyonu
    ax.scatter(*pos, color='black', s=50)

ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.set_box_aspect([1,1,0.5])
plt.axis('equal')
plt.show()