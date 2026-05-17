import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "readiness_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.main import app

print("\n--- RUNNING BVS READINESS SMOKE TEST ---\n")

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    r = client.get("/api/readiness/bvs")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["target"] == "BVS/CVS-style specialist veterinary hospital operating system"
    assert "overall_status" in data
    assert "summary" in data
    assert "layers" in data
    assert "metrics" in data
    assert "next_required_build_slices" in data
    assert len(data["layers"]) >= 8
    layer_names = {layer["layer"] for layer in data["layers"]}
    for required in ["Hospital structure", "Staffing / HR", "15-minute scheduling", "Overnight / inpatients", "Flow state / LIVE gates", "Pharmacy / stock", "Audit / governance"]:
        assert required in layer_names, f"Missing readiness layer: {required}"
    print("BVS readiness endpoint OK")

print("\n--- BVS READINESS TEST PASSED ---\n")
