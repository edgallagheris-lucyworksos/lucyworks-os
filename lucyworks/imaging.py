import pandas as pd

IMAGING_OBJECTS = [
    {"object": "MRI", "purpose": "magnetic resonance imaging workflow"},
    {"object": "CT", "purpose": "computed tomography workflow"},
    {"object": "X_RAY", "purpose": "radiography workflow"},
    {"object": "ULTRASOUND", "purpose": "ultrasound workflow"},
    {"object": "imaging_booking", "purpose": "scan booking and slot control"},
    {"object": "scanner_room", "purpose": "resource and room allocation"},
    {"object": "imaging_result", "purpose": "report and review status"},
]


def imaging_model_table():
    return pd.DataFrame(IMAGING_OBJECTS)
