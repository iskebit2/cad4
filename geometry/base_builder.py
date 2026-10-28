# geometry/base_builder.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import numpy as np

T = TypeVar('T')  # Element tipi

class BaseGeometryBuilder(ABC, Generic[T]):
    """Tüm geometry builder'ların temel sınıfı"""
    
    @abstractmethod
    def build(self, element: T) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Element için geometry oluştur
        Returns: (vertices, colors, indices)
        - vertices: [x,y,z, nx,ny,nz] per vertex
        - colors: [r,g,b] per vertex
        - indices: uint32 triangle indices
        """
    
    def build_all(self, elements: list[T]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Tüm elementler için geometry oluştur"""
        return [self.build(e) for e in elements]