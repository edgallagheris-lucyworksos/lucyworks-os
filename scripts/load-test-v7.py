#!/usr/bin/env python3
"""Non-destructive LucyWorks v7 load harness.

Default mode performs authenticated reads only. Pass --write-events to publish
synthetic durable events; never use real patient identifiers in this harness.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid

import httpx


async def login(client: httpx.AsyncClient, user_id: int) -> None:
    response = await client.post("/api/auth/dev-login", json={"user_id": user_id})
    response.raise_for_status()


def csrf(client: httpx.AsyncClient) -> str:
    value = client.cookies.get("lucyworks_csrf")
    if not value:
        raise RuntimeError("CSRF cookie was not issued")
    return value


async def request_once(client: httpx.AsyncClient, path: str, write_events: bool, index: int) -> tuple[float, int]:
    started = time.perf_counter()
    try:
        if write_events and index % 5 == 0:
            response = await client.post(
                "/api/v7/events",
                headers={"X-CSRF-Token": csrf(client)},
                json={
                    "event_type": "load_test_event",
                    "aggregate_type": "synthetic_load",
                    "aggregate_ref": f"load-{index}",
                    "payload": {"synthetic": True, "index": index},
                    "severity": "info",
                    "idempotency_key": f"load-test-{uuid.uuid4().hex}",
                },
            )
        else:
            response = await client.get(path)
        elapsed = (time.perf_counter() - started) * 1000
        return elapsed, response.status_code
    except Exception:
        return (time.perf_counter() - started) * 1000, 599


async def run(args: argparse.Namespace) -> int:
    limits = httpx.Limits(max_connections=args.concurrency * 2, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), follow_redirects=True, limits=limits, timeout=timeout) as client:
        await login(client, args.user_id)
        paths = [
            "/api/health/ready",
            "/api/auth/me",
            "/api/v7/events?after_sequence=0&limit=50",
            "/api/v7/shadow/summary",
            "/api/clinical-execution/governed/dashboard",
            "/api/bvs-v6/dashboard",
        ]
        semaphore = asyncio.Semaphore(args.concurrency)

        async def guarded(index: int):
            async with semaphore:
                return await request_once(client, paths[index % len(paths)], args.write_events, index)

        results = await asyncio.gather(*(guarded(index) for index in range(args.requests)))

    latencies = [latency for latency, _ in results]
    failures = [status for _, status in results if status >= 400]
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    error_rate = len(failures) / max(1, len(results))
    print({
        "requests": len(results),
        "concurrency": args.concurrency,
        "mean_ms": round(statistics.fmean(latencies), 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max(latencies), 2),
        "errors": len(failures),
        "error_rate": round(error_rate, 5),
        "statuses": {str(status): sum(1 for _, observed in results if observed == status) for status in sorted(set(status for _, status in results))},
    })
    if error_rate > args.max_error_rate:
        print(f"FAIL error rate {error_rate:.3%} exceeds {args.max_error_rate:.3%}")
        return 1
    if p95 > args.max_p95_ms:
        print(f"FAIL p95 {p95:.1f}ms exceeds {args.max_p95_ms:.1f}ms")
        return 1
    print("PASS LucyWorks v7 load thresholds")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-p95-ms", type=float, default=1500.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--write-events", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
