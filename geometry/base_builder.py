# geometry/base_builder.py
import numpy as np
from typing import List, Tuple, TypeVar, Generic
from abc import ABC, abstractmethod

T = TypeVar('T')  # Element tipi

class BaseGeometryBuilder(ABC, Generic[T]):
    """Tüm geometry builder'ların temel sınıfı"""
    
    @abstractmethod
    def build(self, element: T) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Element için geometry oluştur
        Returns: (vertices, colors, indices)
        - vertices: [x,y,z, nx,ny,nz] per vertex
        - colors: [r,g,b] per vertex
        - indices: uint32 triangle indices
        """
        pass
    
    def build_all(self, elements: List[T]) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Tüm elementler için geometry oluştur"""
        return [self.build(e) for e in elements]