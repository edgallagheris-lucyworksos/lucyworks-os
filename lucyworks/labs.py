import os
import pandas as pd

LAB_TESTS_PATH = "assets/lab_tests.csv"
LAB_OBJECTS = [
    {"object": "sample", "purpose": "sample taken from case"},
    {"object": "sample_type", "purpose": "blood, urine, cytology, other"},
    {"object": "test_panel", "purpose": "requested test or panel"},
    {"object": "test_result", "purpose": "result linked to case and reviewer"},
    {"object": "analyser_run", "purpose": "in-house analyser execution"},
    {"object": "send_out_lab_order", "purpose": "external lab request"},
]
DEFAULT_TESTS = [
    {"test_code": "CBC", "name": "Complete Blood Count", "panel": "haematology", "turnaround_minutes": 30},
    {"test_code": "BIOCHEM", "name": "Biochemistry Panel", "panel": "biochemistry", "turnaround_minutes": 45},
]


def lab_model_table():
    return pd.DataFrame(LAB_OBJECTS)


def load_lab_test_library():
    if os.path.exists(LAB_TESTS_PATH):
        return pd.read_csv(LAB_TESTS_PATH)
    return pd.DataFrame(DEFAULT_TESTS)


def lab_test_library_table():
    return load_lab_test_library()


def fast_turnaround_tests(max_minutes: int = 30):
    df = load_lab_test_library()
    if "turnaround_minutes" not in df.columns:
        return df.head(0)
    return df[df["turnaround_minutes"] <= max_minutes]
