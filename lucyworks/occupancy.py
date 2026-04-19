import pandas as pd

OCCUPANCY_FIELDS = [
    {"field": "space_id", "meaning": "bed, kennel, bay, or room"},
    {"field": "space_type", "meaning": "ICU, ward, recovery, or consult"},
    {"field": "case_id", "meaning": "current occupying case"},
    {"field": "occupied_from", "meaning": "when occupancy began"},
    {"field": "expected_release", "meaning": "planned release time"},
    {"field": "status", "meaning": "occupied, due_transfer, or cleaning"},
]


def occupancy_schema_table():
    return pd.DataFrame(OCCUPANCY_FIELDS)
