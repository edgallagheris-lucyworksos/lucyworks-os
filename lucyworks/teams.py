import pandas as pd

TEAMS = [
    {"team": "Reception", "purpose": "front desk and arrivals"},
    {"team": "Referral Coordination", "purpose": "referrals and bookings"},
    {"team": "Surgery", "purpose": "theatre and surgical workflow"},
    {"team": "Imaging", "purpose": "MRI, CT, X-ray, ultrasound"},
    {"team": "ICU", "purpose": "critical care"},
    {"team": "Wards", "purpose": "inpatient ward management"},
    {"team": "Labs", "purpose": "sample and result processing"},
    {"team": "Pharmacy", "purpose": "drug and stock control"},
    {"team": "Discharge", "purpose": "owner-ready discharge flow"},
    {"team": "Operations", "purpose": "hospital coordination"},
]


def team_table():
    return pd.DataFrame(TEAMS)
