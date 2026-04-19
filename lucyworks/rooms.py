import pandas as pd

ROOM_TYPES = [
    {"room_type": "consult", "purpose": "consult room"},
    {"room_type": "theatre", "purpose": "procedure room"},
    {"room_type": "prep", "purpose": "pre-procedure preparation"},
    {"room_type": "recovery", "purpose": "post-procedure recovery"},
    {"room_type": "icu_bay", "purpose": "critical care space"},
    {"room_type": "ward_kennel", "purpose": "inpatient ward space"},
    {"room_type": "isolation", "purpose": "isolation room"},
    {"room_type": "imaging_suite", "purpose": "scanner and imaging area"},
    {"room_type": "lab_area", "purpose": "lab work area"},
    {"room_type": "pharmacy_area", "purpose": "medication storage and dispense area"},
]


def room_type_table():
    return pd.DataFrame(ROOM_TYPES)
