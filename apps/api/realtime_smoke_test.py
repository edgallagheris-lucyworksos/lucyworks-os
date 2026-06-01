import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_realtime_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.database import engine
from app.main import app

SQLModel.metadata.drop_all(engine)

print("\n--- RUNNING REALTIME SMOKE TEST ---\n")

try:
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

        r = client.get("/api/realtime/status")
        assert r.status_code == 200, r.text
        status = r.json()
        assert status["stream"] == "available"
        assert "pulse_update" in status["event_types"]
        assert "manual_update" in status["event_types"]
        print("Realtime status OK")

        r = client.get("/api/realtime/events")
        assert r.status_code == 200, r.text
        events = r.json()
        assert events["count"] >= 1
        assert isinstance(events["generated"], list)
        assert any(event["event_type"] == "pulse_update" for event in events["generated"])
        print("Realtime events snapshot OK")

        r = client.post(
            "/api/realtime/publish",
            json={
                "event_type": "manual_update",
                "title": "Smoke test live event",
                "detail": "Published by realtime smoke test",
                "severity": "info",
                "source": "smoke_test",
                "entity_type": "system",
                "entity_id": 1,
                "actor_name": "Realtime Smoke Test",
            },
        )
        assert r.status_code == 200, r.text
        published = r.json()
        assert published["ok"] is True
        assert published["event"]["event_type"] == "manual_update"
        assert published["audit_event"]["action"] == "realtime_event_published"
        print("Realtime publish OK")

        r = client.get("/api/realtime/events")
        assert r.status_code == 200, r.text
        after = r.json()
        assert len(after["published"]) >= 1
        assert any(event["title"] == "Smoke test live event" for event in after["published"])
        print("Published event appears in snapshot OK")

        with client.stream("GET", "/api/realtime/stream") as response:
            assert response.status_code == 200, response.text
            first_chunk = next(response.iter_text())
            assert "event:" in first_chunk or "data:" in first_chunk
        print("Realtime stream OK")

    print("\n--- REALTIME SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
