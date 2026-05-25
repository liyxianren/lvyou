#!/usr/bin/env python3
"""Verify itinerary edits are visible and stale text is gone."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_ROOTS = ("data", "content", "plans", "templates", "static")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_project_files(root: Path):
    for folder in DEFAULT_ROOTS:
        base = root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                yield path


def fetch(base_url: str, route: str) -> str:
    url = base_url.rstrip("/") + route
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root. Default: current directory.")
    parser.add_argument("--base-url", default="", help="Running Flask base URL, for example http://127.0.0.1:5000.")
    parser.add_argument("--stale", action="append", default=[], help="Text that must not appear in project files or rendered pages.")
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help='Rendered-page expectation in the form "/day/day1::text that must appear".',
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    failures: list[str] = []

    trip_path = root / "data" / "trip.json"
    try:
        json.loads(read_text(trip_path))
        print(f"[OK] JSON valid: {trip_path}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Invalid JSON in {trip_path}: {exc}")

    if args.stale:
        for path in iter_project_files(root):
            text = read_text(path)
            for phrase in args.stale:
                if phrase and phrase in text:
                    failures.append(f"Stale text found in {path}: {phrase}")

    if args.base_url:
        routes = {"/", "/itinerary"}
        for expectation in args.expect:
            if "::" not in expectation:
                failures.append(f"Invalid --expect format, expected /path::text: {expectation}")
                continue
            route, _ = expectation.split("::", 1)
            routes.add(route)

        rendered: dict[str, str] = {}
        for route in sorted(routes):
            try:
                rendered[route] = fetch(args.base_url, route)
                print(f"[OK] HTTP {route}")
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                failures.append(f"Could not fetch {route}: {exc}")

        for phrase in args.stale:
            for route, html in rendered.items():
                if phrase and phrase in html:
                    failures.append(f"Stale text found in rendered {route}: {phrase}")

        for expectation in args.expect:
            if "::" not in expectation:
                continue
            route, expected_text = expectation.split("::", 1)
            html = rendered.get(route)
            if html is not None and expected_text not in html:
                failures.append(f"Expected text missing in rendered {route}: {expected_text}")

    if failures:
        print("\n[FAIL]")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("[OK] Travel update consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
