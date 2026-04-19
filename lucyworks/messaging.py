import pandas as pd

MESSAGE_TYPES = [
    {"message_type": "referral_ack", "purpose": "acknowledge referral"},
    {"message_type": "arrival_delay", "purpose": "notify operational delay"},
    {"message_type": "owner_update", "purpose": "case update"},
    {"message_type": "discharge_ready", "purpose": "discharge notification"},
    {"message_type": "result_reminder", "purpose": "internal reminder"},
]


def message_template_table():
    return pd.DataFrame(MESSAGE_TYPES)
