import json
import os
from datetime import datetime


def audit_event(event: dict, path="exports/audit.jsonl"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    event["logged_at"] = datetime.utcnow().isoformat() + "Z"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
