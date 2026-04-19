import json
from datetime import datetime


def audit_event(event: dict, path="lucyworks_audit.jsonl"):
    event["logged_at"] = datetime.utcnow().isoformat() + "Z"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
