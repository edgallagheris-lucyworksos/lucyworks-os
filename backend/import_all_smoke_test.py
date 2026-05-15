"""Smoke test that backend modules import cleanly under Python 3.12."""

from app.main import app


def _router_paths() -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


def main() -> None:
    paths = _router_paths()
    required_paths = {
        "/api/health",
        "/api/v3/board",
        "/api/dashboard/intelligence",
    }
    missing = sorted(path for path in required_paths if path not in paths)
    assert not missing, f"Missing required routes after import: {missing}"
    print("import_all_smoke_test: PASS")


if __name__ == "__main__":
    main()
