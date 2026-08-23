from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_critical_deadline_v13_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "LUCYWORKS_LEGACY_TEST_BYPASS": "true",
})

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from app.database import engine
from app.hospital_ops_models import CanonicalEpisodeState
from app.main import app

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

try:
    with Session(engine) as session:
        session.add(CanonicalEpisodeState(
            episode_ref="EP-V13-CRITICAL",
            patient_ref="PAT-V13-CRITICAL",
            patient_name="Critical Result Proof Patient",
            premises_ref="default-premises",
            service_line="diagnostics",
            urgency="urgent",
            phase="diagnostics",
            status="active",
            owner_role="clinician",
            next_action="Acknowledge and act on the critical diagnostic result",
        ))
        session.commit()

    with TestClient(app) as client:
        due_at = datetime.now(timezone.utc) - timedelta(minutes=17)
        created = client.post("/api/control-plane/critical-results", json={
            "resultRef": "critical-v13-overdue-001",
            "patientCaseId": "PAT-V13-CRITICAL",
            "referralEpisodeId": "EP-V13-CRITICAL",
            "resultType": "potassium",
            "severity": "red",
            "summary": "Critical potassium result awaiting review",
            "assignedTo": "Operational Proof Clinician",
            "assignedRole": "clinician",
            "dueAt": due_at.isoformat(),
            "createdBy": "synthetic-laboratory",
        })
        assert created.status_code == 200, created.text
        result_id = created.json()["result"]["id"]

        listed = client.get("/api/control-plane/critical-results")
        assert listed.status_code == 200, listed.text
        list_payload = listed.json()
        assert list_payload["count"] == 1
        assert list_payload["overdueCount"] == 1
        overdue_result = list_payload["results"][0]
        assert overdue_result["overdue"] is True
        assert overdue_result["deadlineState"] == "overdue"
        assert overdue_result["minutesOverdue"] >= 16

        dashboard = client.get("/api/control-plane/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        dashboard_payload = dashboard.json()
        assert dashboard_payload["summary"]["unacknowledgedCriticalResults"] == 1
        assert dashboard_payload["summary"]["overdueCriticalResults"] == 1
        assert dashboard_payload["criticalResults"][0]["overdue"] is True
        print("Overdue critical result is visible as a deadline breach")

        acknowledged = client.patch(f"/api/control-plane/critical-results/{result_id}/acknowledge", json={
            "acknowledgedBy": "Operational Proof Clinician",
            "acknowledgedByRole": "clinician",
            "actionTaken": "Patient reviewed immediately and treatment adjusted",
            "note": "Overdue result recovered through escalation",
        })
        assert acknowledged.status_code == 200, acknowledged.text

        cleared = client.get("/api/control-plane/dashboard")
        assert cleared.status_code == 200, cleared.text
        cleared_payload = cleared.json()
        assert cleared_payload["summary"]["unacknowledgedCriticalResults"] == 0
        assert cleared_payload["summary"]["overdueCriticalResults"] == 0
        assert cleared_payload["criticalResults"][0]["overdue"] is False
        assert cleared_payload["criticalResults"][0]["deadlineState"] == "acknowledged"

        duplicate_ack = client.patch(f"/api/control-plane/critical-results/{result_id}/acknowledge", json={
            "acknowledgedBy": "Operational Proof Clinician",
            "acknowledgedByRole": "clinician",
            "actionTaken": "Duplicate acknowledgement attempt",
        })
        assert duplicate_ack.status_code == 409, duplicate_ack.text
        print("Acknowledgement clears the breach and duplicate action is rejected")

    print("\n--- CRITICAL RESULT DEADLINE V13 SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
