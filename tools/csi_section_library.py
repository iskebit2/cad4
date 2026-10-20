# tools/csi_section_library

import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, Tuple, Optional, List, Any
import logging

logger = logging.getLogger(__name__)

class CSiSectionLibrary:
    """
    CSi (ETABS/SAP2000) kesit kütüphanesi parser
    """
    
    # Kesit tipleri ve önemli özellikleri
    SECTION_TYPES = {
        'STEEL_I_SECTION': {
            'shape': 'I/Wide Flange',
            'required': ['D', 'BF', 'TF', 'TW'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J', 'AS2', 'AS3']
        },
        'STEEL_CHANNEL_SECTION': {
            'shape': 'Channel',
            'required': ['D', 'BF', 'TF', 'TW'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J', 'AS2', 'AS3']
        },
        'STEEL_ANGLE_SECTION': {
            'shape': 'Angle',
            'required': ['D', 'BF', 'TF', 'TW'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J']
        },
        'STEEL_T_SECTION': {
            'shape': 'Tee',
            'required': ['D', 'BF', 'TF', 'TW'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J', 'AS2', 'AS3']
        },
        'STEEL_DBLANGLE_SECTION': {
            'shape': 'Double Angle',
            'required': ['D', 'BF', 'TF', 'TW', 'DIST'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J']
        },
        'STEEL_PIPE_SECTION': {
            'shape': 'Pipe',
            'required': ['OD', 'T'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J', 'AS2']
        },
        'STEEL_RECTANGULAR_SECTION': {
            'shape': 'Rectangular',
            'required': ['D', 'BF'],
            'properties': ['A', 'I33', 'I22', 'Z33', 'Z22', 'J', 'AS2', 'AS3']
        },
        'CONCRETE_RECTANGULAR_SECTION': {
            'shape': 'Concrete Rectangular',
            'required': ['D', 'BF'],
            'properties': ['A', 'I33', 'I22']
        },
        'CONCRETE_CIRCULAR_SECTION': {
            'shape': 'Concrete Circular',
            'required': ['D'],
            'properties': ['A', 'I33', 'I22']
        }
    }
    
    def __init__(self, xml_path: str = None):
        self.xml_path = xml_path
        self.tree = None
        self.root = None
        self.sections_df = None
        self.sections_dict: Dict[str, Dict] = {}
        self.ns = {'csi': 'http://www.csiberkeley.com'}
        
        if xml_path:
            self.load(xml_path)
    
    def load(self, xml_path: str):
        """XML dosyasını yükle"""
        try:
            self.tree = ET.parse(xml_path)
            self.root = self.tree.getroot()
            self.xml_path = xml_path
            self._parse_all_sections()
            logger.info(f"Loaded {len(self.sections_dict)} sections from {xml_path}")
        except Exception as e:
            logger.error(f"Error loading {xml_path}: {e}")
    
    def _parse_all_sections(self):
        """Tüm kesitleri parse et"""
        sections_data = []
        
        for section in self.root:
            # CONTROL veya PROPERTY_FILE kısımlarını geç
            if section.tag.endswith('CONTROL') or section.tag.endswith('PROPERTY_FILE'):
                continue
            
            # Kesit tipini al
            section_type = section.tag.split('}')[-1]
            
            # LABEL'i bul
            label_node = section.find('csi:LABEL', self.ns)
            if label_node is None or not label_node.text:
                continue
            
            label = label_node.text
            
            # Kesit verilerini topla
            section_data = {
                'type': section_type,
                'label': label,
                'shape': self.SECTION_TYPES.get(section_type, {}).get('shape', section_type)
            }
            
            # Tüm alt elemanları ekle
            for child in section:
                tag = child.tag.split('}')[-1]
                if tag != 'LABEL':
                    section_data[tag] = child.text
            
            self.sections_dict[label] = section_data
            sections_data.append(section_data)
        
        # DataFrame oluştur
        if sections_data:
            self.sections_df = pd.DataFrame(sections_data)
            if 'label' in self.sections_df.columns:
                self.sections_df.set_index('label', inplace=True)
    
    def get_section(self, label: str) -> Optional[Dict[str, Any]]:
        """Kesit etiketine göre kesit bilgisi getir"""
        return self.sections_dict.get(label)
    
    def get_section_property(self, label: str, prop: str) -> Any:
        """Kesitin belirli bir özelliğini getir"""
        section = self.get_section(label)
        if section and prop in section:
            value = section[prop]
            # Sayısal değerleri dönüştür
            try:
                if 'E' in value or 'e' in value:
                    return float(value)
                elif '.' in value:
                    return float(value)
                else:
                    return int(value)
            except (ValueError, TypeError):
                return value
        return None
    
    def get_section_geometry(self, label: str) -> Dict[str, float]:
        """Kesitin geometrik özelliklerini getir (ETABS FRAMESECTION formatında)"""
        section = self.get_section(label)
        if not section:
            return {}
        
        geometry = {}
        section_type = section.get('type', '')
        
        # Kesit tipine göre geometri dönüşümü
        if section_type == 'STEEL_I_SECTION':
            geometry['SHAPE'] = 'Steel I/Wide Flange'
            geometry['D'] = float(section.get('D', 0))
            geometry['B'] = float(section.get('BF', 0))
            geometry['TF'] = float(section.get('TF', 0))
            geometry['TW'] = float(section.get('TW', 0))
            
        elif section_type == 'STEEL_RECTANGULAR_SECTION':
            geometry['SHAPE'] = 'Steel Rectangular'
            geometry['D'] = float(section.get('D', 0))
            geometry['B'] = float(section.get('BF', 0))
            
        elif section_type == 'CONCRETE_RECTANGULAR_SECTION':
            geometry['SHAPE'] = 'Concrete Rectangular'
            geometry['D'] = float(section.get('D', 0))
            geometry['B'] = float(section.get('BF', 0))
            
        elif section_type == 'CONCRETE_CIRCULAR_SECTION':
            geometry['SHAPE'] = 'Concrete Circular'
            geometry['D'] = float(section.get('D', 0))
        
        return geometry
    
    def search_sections(self, **criteria) -> pd.DataFrame:
        """Kesitleri kriterlere göre ara"""
        if self.sections_df is None:
            return pd.DataFrame()
        
        mask = pd.Series(True, index=self.sections_df.index)
        for key, value in criteria.items():
            if key in self.sections_df.columns:
                if isinstance(value, (int, float)):
                    mask &= (self.sections_df[key].astype(float) >= value)
                else:
                    mask &= (self.sections_df[key] == value)
        
        return self.sections_df[mask]
    
    def to_frame_section_format(self, label: str, material: str = None) -> Dict:
        """Kesiti ETABS FRAMESECTION formatına dönüştür"""
        section = self.get_section(label)
        if not section:
            return {}
        
        geometry = self.get_section_geometry(label)
        if not geometry:
            return {}
        
        result = {
            'name': f'"{label}"',
            'material': f'"{material}"' if material else None,
            'shape': geometry['SHAPE']
        }
        
        # Geometri özelliklerini ekle
        for key, value in geometry.items():
            if key not in ['SHAPE']:
                result[key] = value
        
        return result
    
    def list_sections_by_type(self, section_type: str) -> List[str]:
        """Belirli tipteki kesitleri listele"""
        if self.sections_df is None:
            return []
        mask = self.sections_df['type'] == section_type
        return self.sections_df[mask].index.tolist()


class CSiMaterialLibrary:
    """
    CSi (ETABS/SAP2000) malzeme kütüphanesi parser
    """
    
    MATERIAL_MAP = {
        'COMMON': ['modulusOfElasticity', 'poissonsRatio', 'massDensity', 
                   'weightDensity', 'coefficientOfThermalExpansion'],
        'STEEL': ['minimumYieldStress', 'minimumTensileStress', 'effectiveYieldStress', 
                  'effectiveTensileStress', 'strainAtHardening', 'strainAtMaxStress', 
                  'strainAtRupture'],
        'CONCRETE': ['compressiveStrength', 'strainAtfc', 'strainAtUltimate', 
                     'isLightWeight', 'shearStrengthReductionFactor']
    }
    
    # Malzeme tipi eşleştirmeleri
    TYPE_MAPPING = {
        'concrete': 'Concrete',
        'steel': 'Steel',
        'rebar': 'Rebar',
        'tendon': 'Tendon'
    }
    
    def __init__(self, xml_path: str = None):
        self.xml_path = xml_path
        self.materials_df = None
        self.materials_dict: Dict[str, Dict] = {}
        
        if xml_path:
            self.load(xml_path)
    
    def load(self, xml_path: str):
        """XML dosyasını yükle"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            self.xml_path = xml_path
            self._parse_materials(root)
            logger.info(f"Loaded {len(self.materials_dict)} materials from {xml_path}")
        except Exception as e:
            logger.error(f"Error loading {xml_path}: {e}")
    
    def _parse_materials(self, root):
        """Malzemeleri parse et"""
        data_list = []
        
        for mat in root.findall('.//{*}material'):
            # Attribute'ları al (name, grade, type)
            row = mat.attrib.copy()
            
            # İçindeki tüm değerleri sözlüğe bas
            for prop in mat:
                tag = prop.tag.split('}')[-1]
                row[tag] = prop.text
            
            # Malzeme adını index olarak kullan
            if 'name' in row:
                self.materials_dict[row['name']] = row
            
            data_list.append(row)
        
        # DataFrame oluştur
        if data_list:
            self.materials_df = pd.DataFrame(data_list)
            if 'name' in self.materials_df.columns:
                self.materials_df.set_index('name', inplace=True)
    
    def get_material(self, name: str) -> Optional[Dict[str, Any]]:
        """Malzeme adına göre malzeme bilgisi getir"""
        return self.materials_dict.get(name)
    
    def get_material_property(self, name: str, prop: str) -> Any:
        """Malzemenin belirli bir özelliğini getir"""
        material = self.get_material(name)
        if material and prop in material:
            value = material[prop]
            # Sayısal değerleri dönüştür
            try:
                if 'E' in value or 'e' in value:
                    return float(value)
                elif '.' in value:
                    return float(value)
                else:
                    return int(value)
            except (ValueError, TypeError):
                return value
        return None
    
    def to_etabs_format(self, name: str) -> Dict:
        """Malzemeyi ETABS MATERIAL formatına dönüştür"""
        mat = self.get_material(name)
        if not mat:
            return {}
        
        mat_type = mat.get('type', '').lower()
        etabs_type = self.TYPE_MAPPING.get(mat_type, mat_type.capitalize())
        
        result = {
            'name': f'"{name}"',
            'type': etabs_type
        }
        
        if 'grade' in mat:
            result['grade'] = f'"{mat["grade"]}"'
        
        # Yoğunluk
        if 'weightDensity' in mat:
            result['weightpervolume'] = float(mat['weightDensity'])
        
        # Elastisite modülü
        if 'modulusOfElasticity' in mat:
            result['e'] = float(mat['modulusOfElasticity'])
        
        # Poisson oranı
        if 'poissonsRatio' in mat:
            result['u'] = float(mat['poissonsRatio'])
        
        # Dayanımlar
        if mat_type == 'concrete':
            if 'compressiveStrength' in mat:
                result['fc'] = float(mat['compressiveStrength'])
        
        elif mat_type in ['steel', 'rebar']:
            if 'minimumYieldStress' in mat:
                result['fy'] = float(mat['minimumYieldStress'])
            if 'minimumTensileStress' in mat:
                result['fu'] = float(mat['minimumTensileStress'])
        
        return result
    
    def search_materials(self, **criteria) -> pd.DataFrame:
        """Malzemeleri kriterlere göre ara"""
        if self.materials_df is None:
            return pd.DataFrame()
        
        mask = pd.Series(True, index=self.materials_df.index)
        for key, value in criteria.items():
            if key in self.materials_df.columns:
                if isinstance(value, (int, float)):
                    mask &= (self.materials_df[key].astype(float) >= value)
                else:
                    mask &= (self.materials_df[key] == value)
        
        return self.materials_df[mask]
    
    def list_materials_by_type(self, mat_type: str) -> List[str]:
        """Belirli tipteki malzemeleri listele"""
        if self.materials_df is None:
            return []
        mask = self.materials_df['type'] == mat_type
        return self.materials_df[mask].index.tolist()


class CSiLibrary:
    """
    CSi kütüphanelerini birleştiren ana sınıf
    """
    
    def __init__(self, material_xml: str = None, section_xml: str = None):
        self.materials = CSiMaterialLibrary(material_xml)
        self.sections = CSiSectionLibrary(section_xml)
    
    def load_materials(self, xml_path: str):
        """Malzeme kütüphanesi yükle"""
        self.materials.load(xml_path)
    
    def load_sections(self, xml_path: str):
        """Kesit kütüphanesi yükle"""
        self.sections.load(xml_path)
    
    def create_frame_section(self, section_label: str, material_name: str = None) -> Dict:
        """FRAMESECTION tanımı oluştur"""
        return self.sections.to_frame_section_format(section_label, material_name)
    
    def create_material(self, material_name: str) -> Dict:
        """MATERIAL tanımı oluştur"""
        return self.materials.to_etabs_format(material_name)
    
    def get_section_with_material(self, section_label: str, material_name: str = None) -> Dict:
        """Kesit ve malzeme bilgisini birleştir"""
        section = self.sections.get_section(section_label)
        if not section:
            return {}
        
        material = self.materials.get_material(material_name) if material_name else None
        
        result = {
            'section': section,
            'material': material
        }
        
        # Geometrik özellikleri ekle
        geometry = self.sections.get_section_geometry(section_label)
        if geometry:
            result['geometry'] = geometry
        
        return result
