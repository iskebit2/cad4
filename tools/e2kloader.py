import re
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Point3D:
    """3D nokta koordinatı"""
    x: float
    y: float
    z: float = 0.0
    point_id: str = ""
    stories: List[str] = field(default_factory=list)
    has_z: bool = False  # Direkt z koordinatı var mı?

@dataclass
class Element:
    """Eleman (line, area)"""
    name: str
    type: str  # BEAM, PANEL, FLOOR, etc.
    point_ids: List[str]
    properties: Dict[str, Any] = field(default_factory=dict)

class E2KParser:
    """
    ETABS .$et / .e2k dosya okuma - TAM KAPSAMLI VERSİYON
    """
    
    # Section tipleri ve parse stratejileri
    SECTION_TYPES = {
        'PROGRAM INFORMATION': 'program_info',
        'CONTROLS': 'key_value_pairs',
        'STORIES - IN SEQUENCE FROM TOP': 'stories',
        'GRIDS': 'grids',
        'DIAPHRAGM NAMES': 'simple_list',
        'MATERIAL PROPERTIES': 'materials',
        'REBAR DEFINITIONS': 'rebar_defs',
        'FRAME SECTIONS': 'frame_sections',
        'AUTO SELECT SECTION LISTS': 'auto_select',
        'CONCRETE SECTIONS': 'concrete_sections',
        'TENDON SECTIONS': 'tendon_sections',
        'SLAB PROPERTIES': 'shell_props',
        'WALL PROPERTIES': 'shell_props',
        'PIER/SPANDREL NAMES': 'simple_list',
        'POINT COORDINATES': 'point_coordinates',
        'LINE CONNECTIVITIES': 'line_connectivity',
        'AREA CONNECTIVITIES': 'area_connectivity',
        'POINT ASSIGNS': 'point_assigns',
        'LINE ASSIGNS': 'line_assigns',
        'AREA ASSIGNS': 'area_assigns',
        'LOAD PATTERNS': 'load_patterns',
        'SHELL UNIFORM LOAD SETS': 'shell_load_sets',
        'SHELL OBJECT LOADS': 'shell_loads',
        'LOAD CASES': 'load_cases',
        'LOAD COMBINATIONS': 'load_combinations',
        'MASS SOURCE': 'mass_source',
        'FUNCTIONS': 'functions',
    }
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.raw_sections: Dict[str, List[str]] = {}
        
        # Story data
        self.stories: Dict[str, float] = {}  # story_name -> elevation
        self.story_heights: Dict[str, float] = {}  # story_name -> height
        self.story_order: List[str] = []  # stories in order from top
        self.base_elevation = 0.0
        
        # Point data
        self.points: Dict[str, Point3D] = {}  # point_id -> Point3D
        self.point_assignments: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)  # point_id -> [(story, props)]
        
        # Element data
        self.lines: Dict[str, Element] = {}
        self.areas: Dict[str, Element] = {}
        
        # Section properties
        self.frame_sections: Dict[str, Dict] = {}
        self.shell_props: Dict[str, Dict] = {}
        
        if file_path:
            self._load_and_parse()
    
    def _load_and_parse(self):
        """Load and parse ETABS file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            logger.info(f"[E2KParser] Loaded file: {self.file_path}, size: {len(content)} bytes")
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return
        
        # Handle continuation lines (lines ending with _)
        content = re.sub(r' _\r?\n', ' ', content)
        
        # Extract sections
        lines = content.split('\n')
        self.raw_sections = self._extract_sections(lines)
        
        # Process in correct order
        self._process_program_info()
        self._process_stories()
        self._process_point_coordinates()
        self._process_point_assigns()
        self._create_3d_points()
        
        # Process other sections
        for section_name in self.raw_sections:
            if section_name not in ['PROGRAM INFORMATION', 'STORIES - IN SEQUENCE FROM TOP', 
                                    'POINT COORDINATES', 'POINT ASSIGNS']:
                self._process_section(section_name)
        
        # Create combined geometry tables
        self._create_line_geometry()
        self._create_area_geometry()
        
        logger.info(f"[E2KParser] Loaded {len(self.tables)} sections, {len(self.points)} points, "
                   f"{len(self.lines)} lines, {len(self.areas)} areas")
    
    def _extract_sections(self, lines: List[str]) -> Dict[str, List[str]]:
        """Extract sections from lines"""
        sections = {}
        current_section = None
        section_data = []
        
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            
            if line.startswith('$'):
                # Save previous section
                if current_section and section_data:
                    sections[current_section] = section_data
                
                # Start new section
                current_section = line[1:].strip()
                section_data = []
                logger.debug(f"Found section: {current_section}")
            else:
                if current_section and not line.startswith('  END'):
                    section_data.append(line)
        
        # Save last section
        if current_section and section_data:
            sections[current_section] = section_data
        
        return sections
    
    def _parse_line(self, line: str) -> List[str]:
        """Parse a line respecting quoted strings"""
        parts = []
        current = []
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
                current.append(char)
            elif char.isspace() and not in_quotes:
                if current:
                    parts.append(''.join(current))
                    current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _try_convert(self, value: str) -> Any:
        """Try to convert string to number"""
        # Remove quotes if present
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        
        try:
            if '.' in value or 'E' in value.upper():
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value
    
    def _process_program_info(self):
        """Process program information"""
        lines = self.raw_sections.get('PROGRAM INFORMATION', [])
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 3:
                data.append({
                    'program': parts[1] if len(parts) > 1 else '',
                    'version': parts[3] if len(parts) > 3 else ''
                })
        if data:
            self.tables['PROGRAM_INFO'] = pd.DataFrame(data)
    
    def _process_stories(self):
        """Process STORIES section"""
        lines = self.raw_sections.get('STORIES - IN SEQUENCE FROM TOP', [])
        if not lines:
            return
        
        story_data = []
        current_elev = 0.0
        
        # Find base elevation
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 3 and parts[0] == 'STORY' and parts[1] == '"Base"':
                for i in range(2, len(parts)-1):
                    if parts[i] == 'ELEV':
                        self.base_elevation = float(parts[i+1])
                        current_elev = self.base_elevation
                        break
        
        # Process from bottom to top for elevation calculation
        stories_reversed = []
        for line in reversed(lines):
            parts = self._parse_line(line)
            if len(parts) >= 3 and parts[0] == 'STORY':
                story_name = parts[1].strip('"')
                height = 0.0
                
                for i in range(2, len(parts)-1):
                    if parts[i] == 'HEIGHT':
                        height = float(parts[i+1])
                        break
                
                if story_name != 'Base':
                    stories_reversed.append({
                        'name': story_name,
                        'height': height,
                        'elevation': current_elev
                    })
                    current_elev += height
        
        # Store in original order (from top)
        for story in reversed(stories_reversed):
            self.stories[story['name']] = story['elevation']
            self.story_heights[story['name']] = story['height']
            self.story_order.append(story['name'])
            story_data.append(story)
        
        # Add Base
        self.stories['Base'] = self.base_elevation
        self.story_heights['Base'] = 0
        self.story_order.append('Base')
        story_data.append({'name': 'Base', 'height': 0, 'elevation': self.base_elevation})
        
        self.tables['STORIES'] = pd.DataFrame(story_data)
    
    def _process_point_coordinates(self):
        """Process POINT COORDINATES section"""
        lines = self.raw_sections.get('POINT COORDINATES', [])
        
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 4 and parts[0] == 'POINT':
                point_id = parts[1].strip('"')
                x = float(parts[2])
                y = float(parts[3])
                
                # Check if Z coordinate is provided
                has_z = len(parts) >= 5
                z = float(parts[4]) if has_z else 0.0
                
                self.points[point_id] = Point3D(
                    x=x, y=y, z=z,
                    point_id=point_id,
                    has_z=has_z
                )
    
    def _process_point_assigns(self):
        """Process POINT ASSIGNS section"""
        lines = self.raw_sections.get('POINT ASSIGNS', [])
        
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 3 and parts[0] == 'POINTASSIGN':
                point_id = parts[1].strip('"')
                story_name = parts[2].strip('"')
                
                # Parse additional properties
                props = {}
                i = 3
                while i < len(parts) - 1:
                    key = parts[i]
                    value = parts[i + 1].strip('"') if i + 1 < len(parts) else ''
                    props[key] = value
                    i += 2
                
                self.point_assignments[point_id].append((story_name, props))
                
                if point_id in self.points:
                    self.points[point_id].stories.append(story_name)
    
    def _create_3d_points(self):
        """Create comprehensive 3D point table"""
        point_data = []
        
        for point_id, point in self.points.items():
            if point.has_z:
                # Point has explicit Z coordinate
                point_data.append({
                    'point_id': point_id,
                    'x': point.x,
                    'y': point.y,
                    'z': point.z,
                    'story': None,
                    'has_explicit_z': True
                })
            elif point.stories:
                # Point has story assignments
                for story in point.stories:
                    if story in self.stories:
                        point_data.append({
                            'point_id': point_id,
                            'x': point.x,
                            'y': point.y,
                            'z': self.stories[story],
                            'story': story,
                            'has_explicit_z': False
                        })
            else:
                # Point without story assignment
                point_data.append({
                    'point_id': point_id,
                    'x': point.x,
                    'y': point.y,
                    'z': 0.0,
                    'story': None,
                    'has_explicit_z': False
                })
        
        if point_data:
            self.tables['POINTS_3D'] = pd.DataFrame(point_data)
    
    def _process_line_connectivity(self):
        """Process LINE CONNECTIVITIES section"""
        lines = self.raw_sections.get('LINE CONNECTIVITIES', [])
        
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 5 and parts[0] == 'LINE':
                line_name = parts[1].strip('"')
                line_type = parts[2]
                point1 = parts[3].strip('"')
                point2 = parts[4].strip('"')
                
                self.lines[line_name] = Element(
                    name=line_name,
                    type=line_type,
                    point_ids=[point1, point2]
                )
    
    def _process_area_connectivity(self):
        """Process AREA CONNECTIVITIES section"""
        lines = self.raw_sections.get('AREA CONNECTIVITIES', [])
        
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 5 and parts[0] == 'AREA':
                area_name = parts[1].strip('"')
                area_type = parts[2]
                num_points = int(parts[3])
                
                # Get point IDs
                point_ids = []
                for i in range(num_points):
                    point_id = parts[4 + i].strip('"')
                    point_ids.append(point_id)
                
                self.areas[area_name] = Element(
                    name=area_name,
                    type=area_type,
                    point_ids=point_ids
                )
    
    def _create_line_geometry(self):
        """Create line geometry with 3D coordinates"""
        line_data = []
        
        # Get line assigns
        line_assigns = self.tables.get('LINE_ASSIGNS', pd.DataFrame())
        line_assign_dict = defaultdict(list)
        
        if not line_assigns.empty:
            for _, row in line_assigns.iterrows():
                if 'LINEASSIGN' in row and 'name' in row:
                    line_assign_dict[row['name']].append(row)
        
        # Process each line
        for line_name, line in self.lines.items():
            # Get point coordinates
            points_3d = []
            for point_id in line.point_ids:
                point_df = self.tables.get('POINTS_3D', pd.DataFrame())
                point_rows = point_df[point_df['point_id'] == point_id]
                if not point_rows.empty:
                    points_3d.append(point_rows.iloc[0])
            
            if len(points_3d) >= 2:
                # Create line entry
                line_entry = {
                    'line_id': line_name,
                    'type': line.type,
                    'point_i': line.point_ids[0],
                    'point_j': line.point_ids[1],
                    'xi': points_3d[0]['x'],
                    'yi': points_3d[0]['y'],
                    'zi': points_3d[0]['z'],
                    'xj': points_3d[1]['x'],
                    'yj': points_3d[1]['y'],
                    'zj': points_3d[1]['z'],
                }
                
                # Add assigns if available
                assigns = line_assign_dict.get(line_name, [])
                if assigns:
                    line_entry['story'] = assigns[0].get('story', '')
                    line_entry['section'] = assigns[0].get('SECTION', '')
                
                line_data.append(line_entry)
        
        if line_data:
            self.tables['LINES_3D'] = pd.DataFrame(line_data)
    
    def _create_area_geometry(self):
        """Create area geometry with 3D coordinates"""
        area_data = []
        
        # Get area assigns
        area_assigns = self.tables.get('AREA_ASSIGNS', pd.DataFrame())
        area_assign_dict = defaultdict(list)
        
        if not area_assigns.empty:
            for _, row in area_assigns.iterrows():
                if 'AREAASSIGN' in row and 'name' in row:
                    area_assign_dict[row['name']].append(row)
        
        # Process each area
        for area_name, area in self.areas.items():
            # Get point coordinates
            points_3d = []
            z_values = []
            
            for point_id in area.point_ids:
                point_df = self.tables.get('POINTS_3D', pd.DataFrame())
                point_rows = point_df[point_df['point_id'] == point_id]
                if not point_rows.empty:
                    point = point_rows.iloc[0]
                    points_3d.append({
                        'x': point['x'],
                        'y': point['y'],
                        'z': point['z']
                    })
                    z_values.append(point['z'])
            
            if points_3d:
                # Calculate average Z for the area
                avg_z = sum(z_values) / len(z_values) if z_values else 0
                
                area_entry = {
                    'area_id': area_name,
                    'type': area.type,
                    'num_points': len(area.point_ids),
                    'point_ids': ','.join(area.point_ids),
                    'avg_z': avg_z,
                    'min_z': min(z_values) if z_values else 0,
                    'max_z': max(z_values) if z_values else 0,
                }
                
                # Add individual point coordinates
                for i, point in enumerate(points_3d):
                    area_entry[f'x{i+1}'] = point['x']
                    area_entry[f'y{i+1}'] = point['y']
                    area_entry[f'z{i+1}'] = point['z']
                
                # Add assigns if available
                assigns = area_assign_dict.get(area_name, [])
                if assigns:
                    area_entry['story'] = assigns[0].get('story', '')
                    area_entry['section'] = assigns[0].get('SECTION', '')
                    area_entry['pier'] = assigns[0].get('PIER', '')
                    area_entry['diaph'] = assigns[0].get('DIAPH', '')
                
                area_data.append(area_entry)
        
        if area_data:
            self.tables['AREAS_3D'] = pd.DataFrame(area_data)
    
    def _process_section(self, section_name: str):
        """Process a section based on its type"""
        lines = self.raw_sections.get(section_name, [])
        if not lines:
            return
        
        section_key = section_name.replace(' ', '_').replace('/', '_')
        
        # Get parse method based on section type
        parse_type = self.SECTION_TYPES.get(section_name, 'generic')
        parse_method = getattr(self, f"_parse_{parse_type}", None)
        
        if parse_method:
            data = parse_method(lines, section_name)
        else:
            data = self._parse_generic(lines, section_name)
        
        if data:
            self.tables[section_key] = pd.DataFrame(data)
    
    def _parse_generic(self, lines: List[str], section_name: str) -> List[Dict]:
        """Generic parser for any section"""
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if parts:
                row = {'raw_line': line}
                
                # Try to parse as key-value pairs
                i = 0
                while i < len(parts):
                    if i + 1 < len(parts) and not parts[i].startswith('"'):
                        # Potential key-value pair
                        key = parts[i]
                        value = self._try_convert(parts[i + 1])
                        row[key] = value
                        i += 2
                    else:
                        # Just store as value
                        row[f'col_{i}'] = self._try_convert(parts[i])
                        i += 1
                
                data.append(row)
        
        return data
    
    def _parse_key_value_pairs(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse sections with key-value pairs"""
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if parts:
                row = {}
                i = 0
                while i < len(parts):
                    if i + 1 < len(parts):
                        key = parts[i]
                        value = self._try_convert(parts[i + 1])
                        row[key] = value
                        i += 2
                    else:
                        i += 1
                data.append(row)
        return data
    
    def _parse_simple_list(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse simple lists (like PIER/SPANDREL NAMES)"""
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 2:
                data.append({
                    'type': parts[0],
                    'name': parts[1].strip('"')
                })
        return data
    
    def _parse_materials(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse MATERIAL PROPERTIES section"""
        data = []
        current_material = {}
        
        for line in lines:
            parts = self._parse_line(line)
            if not parts:
                continue
            
            if parts[0] == 'MATERIAL' and len(parts) >= 3:
                if current_material:
                    data.append(current_material)
                
                current_material = {
                    'name': parts[1].strip('"'),
                }
                
                # Parse remaining
                i = 2
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_material[key] = value
                    i += 2
            else:
                # Continuation of previous material
                i = 0
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_material[key] = value
                    i += 2
        
        if current_material:
            data.append(current_material)
        
        return data
    
    def _parse_frame_sections(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse FRAME SECTIONS section"""
        data = []
        current_section = {}
        
        for line in lines:
            parts = self._parse_line(line)
            if not parts:
                continue
            
            if parts[0] == 'FRAMESECTION' and len(parts) >= 3:
                if current_section:
                    data.append(current_section)
                    self.frame_sections[current_section.get('name', '')] = current_section
                
                current_section = {
                    'type': 'FRAMESECTION',
                    'name': parts[1].strip('"')
                }
                
                i = 2
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_section[key] = value
                    i += 2
            else:
                # Continuation
                i = 0
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_section[key] = value
                    i += 2
        
        if current_section:
            data.append(current_section)
            self.frame_sections[current_section.get('name', '')] = current_section
        
        return data
    
    def _parse_shell_props(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse SHELLPROP sections"""
        data = []
        current_prop = {}
        
        for line in lines:
            parts = self._parse_line(line)
            if not parts:
                continue
            
            if parts[0] == 'SHELLPROP' and len(parts) >= 3:
                if current_prop:
                    data.append(current_prop)
                    self.shell_props[current_prop.get('name', '')] = current_prop
                
                current_prop = {
                    'name': parts[1].strip('"')
                }
                
                i = 2
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_prop[key] = value
                    i += 2
            else:
                # Continuation
                i = 0
                while i < len(parts) - 1:
                    key = parts[i]
                    value = self._try_convert(parts[i + 1])
                    current_prop[key] = value
                    i += 2
        
        if current_prop:
            data.append(current_prop)
            self.shell_props[current_prop.get('name', '')] = current_prop
        
        return data
    
    def _parse_line_assigns(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse LINE ASSIGNS section"""
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 4 and parts[0] == 'LINEASSIGN':
                row = {
                    'LINEASSIGN': parts[0],
                    'name': parts[1].strip('"'),
                    'story': parts[2].strip('"')
                }
                
                i = 3
                while i < len(parts) - 1:
                    key = parts[i]
                    value = parts[i + 1].strip('"')
                    row[key] = self._try_convert(value)
                    i += 2
                
                data.append(row)
        
        return data
    
    def _parse_area_assigns(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse AREA ASSIGNS section"""
        data = []
        for line in lines:
            parts = self._parse_line(line)
            if len(parts) >= 4 and parts[0] == 'AREAASSIGN':
                row = {
                    'AREAASSIGN': parts[0],
                    'name': parts[1].strip('"'),
                    'story': parts[2].strip('"')
                }
                
                i = 3
                while i < len(parts) - 1:
                    key = parts[i]
                    value = parts[i + 1].strip('"')
                    row[key] = self._try_convert(value)
                    i += 2
                
                data.append(row)
        
        return data
    
    def _parse_load_combinations(self, lines: List[str], section_name: str) -> List[Dict]:
        """Parse LOAD COMBINATIONS section"""
        data = []
        current_combo = {}
        
        for line in lines:
            parts = self._parse_line(line)
            if not parts:
                continue
            
            if parts[0] == 'COMBO' and len(parts) >= 3:
                if current_combo:
                    data.append(current_combo)
                
                current_combo = {
                    'name': parts[1].strip('"'),
                    'type': parts[3] if len(parts) > 3 else ''
                }
            elif parts[0] in ['LOADCASE', 'LOADCOMBO'] and len(parts) >= 4:
                if current_combo:
                    key = f"{parts[0]}_{parts[1].strip('"')}"
                    current_combo[key] = parts[3]
        
        if current_combo:
            data.append(current_combo)
        
        return data
    
    # Helper methods for data access
    
    def get_points_by_story(self, story_name: str) -> pd.DataFrame:
        """Get all points for a specific story"""
        points_df = self.tables.get('POINTS_3D', pd.DataFrame())
        if not points_df.empty:
            return points_df[points_df['story'] == story_name]
        return pd.DataFrame()
    
    def get_lines_by_story(self, story_name: str) -> pd.DataFrame:
        """Get all lines for a specific story"""
        lines_df = self.tables.get('LINES_3D', pd.DataFrame())
        if not lines_df.empty and 'story' in lines_df.columns:
            return lines_df[lines_df['story'] == story_name]
        return pd.DataFrame()
    
    def get_areas_by_story(self, story_name: str) -> pd.DataFrame:
        """Get all areas for a specific story"""
        areas_df = self.tables.get('AREAS_3D', pd.DataFrame())
        if not areas_df.empty and 'story' in areas_df.columns:
            return areas_df[areas_df['story'] == story_name]
        return pd.DataFrame()
    
    def get_frame_section(self, section_name: str) -> Dict:
        """Get frame section properties"""
        return self.frame_sections.get(section_name, {})
    
    def get_shell_prop(self, prop_name: str) -> Dict:
        """Get shell property"""
        return self.shell_props.get(prop_name, {})


# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Parse the file
    parser = E2KParser("D:/Projects/deneme/1.$et")
    
    
    # Access parsed data
    print("\n=== STORIES ===")
    print(parser.tables.get('STORIES', pd.DataFrame()))
    
    print("\n=== POINTS 3D ===")
    print(parser.tables.get('POINTS_3D', pd.DataFrame()).head())
    
    print("\n=== LINES 3D ===")
    print(parser.tables.get('LINES_3D', pd.DataFrame()).head())
    
    print("\n=== AREAS 3D ===")
    print(parser.tables.get('AREAS_3D', pd.DataFrame()).head())
    
    print("\n=== FRAME SECTIONS ===")
    print(parser.tables.get('FRAME_SECTIONS', pd.DataFrame()))
    
    # Get points for a specific story
    story7_points = parser.get_points_by_story('Story7')
    print(f"\n=== Points in Story7: {len(story7_points)} points ===")
    
    