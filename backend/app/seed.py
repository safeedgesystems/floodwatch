"""Demonstration network. All roads, reports and distances are simulated."""

SEED_LOCATIONS = [
    {"id": "RS", "name": "Riverside",         "x": 80,  "y": 330, "shelter": None},
    {"id": "OB", "name": "Old Bridge",        "x": 110, "y": 110, "shelter": None},
    {"id": "MS", "name": "Market Square",     "x": 300, "y": 220, "shelter": None},
    {"id": "HJ", "name": "Hospital Junction", "x": 340, "y": 70,  "shelter": "Medical"},
    {"id": "HC", "name": "Hillcrest",         "x": 520, "y": 120, "shelter": "High ground"},
    {"id": "UG", "name": "University Gate",   "x": 510, "y": 280, "shelter": "Shelter hall"},
    {"id": "AP", "name": "Airport",           "x": 610, "y": 350, "shelter": "Terminal"},
    {"id": "HB", "name": "Harbour",           "x": 280, "y": 380, "shelter": None},
]

SEED_ROADS = [
    {"id": "RS-OB", "a": "RS", "b": "OB", "km": 2.1},
    {"id": "OB-MS", "a": "OB", "b": "MS", "km": 1.8},
    {"id": "RS-MS", "a": "RS", "b": "MS", "km": 2.9},
    {"id": "MS-HJ", "a": "MS", "b": "HJ", "km": 1.2},
    {"id": "HJ-HC", "a": "HJ", "b": "HC", "km": 2.2},
    {"id": "MS-HC", "a": "MS", "b": "HC", "km": 3.0},
    {"id": "HC-UG", "a": "HC", "b": "UG", "km": 1.9},
    {"id": "MS-UG", "a": "MS", "b": "UG", "km": 3.1},
    {"id": "UG-AP", "a": "UG", "b": "AP", "km": 3.4},
    {"id": "MS-HB", "a": "MS", "b": "HB", "km": 2.8},
    {"id": "RS-HB", "a": "RS", "b": "HB", "km": 3.5},
    {"id": "HB-AP", "a": "HB", "b": "AP", "km": 6.8},
]

SEED_MANUAL_BLOCKS = {"RS-MS", "HJ-HC"}

SEED_REPORTS = [
    {"location": "Riverside", "locId": "RS", "roadId": "RS-OB", "severity": "High",
     "description": "Water covering both lanes near the bridge"},
    {"location": "Market Square", "locId": "MS", "roadId": "MS-HJ", "severity": "Medium",
     "description": "Standing water pooling near vendor stalls"},
    {"location": "Hillcrest", "locId": "HC", "roadId": "HJ-HC", "severity": "Low",
     "description": "Minor overflow near residential gate"},
]
