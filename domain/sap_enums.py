#domain/sap_enums.py

# SAP2000 enums
UNIT_DEFINITIONS = {
    1: ('lb', 'in'),
    2: ('lb', 'ft'),
    3: ('kip', 'in'),
    4: ('kip', 'ft'),
    5: ('kN', 'mm'),
    6: ('kN', 'm'),
    7: ('kgf', 'mm'),
    8: ('kgf', 'm'),
    9: ('N', 'mm'),
    10: ('N', 'm'),
    11: ('Ton', 'mm'),
    12: ('Ton', 'm'),
    13: ('kN', 'cm'),
    14: ('kgf', 'cm'),
    15: ('N', 'cm'),
    16: ('Ton', 'cm')
}

# Enumerations
LOAD_PATTERN_TYPES = {
    1: "DEAD",
    2: "SUPERDEAD",
    3: "LIVE",
    4: "REDUCELIVE",
    5: "QUAKE",
    6: "WIND",
    7: "SNOW",
    8: "OTHER",
    9: "MOVE",
    10: "TEMPERATURE",
    11: "ROOFLIVE",
    12: "NOTIONAL",
    13: "PATTERNLIVE",
    14: "WAVE",
    15: "BRAKING",
    16: "CENTRIFUGAL",
    17: "FRICTION",
    18: "ICE",
    19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE",
    21: "VERTICALEARTHPRESSURE",
    22: "EARTHSURCHARGE",
    23: "DOWNDRAG",
    24: "VEHICLECOLLISION",
    25: "VESSELCOLLISION",
    26: "TEMPERATUREGRADIENT",
    27: "SETTLEMENT",
    28: "SHRINKAGE",
    29: "CREEP",
    30: "WATERLOADPRESSURE",
    31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES",
    33: "PEDESTRIANLL",
    34: "PRESTRESS",
    35: "HYPERSTATIC",
    36: "BOUYANCY",
    37: "STREAMFLOW",
    38: "IMPACT",
    39: "CONSTRUCTION"
}

LOAD_CASE_TYPES = {
    1: "LinearStatic",
    2: "NonlinearStatic",
    3: "Modal",
    4: "ResponseSpectrum",
    5: "LinearHistory",           # Modal Time History
    6: "NonlinearHistory",        # Modal Time History
    7: "LinearDynamic",           # Direct Integration Time History
    8: "NonlinearDynamic",        # Direct Integration Time History
    9: "MovingLoad",
    10: "Buckling",
    11: "SteadyState",
    12: "PowerSpectralDensity",
    13: "LinearStaticMultistep",
    14: "Hyperstatic",
    15: "ExternalResults",
    16: "StagedConstruction",
    17: "NonlinearStaticMultiStep"
}

LOAD_CASE_DESIGN_TYPES = {
    1: "DEAD", 2: "SUPERDEAD", 3: "LIVE", 4: "REDUCELIVE", 5: "QUAKE", 6: "WIND", 7: "SNOW",
    8: "OTHER", 9: "MOVE", 10: "TEMPERATURE", 11: "ROOFLIVE", 12: "NOTIONAL", 13: "PATTERNLIVE",
    14: "WAVE", 15: "BRAKING", 16: "CENTRIFUGAL", 17: "FRICTION", 18: "ICE", 19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE", 21: "VERTICALEARTHPRESSURE", 22: "EARTHSURCHARGE", 23: "DOWNDRAG",
    24: "VEHICLECOLLISION", 25: "VESSELCOLLISION", 26: "TEMPERATUREGRADIENT", 27: "SETTLEMENT",
    28: "SHRINKAGE", 29: "CREEP", 30: "WATERLOADPRESSURE", 31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES", 33: "PEDESTRIANLL", 34: "PRESTRESS", 35: "HYPERSTATIC", 36: "BOUYANCY",
    37: "STREAMFLOW", 38: "IMPACT", 39: "CONSTRUCTION", 40: "DEADWEARING", 41: "DEADWATER",
    42: "DEADMANUFACTURE", 43: "EARTHHYDROSTATIC", 44: "PASSIVEEARTHPRESSURE",
    45: "ACTIVEEARTHPRESSURE", 46: "PEDESTRIANLLREDUCED", 47: "SNOWHIGHALTITUDE", 48: "EUROLM1CHAR",
    49: "EUROLM1FREQ", 50: "EUROLM2", 51: "EUROLM3", 52: "EUROLM4"
}

OBJECT_TYPE_MAP = {
    1: "Point",
    2: "Frame",
    3: "Cable",
    4: "Tendon",
    5: "Area",
    6: "Solid",
    7: "Link"
}

COMBOTYPE = {
#This is 0, 1, 2, 3 or 4 indicating the load combination type.
0 : "Linear Additive",
1 : "Envelope",
2 : "Absolute Additive",
3 : "SRSS",
4 : "Range Additive",
}