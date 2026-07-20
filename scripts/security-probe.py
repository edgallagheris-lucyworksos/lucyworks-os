#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-destructive LucyWorks deployment security probe")
    parser.add_argument("base_url", help="Deployed LucyWorks URL, for example https://lucyworks.example.org")
    parser.add_argument("--token", help="Optional valid senior-user bearer token for authenticated probes")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    parsed = urlparse(base)
    failures: list[str] = []
    results: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        results.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            failures.append(f"{name}: {detail}")

    record("https", parsed.scheme == "https", f"scheme={parsed.scheme}")

    with httpx.Client(base_url=base, follow_redirects=False, timeout=15.0) as client:
        live = client.get("/api/health/live")
        record("liveness", live.status_code == 200, f"status={live.status_code}")
        for header in ("x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"):
            record(f"header:{header}", bool(live.headers.get(header)), live.headers.get(header, "missing"))
        record("request-id", bool(live.headers.get("x-request-id")), live.headers.get("x-request-id", "missing"))

        protected = client.get("/api/production-readiness/dashboard")
        record("anonymous-protected-route", protected.status_code == 401, f"status={protected.status_code}")

        invalid = client.get("/api/production-readiness/dashboard", headers={"Authorization": "Bearer invalid.invalid.invalid"})
        record("invalid-token", invalid.status_code == 401, f"status={invalid.status_code}")

        metrics = client.get("/api/metrics")
        record("metrics-protected", metrics.status_code == 401, f"status={metrics.status_code}")

        options = client.options("/api/production-readiness/dashboard", headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "GET"})
        allow_origin = options.headers.get("access-control-allow-origin", "")
        record("cors-not-reflected", allow_origin != "https://attacker.invalid", f"allow-origin={allow_origin or 'unset'}")

        oversized = client.post("/api/auth/oidc/exchange", content=b"x" * 100_000, headers={"Content-Type": "application/octet-stream"})
        record("malformed-body-rejected", oversized.status_code in {400, 401, 413, 415, 422}, f"status={oversized.status_code}")

        if args.token:
            auth = {"Authorization": f"Bearer {args.token}"}
            me = client.get("/api/auth/me", headers=auth)
            record("valid-token", me.status_code == 200, f"status={me.status_code}")
            dashboard = client.get("/api/production-readiness/dashboard", headers=auth)
            record("authorised-readiness", dashboard.status_code == 200, f"status={dashboard.status_code}")

    print(json.dumps({"baseUrl": base, "passed": not failures, "results": results, "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
