import os
from datetime import datetime

import pandas as pd

MESSAGES_PATH = "exports/messages.csv"
MESSAGE_TYPES = [
    {"message_type": "referral_ack", "purpose": "acknowledge referral"},
    {"message_type": "arrival_delay", "purpose": "notify operational delay"},
    {"message_type": "owner_update", "purpose": "case update"},
    {"message_type": "discharge_ready", "purpose": "discharge notification"},
    {"message_type": "result_reminder", "purpose": "internal reminder"},
]
MESSAGE_COLUMNS = [
    "message_id",
    "case_id",
    "message_type",
    "audience",
    "channel",
    "status",
    "subject",
    "body",
    "created_at",
]


def message_template_table():
    return pd.DataFrame(MESSAGE_TYPES)


def load_messages():
    if os.path.exists(MESSAGES_PATH):
        return pd.read_csv(MESSAGES_PATH)
    return pd.DataFrame(columns=MESSAGE_COLUMNS)


def save_messages(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(MESSAGES_PATH, index=False)


def append_message(message: dict):
    df = load_messages()
    df = pd.concat([df, pd.DataFrame([message])], ignore_index=True)
    save_messages(df)


def build_message(case_id: str, message_type: str, audience: str, subject: str, body: str, channel: str = "email"):
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return {
        "message_id": case_id + "-" + message_type + "-" + stamp,
        "case_id": case_id,
        "message_type": message_type,
        "audience": audience,
        "channel": channel,
        "status": "draft",
        "subject": subject,
        "body": body,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def case_messages(case_id: str):
    df = load_messages()
    if df.empty:
        return df
    return df[df["case_id"] == case_id]


def message_status_summary():
    df = load_messages()
    if df.empty or "status" not in df.columns:
        return pd.DataFrame(columns=["status", "count"])
    return df.groupby("status", as_index=False).size().rename(columns={"size": "count"})
