# test_profile.py
from geometry.profile_generator import ProfileGenerator
from domain.definition import SectionType
import numpy as np
import logging
logger = logging.getLogger(__name__)

pg = ProfileGenerator()

# Her profil tipini test et
for st in [SectionType.RECT, SectionType.I, SectionType.L, SectionType.T, 
           SectionType.CIRCLE, SectionType.PIPE, SectionType.TUBE]:
    params = {}
    if st == SectionType.RECT:
        params = {"b": 100, "h": 200}
    elif st == SectionType.I:
        params = {"b": 150, "h": 300, "tw": 10, "tf": 14}
    elif st == SectionType.L:
        params = {"b": 80, "h": 100, "t": 8}
    elif st == SectionType.T:
        params = {"b": 120, "h": 150, "tw": 10, "tf": 15}
    elif st == SectionType.CIRCLE:
        params = {"r": 50, "n": 8}
    elif st == SectionType.PIPE:
        params = {"ro": 60, "ri": 50, "n": 8}
    elif st == SectionType.TUBE:
        params = {"b": 100, "h": 200, "t": 10}
    
    profile = pg.get_profile(st, params)
    # logger.debug(f"{st}: {len(profile)} points")
    # logger.debug(f"  Min: ({profile[:,0].min():.1f}, {profile[:,1].min():.1f})")
    # logger.debug(f"  Max: ({profile[:,0].max():.1f}, {profile[:,1].max():.1f})")
    # logger.debug(f"  First: ({profile[0,0]:.1f}, {profile[0,1]:.1f})")
    # logger.debug()