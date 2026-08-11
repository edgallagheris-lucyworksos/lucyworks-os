# Manual Day Control Smoke retirement

The legacy `.github/workflows/manual-day-control-smoke.yml` workflow was retired because it duplicated the retained `Day Control Check` gate.

The retired workflow ran on every push to `main` and used Python 3.11. The retained day-control workflow is domain-scoped, uses the repository's current Python 3.12 test environment, and runs `apps/api/day_control_smoke_test.py` only when day-control code or its workflow changes.

This removes duplicate failure notifications without removing day-control regression coverage.
