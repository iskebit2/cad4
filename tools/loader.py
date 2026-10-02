# core/loader.py
import numpy as np
import glm
from tools.s2kloader import S2KLoader
from geometry.spatialgrid import SpatialGrid
import logging
logger = logging.getLogger(__name__)


class ModelLoader:
    """Model yükleme işlemlerinden sorumlu sınıf"""
    
    def __init__(self, engine):
        self.engine = engine
    
    def import_s2k(self):
        """S2K dosyası içe aktar"""
        try:
            loader = S2KLoader()
            batch_data, individual_data = loader.load()
            
            if batch_data and individual_data:
                self.load_model(batch_data, individual_data)
                # logger.debug("Model loaded successfully.")
            else:
                logger.debug("No data loaded.")
                
        except Exception as e:
            logger.debug(f"Import error: {e}")
    
    def load_model(self, batch_data, individual_data):
        """Model verilerini yükle ve tüm bileşenleri güncelle"""
        if not batch_data or not individual_data:
            return
        
        # 1. Sahneye verileri yükle
        self.engine.scene.load_data(batch_data, individual_data)
        
        # 2. Model sınırlarını hesapla (Scene üzerinden)
        center, size_vec = self.engine.scene.calculate_bounds()
        
        # 3. Spatial grid'i kur
        model_width = max(size_vec.x, size_vec.y)
        cell_size = model_width / 20.0
        spatialgrid = SpatialGrid(cell_size)
        
        elements = [(idx, v_list) for idx, (v_list, _) in enumerate(individual_data)]
        spatialgrid.add_elements_batch(elements)
        
        # 4. Picker'a grid'i ver
        self.engine.picker.set_spatial_grid(spatialgrid)
        
        # 5. Kamerayı ayarla
        self._focus_on_model(center, size_vec)
        
        # logger.debug(f"Model yüklendi - Merkez: {center}, Boyut: {size_vec}")
    
    def _focus_on_model(self, center, size_vec):
        """Kamerayı modele odakla"""
        self.engine.cam.target = center
        self.engine.cam.dist = max(size_vec.x, size_vec.y, size_vec.z) * 1.5
        self.engine.cam._update_position()