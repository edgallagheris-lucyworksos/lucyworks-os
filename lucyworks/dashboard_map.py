import pandas as pd

DASHBOARD_MAP = [
    {"view": "Hospital Operational Dashboard", "owner": "ops manager", "purpose": "whole hospital control"},
    {"view": "Department Command View", "owner": "department lead", "purpose": "team, work, resources, problems"},
    {"view": "Team or Personal Execution View", "owner": "individual staff", "purpose": "current work and blockers"},
    {"view": "Case Detail View", "owner": "clinical or ops", "purpose": "case truth and next action"},
    {"view": "Room Detail View", "owner": "clinical or ops", "purpose": "room state and turnover"},
]


def dashboard_map_table():
    return pd.DataFrame(DASHBOARD_MAP)
