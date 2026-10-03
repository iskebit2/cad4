#geometry/spatialgrid.py

from typing import Dict, List, Tuple, Set, Optional, Union
import numpy as np
from dataclasses import dataclass
from enum import Enum

from domain.definition import ElementType
from logging_config import CadLogger
from logging_config import CadLogger

logger = CadLogger.get(__name__)

@dataclass
class BoundingBox:
    """Min-max bounding box"""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    
    @classmethod
    def from_list(cls, vertices: List[float]) -> 'BoundingBox':
        """Vertex listesinden bounding box oluştur"""
        if not vertices:
            return cls(0, 0, 0, 0, 0, 0)
        
        # Her 7 eleman: x,y,z,r,g,b,a
        xs = vertices[0::7]
        ys = vertices[1::7]
        zs = vertices[2::7]
        
        return cls(
            min_x=min(xs), min_y=min(ys), min_z=min(zs),
            max_x=max(xs), max_y=max(ys), max_z=max(zs)
        )
    
    def get_center(self) -> Tuple[float, float, float]:
        """Merkez noktayı döndür"""
        return (
            (self.min_x + self.max_x) * 0.5,
            (self.min_y + self.max_y) * 0.5,
            (self.min_z + self.max_z) * 0.5
        )
    
    def get_size(self) -> Tuple[float, float, float]:
        """Boyutları döndür"""
        return (
            self.max_x - self.min_x,
            self.max_y - self.min_y,
            self.max_z - self.min_z
        )

class SpatialGrid:
    """
    Uzaysal bölmeleme grid'i
    - Model yükleme anında 1 kez kurulur
    - Hover/picking için hızlı sorgulama
    - Hücre bazlı eleme ile performans
    """
    
    def __init__(self, cell_size: float = 500.0):
        """
        Args:
            cell_size: Hücre boyutu (model ölçeğine göre)
                      Örn: 9km model → 500m hücre
        """
        if cell_size <= 0:
            raise ValueError(f"cell_size pozitif olmalı: {cell_size}")
            
        self.cell_size = float(cell_size)
        self.cells: Dict[Tuple[int, int, int], List[int]] = {}
        
        # Metadata (opsiyonel, debug için)
        self.element_count = 0
        self.cell_count = 0
        
        # Cache'ler
        self._bbox_cache: Dict[int, BoundingBox] = {}
        self._type_cache: Dict[int, ElementType] = {}
        
    def _get_cell_coords(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """
        Bir noktanın hangi hücrede olduğunu döndür
        
        Performans: floor div operasyonu, hızlı
        """
        return (
            int(x // self.cell_size),
            int(y // self.cell_size),
            int(z // self.cell_size)
        )
    
    def _get_cell_range(self, bbox: BoundingBox) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """
        Bounding box'ın kapsadığı hücre aralığını döndür
        
        Returns:
            ((x_min, x_max), (y_min, y_max), (z_min, z_max))
        """
        x_min, y_min, z_min = self._get_cell_coords(bbox.min_x, bbox.min_y, bbox.min_z)
        x_max, y_max, z_max = self._get_cell_coords(bbox.max_x, bbox.max_y, bbox.max_z)
        
        # Sınır kontrolü - overflow koruması
        x_min, x_max = min(x_min, x_max), max(x_min, x_max)
        y_min, y_max = min(y_min, y_max), max(y_min, y_max)
        z_min, z_max = min(z_min, z_max), max(z_min, z_max)
        
        return (
            (x_min, x_max),
            (y_min, y_max),
            (z_min, z_max)
        )
    
    def add_element(self, element_idx: int, vertex_list: List[float], 
                   element_type: Optional[ElementType] = None) -> None:
        """
        Grid'e eleman ekle
        
        Args:
            element_idx: Eleman indeksi (individual_data'daki sıra)
            vertex_list: OpenGL vertex listesi [x,y,z,r,g,b,a, x,y,z...]
            element_type: Eleman tipi (opsiyonel, debug için)
        """
        if not vertex_list:
            return
            
        # Bounding box hesapla
        bbox = BoundingBox.from_list(vertex_list)
        self._bbox_cache[element_idx] = bbox
        
        # Tip cache
        if element_type:
            self._type_cache[element_idx] = element_type
        
        # Kapsanan hücre aralığını bul
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = self._get_cell_range(bbox)
        
        # Tüm hücrelere ekle
        added_cells = 0
        for ix in range(x_min, x_max + 1):
            for iy in range(y_min, y_max + 1):
                for iz in range(z_min, z_max + 1):
                    key = (ix, iy, iz)
                    if key not in self.cells:
                        self.cells[key] = []
                        self.cell_count += 1
                    
                    # Duplicate kontrolü (aynı eleman aynı hücreye 2 kez eklenmesin)
                    if element_idx not in self.cells[key]:
                        self.cells[key].append(element_idx)
                        added_cells += 1
        
        self.element_count += 1
        
        # Debug: Büyük elemanlar için uyarı
        if added_cells > 27:  # 3x3x3'ten büyük
            logger.debug(f"Uyarı: Eleman {element_idx} {added_cells} hücreye yayıldı")
    
    def add_elements_batch(self, elements: List[Tuple[int, List[float]]], 
                          types: Optional[List[ElementType]] = None) -> None:
        """
        Toplu eleman ekleme (performans için)
        
        Args:
            elements: (index, vertex_list) çiftleri
            types: Eleman tipleri listesi (opsiyonel)
        """
        for i, (idx, vertices) in enumerate(elements):
            elem_type = types[i] if types and i < len(types) else None
            self.add_element(idx, vertices, elem_type)
    
    def query_point(self, x: float, y: float, z: float) -> List[int]:
        """
        Bir noktayı içeren hücredeki elemanları döndür
        
        Args:
            x, y, z: Sorgu noktası
            
        Returns:
            O hücredeki eleman indeksleri
        """
        key = self._get_cell_coords(x, y, z)
        return self.cells.get(key, []).copy()
    
    def query_box(self, min_xyz: Tuple[float, float, float], 
                  max_xyz: Tuple[float, float, float]) -> Set[int]:
        """
        Bir kutu içindeki tüm elemanları döndür
        
        Args:
            min_xyz: (min_x, min_y, min_z)
            max_xyz: (max_x, max_y, max_z)
            
        Returns:
            Kutudaki tüm eleman indeksleri (unique)
        """
        bbox = BoundingBox(*min_xyz, *max_xyz)
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = self._get_cell_range(bbox)
        
        result: Set[int] = set()
        
        for ix in range(x_min, x_max + 1):
            for iy in range(y_min, y_max + 1):
                for iz in range(z_min, z_max + 1):
                    key = (ix, iy, iz)
                    if key in self.cells:
                        result.update(self.cells[key])
        
        return result
    
    def query_frustum(self, frustum_min: Tuple[float, float, float], 
                     frustum_max: Tuple[float, float, float],
                     margin: int = 0) -> Set[int]:
        """
        Görüntü düzlemi (frustum) içindeki elemanları döndür
        
        Args:
            frustum_min: Kameranın görüş kutusu minimum
            frustum_max: Kameranın görüş kutusu maksimum
            margin: Genişletme marjı (hücre sayısı cinsinden)
            
        Returns:
            Görüntüdeki tüm eleman indeksleri
        """
        bbox = BoundingBox(*frustum_min, *frustum_max)
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = self._get_cell_range(bbox)
        
        # Margin ekle
        x_min -= margin
        x_max += margin
        y_min -= margin
        y_max += margin
        z_min -= margin
        z_max += margin
        
        result: Set[int] = set()
        
        for ix in range(x_min, x_max + 1):
            for iy in range(y_min, y_max + 1):
                for iz in range(z_min, z_max + 1):
                    key = (ix, iy, iz)
                    if key in self.cells:
                        result.update(self.cells[key])
        
        return result
    
    def query_ray(self, ray_origin: Tuple[float, float, float], 
                 ray_direction: Tuple[float, float, float],
                 max_distance: float = float('inf')) -> List[int]:
        """
        Işın boyunca geçilen hücrelerdeki elemanları döndür
        
        Args:
            ray_origin: Işın başlangıç noktası (x,y,z)
            ray_direction: Işın yönü (dx,dy,dz) - normalize edilmemiş olabilir
            max_distance: Maksimum mesafe
            
        Returns:
            Işın boyunca bulunan eleman indeksleri
        """
        # 3D DDA algoritması (Digital Differential Analyzer)
        ox, oy, oz = ray_origin
        dx, dy, dz = ray_direction
        
        # Başlangıç hücresi
        cx, cy, cz = self._get_cell_coords(ox, oy, oz)
        
        # Adım yönleri
        step_x = 1 if dx > 0 else -1
        step_y = 1 if dy > 0 else -1
        step_z = 1 if dz > 0 else -1
        
        # Hücre sınırlarına olan mesafeler
        if dx != 0:
            next_x = (cx + (step_x > 0)) * self.cell_size
            t_max_x = (next_x - ox) / dx
            delta_x = self.cell_size / abs(dx)
        else:
            t_max_x = float('inf')
            delta_x = float('inf')
            
        if dy != 0:
            next_y = (cy + (step_y > 0)) * self.cell_size
            t_max_y = (next_y - oy) / dy
            delta_y = self.cell_size / abs(dy)
        else:
            t_max_y = float('inf')
            delta_y = float('inf')
            
        if dz != 0:
            next_z = (cz + (step_z > 0)) * self.cell_size
            t_max_z = (next_z - oz) / dz
            delta_z = self.cell_size / abs(dz)
        else:
            t_max_z = float('inf')
            delta_z = float('inf')
        
        # Işın boyunca hücreleri tara
        result: Set[int] = set()
        t = 0.0
        
        while t <= max_distance:
            # Mevcut hücredeki elemanları ekle
            key = (cx, cy, cz)
            if key in self.cells:
                result.update(self.cells[key])
            
            # Sonraki hücreye geç
            if t_max_x < t_max_y and t_max_x < t_max_z:
                cx += step_x
                t = t_max_x
                t_max_x += delta_x
            elif t_max_y < t_max_z:
                cy += step_y
                t = t_max_y
                t_max_y += delta_y
            else:
                cz += step_z
                t = t_max_z
                t_max_z += delta_z
        
        return list(result)
    
    def get_neighbor_cells(self, x: int, y: int, z: int, 
                          radius: int = 1) -> List[Tuple[int, int, int]]:
        """
        Bir hücrenin komşularını döndür
        
        Args:
            x, y, z: Merkez hücre koordinatları
            radius: Komşuluk yarıçapı (1 = 3x3x3, 2 = 5x5x5, ...)
            
        Returns:
            Komşu hücre anahtarları
        """
        neighbors = []
        for ix in range(x - radius, x + radius + 1):
            for iy in range(y - radius, y + radius + 1):
                for iz in range(z - radius, z + radius + 1):
                    neighbors.append((ix, iy, iz))
        return neighbors
    
    def query_pick_candidates(self, screen_center: Tuple[float, float, float],
                            radius_cells: int = 1) -> Set[int]:
        """
        Picking için aday elemanları döndür
        
        Args:
            screen_center: Tıklanan noktanın dünya koordinatı
            radius_cells: Kaç hücre genişliğinde tarama yapılacak
            
        Returns:
            Picking için aday eleman indeksleri
        """
        cx, cy, cz = self._get_cell_coords(*screen_center)
        neighbor_keys = self.get_neighbor_cells(cx, cy, cz, radius_cells)
        
        candidates: Set[int] = set()
        for key in neighbor_keys:
            if key in self.cells:
                candidates.update(self.cells[key])
        
        return candidates
    
    def get_element_bbox(self, element_idx: int) -> Optional[BoundingBox]:
        """Elemanın bounding box'ını döndür"""
        return self._bbox_cache.get(element_idx)
    
    def get_cell_stats(self) -> Dict:
        """Grid istatistiklerini döndür"""
        cell_sizes = [len(cell) for cell in self.cells.values()]
        
        return {
            'cell_size': self.cell_size,
            'total_cells': self.cell_count,
            'active_cells': len(self.cells),
            'total_elements': self.element_count,
            'avg_elements_per_cell': np.mean(cell_sizes) if cell_sizes else 0,
            'max_elements_per_cell': max(cell_sizes) if cell_sizes else 0,
            'min_elements_per_cell': min(cell_sizes) if cell_sizes else 0,
            'cached_bboxes': len(self._bbox_cache)
        }
    
    def clear(self) -> None:
        """Grid'i temizle"""
        self.cells.clear()
        self._bbox_cache.clear()
        self._type_cache.clear()
        self.element_count = 0
        self.cell_count = 0

# ============= KULLANIM ÖRNEĞİ =============



# Hover için
def hover_test(grid, ray_origin, ray_direction):
    """Fare hover işlemi"""
    candidates = grid.query_ray(ray_origin, ray_direction, max_distance=10000)
    # Bu adaylarla ray-intersection testi yap
    return candidates

# Picking için
def pick_test(grid, screen_center_world):
    """Fare tıklama işlemi"""
    candidates = grid.query_pick_candidates(screen_center_world, radius_cells=1)
    # Bu adaylar unique ID renkleriyle çizilip glReadPixels ile okunur
    return candidates


if __name__ == "__main__":
    import random
    from cad2.tools.s2kloader import S2KLoader
    #dosyadan import etme
    #dosyada ölçülerin birimi var genellikle mm
    file_path= "D:/program/cad2/data/model3.$2k"
    loader = S2KLoader(file_path)
    batch_data, individual_data = loader.load()
    nodes,frames,areas= batch_data

    logger.debug("\nörnek individual_data içeriği ilk 3 data:")
    logger.debug(individual_data[:3])

    logger.debug(f"\nToplam eleman sayısı: {len(individual_data)}")
    logger.debug(f"İlk 3 data: {individual_data[:3]}")
    
    # Model sınırlarını bul
    all_x = []
    all_y = []
    all_z = []
    for vertex_list, _ in individual_data[:100]:  # İlk 100 eleman
        xs = vertex_list[0::7]
        ys = vertex_list[1::7]
        zs = vertex_list[2::7]
        all_x.extend(xs)
        all_y.extend(ys)
        all_z.extend(zs)
    
    logger.debug(f"\nModel koordinat aralığı:")
    logger.debug(f"  X: {min(all_x):.1f} - {max(all_x):.1f}")
    logger.debug(f"  Y: {min(all_y):.1f} - {max(all_y):.1f}")
    logger.debug(f"  Z: {min(all_z):.1f} - {max(all_z):.1f}")
    
    # Daha uygun cell_size seçimi
    model_width = max(all_x) - min(all_x)
    cell_size = model_width / 20  # Yaklaşık 20 hücreye böl
    logger.debug(f"\nSeçilen hücre boyutu: {cell_size:.1f}")

    grid = SpatialGrid(cell_size)
    # Tüm elemanları ekle
    elements = [(idx, v_list) for idx, (v_list, _) in enumerate(individual_data)]
    grid.add_elements_batch(elements)

    logger.debug(f"\nSpatialGrid kuruldu:")
    logger.debug(f"  - Toplam eleman: {grid.element_count}")
    logger.debug(f"  - Aktif hücre: {len(grid.cells)}")
    logger.debug(f"  - Hücre boyutu: {grid.cell_size:.1f}")
    
    # TEST 1: Gerçek node'ların olduğu noktaları sorgula
    logger.debug("\n" + "="*50)
    logger.debug("TEST 1: Gerçek node pozisyonlarında sorgu")
    logger.debug("="*50)
    
    test_points = [
        (9123.84, 59.66, 5063.00),  # İlk node
        (10491.88, 59.66, 5063.30), # İkinci node
        (9870.00, -0.34, 5510.00),  # Üçüncü node
    ]
    
    for point in test_points:
        candidates = grid.query_pick_candidates(point, radius_cells=1)
        logger.debug(f"Nokta {point} → {len(candidates)} aday, indeksler: {sorted(candidates)[:5]}")

    # TEST 2: Rastgele seçilmiş elemanları sorgula
    logger.debug("\n" + "="*50)
    logger.debug("TEST 2: Rastgele eleman bounding box merkezleri")
    logger.debug("="*50)
    
    random_indices = random.sample(range(len(individual_data)), min(5, len(individual_data)))
    for idx in random_indices:
        bbox = grid.get_element_bbox(idx)
        if bbox:
            center = bbox.get_center()
            candidates = grid.query_pick_candidates(center, radius_cells=1)
            logger.debug(f"Eleman {idx} merkez {center} → {len(candidates)} aday")
            logger.debug(f"  Bbox: ({bbox.min_x:.1f}, {bbox.min_y:.1f}, {bbox.min_z:.1f}) - ({bbox.max_x:.1f}, {bbox.max_y:.1f}, {bbox.max_z:.1f})")
    
    # TEST 3: Komşu hücrelerde ara
    logger.debug("\n" + "="*50)
    logger.debug("TEST 3: Radius=2 ile geniş sorgu")
    logger.debug("="*50)
    
    for point in test_points:
        candidates = grid.query_pick_candidates(point, radius_cells=2)
        logger.debug(f"Nokta {point} → {len(candidates)} aday (radius=2)")
    
    # TEST 4: Işın sorgusu
    logger.debug("\n" + "="*50)
    logger.debug("TEST 4: Işın sorgusu")
    logger.debug("="*50)
    
    # Yukarıdan aşağıya doğru ışın
    ray_origin = (10000.0, 1000.0, 6000.0)
    ray_dir = (0.0, -1.0, 0.0)  # -Y yönü
    candidates = grid.query_ray(ray_origin, ray_dir, max_distance=2000)
    logger.debug(f"Işın {ray_origin} yön {ray_dir} → {len(candidates)} aday")
    
    # Grid istatistikleri
    logger.debug("\n" + "="*50)
    logger.debug("Grid İstatistikleri")
    logger.debug("="*50)
    stats = grid.get_cell_stats()
    for key, value in stats.items():
        logger.debug(f"  {key}: {value}")