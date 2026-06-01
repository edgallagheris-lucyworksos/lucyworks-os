import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_shadow_mode_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING SHADOW MODE SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        episodes = client.get("/api/episodes").json()
        assert episodes, "No seeded episodes"
        episode = episodes[0]

        payload = {
            "actor_name": "Shadow Smoke Test",
            "rows": [
                {
                    "external_ref": "shadow-1",
                    "episode_ref": episode["episode_ref"],
                    "patient_name": episode.get("patient_name") or "Known patient",
                    "stage": episode.get("current_phase") or "intake",
                    "room": episode.get("current_room_name") or "Unknown room",
                    "owner_role": "clinician",
                    "status": "imported",
                },
                {
                    "external_ref": "shadow-unknown",
                    "episode_ref": "EP-DOES-NOT-EXIST",
                    "patient_name": "Unknown",
                    "stage": "wrong-stage",
                    "room": "wrong-room",
                    "owner_role": "nurse",
                    "status": "imported",
                },
            ],
        }

        r = client.post("/api/shadow-mode/import-rows", json=payload)
        assert r.status_code == 200, r.text
        imported = r.json()
        assert imported["ok"] is True
        assert imported["created_count"] == 2
        ids = [record["id"] for record in imported["records"]]
        print("Import OK")

        r = client.get("/api/shadow-mode/records")
        assert r.status_code == 200, r.text
        records = r.json()
        assert records["count"] == 2
        print("Records OK")

        r = client.post("/api/shadow-mode/validate")
        assert r.status_code == 200, r.text
        validated = r.json()
        assert validated["ok"] is True
        assert validated["count"] == 2
        assert any("unknown_episode" in item["mismatches"] for item in validated["results"])
        print("Validate OK")

        r = client.post("/api/shadow-mode/approve", json={"ids": [ids[0]], "actor_name": "Shadow Smoke Test", "note": "known good row"})
        assert r.status_code == 200, r.text
        approved = r.json()
        assert approved["ok"] is True
        assert approved["records"][0]["approved"] is True
        print("Approve OK")

        r = client.post("/api/shadow-mode/reject", json={"ids": [ids[1]], "actor_name": "Shadow Smoke Test", "note": "bad external ref"})
        assert r.status_code == 200, r.text
        rejected = r.json()
        assert rejected["ok"] is True
        assert rejected["records"][0]["rejected"] is True
        print("Reject OK")

        r = client.get("/api/shadow-mode/summary")
        assert r.status_code == 200, r.text
        summary = r.json()
        assert summary["count"] == 2
        assert summary["approved"] == 1
        assert summary["rejected"] == 1
        print("Summary OK")

    print("\n--- SHADOW MODE SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
