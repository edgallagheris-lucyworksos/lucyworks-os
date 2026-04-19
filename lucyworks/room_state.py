import pandas as pd

ROOM_STATES = [
    {"state": "ready", "meaning": "available for use"},
    {"state": "occupied", "meaning": "currently in use"},
    {"state": "cleaning", "meaning": "reset or turnaround in progress"},
    {"state": "blocked", "meaning": "cannot be used"},
    {"state": "reserved", "meaning": "held for upcoming use"},
    {"state": "out_of_service", "meaning": "maintenance or unavailable"},
]


def default_room_state_table():
    return pd.DataFrame(ROOM_STATES)
