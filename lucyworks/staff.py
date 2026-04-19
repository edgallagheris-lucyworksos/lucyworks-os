import pandas as pd

STAFF_TYPES = [
    {"staff_type": "specialist", "purpose": "consultant or senior clinician"},
    {"staff_type": "nurse", "purpose": "clinical nursing and theatre support"},
    {"staff_type": "reception", "purpose": "front desk and arrivals"},
    {"staff_type": "coordinator", "purpose": "referral and workflow coordination"},
    {"staff_type": "ops_manager", "purpose": "hospital-wide control"},
    {"staff_type": "ward_staff", "purpose": "inpatient ward support"},
    {"staff_type": "icu_staff", "purpose": "critical care support"},
    {"staff_type": "imaging_staff", "purpose": "MRI, CT, X-ray, ultrasound support"},
    {"staff_type": "theatre_staff", "purpose": "prep, procedure, recovery support"},
    {"staff_type": "lab_staff", "purpose": "lab flow and sample handling"},
    {"staff_type": "pharmacy_stock", "purpose": "drug and inventory control"},
]


def default_staff_type_table():
    return pd.DataFrame(STAFF_TYPES)
