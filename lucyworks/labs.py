import pandas as pd

LAB_OBJECTS = [
    {"object": "sample", "purpose": "sample taken from case"},
    {"object": "sample_type", "purpose": "blood, urine, cytology, other"},
    {"object": "test_panel", "purpose": "requested test or panel"},
    {"object": "test_result", "purpose": "result linked to case and reviewer"},
    {"object": "analyser_run", "purpose": "in-house analyser execution"},
    {"object": "send_out_lab_order", "purpose": "external lab request"},
]


def lab_model_table():
    return pd.DataFrame(LAB_OBJECTS)
