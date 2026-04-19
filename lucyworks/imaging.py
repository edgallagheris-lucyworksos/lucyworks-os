import os
import pandas as pd

IMAGING_RESOURCES_PATH = "assets/imaging_resources.csv"
IMAGING_OBJECTS = [
    {"object": "MRI", "purpose": "magnetic resonance imaging workflow"},
    {"object": "CT", "purpose": "computed tomography workflow"},
    {"object": "X_RAY", "purpose": "radiography workflow"},
    {"object": "ULTRASOUND", "purpose": "ultrasound workflow"},
    {"object": "imaging_booking", "purpose": "scan booking and slot control"},
    {"object": "scanner_room", "purpose": "resource and room allocation"},
    {"object": "imaging_result", "purpose": "report and review status"},
]
DEFAULT_RESOURCES = [
    {"resource_id": "IMG001", "name": "MRI Scanner 1", "modality": "MRI", "room": "MRI Suite", "status": "ready"},
    {"resource_id": "IMG002", "name": "CT Scanner 1", "modality": "CT", "room": "CT Suite", "status": "ready"},
]


def imaging_model_table():
    return pd.DataFrame(IMAGING_OBJECTS)


def load_imaging_resources():
    if os.path.exists(IMAGING_RESOURCES_PATH):
        return pd.read_csv(IMAGING_RESOURCES_PATH)
    return pd.DataFrame(DEFAULT_RESOURCES)


def imaging_resource_table():
    return load_imaging_resources()


def imaging_status_summary():
    df = load_imaging_resources()
    if df.empty or "status" not in df.columns:
        return pd.DataFrame(columns=["status", "count"])
    return df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
