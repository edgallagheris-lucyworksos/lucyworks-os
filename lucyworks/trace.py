import json
import hashlib
import os
from datetime import datetime

LAST_HASH = "GENESIS"


def trace_event(event: dict, path="exports/trace.jsonl"):
    global LAST_HASH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    event["logged_at"] = datetime.utcnow().isoformat() + "Z"
    event["prev_hash"] = LAST_HASH
    event["hash"] = hashlib.sha256((LAST_HASH + json.dumps(event, sort_keys=True)).encode()).hexdigest()
    LAST_HASH = event["hash"]

    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
