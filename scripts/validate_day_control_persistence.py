from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "apps/api/app/schedule_state_models.py",
    ROOT / "apps/api/app/day_control_routes.py",
    ROOT / "backend/app/schedule_state_models.py",
    ROOT / "backend/app/day_control_routes.py",
    ROOT / "apps/api/day_control_smoke_test.py",
]
for path in required:
    assert path.exists(), f"Missing {path}"

for main_path in [ROOT / "apps/api/app/main.py", ROOT / "backend/app/main.py"]:
    text = main_path.read_text()
    assert "day_control_routes" in text, f"day-control routes not imported in {main_path}"
    assert "day_control_router" in text, f"day-control router not included in {main_path}"

route_text = (ROOT / "apps/api/app/day_control_routes.py").read_text()
for token in ["ScheduleStateBlock", "ScheduleStateEvent", "get_session", "/blocks", "/audit"]:
    assert token in route_text, f"Missing {token} in day-control route"

print("day-control persistence validator passed")
