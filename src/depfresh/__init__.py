#!/usr/bin/env python3
"""depfresh: Check if pyproject.toml dependencies are up to date with PyPI.

Unlike `pip list --outdated`, depfresh checks DECLARED dependencies in
pyproject.toml against PyPI without installing anything. Useful for CI
pipelines and quick health checks across many projects.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional

import httpx
from packaging.version import Version, InvalidVersion
from packaging.requirements import Requirement


def parse_pyproject(pyproject_path: Path) -> list[Requirement]:
    """Parse pyproject.toml and extract dependency Requirements."""
    import tomllib

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    dep_strings = data.get("project", {}).get("dependencies", [])
    return [Requirement(s) for s in dep_strings]


def get_latest_version(package_name: str, client: httpx.Client) -> Optional[str]:
    """Fetch latest version from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = client.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        return data.get("info", {}).get("version")
    except (httpx.HTTPError, KeyError, json.JSONDecodeError):
        return None


def version_is_outdated(req: Requirement, latest: str) -> bool:
    """Check if the declared requirement doesn't include the latest version."""
    if not req.specifier:
        return False  # No constraint means any version is fine

    try:
        latest_version = Version(latest)
        return latest_version not in req.specifier
    except InvalidVersion:
        return False


def format_spec(req: Requirement) -> str:
    """Format the requirement specifier for display."""
    if not req.specifier:
        return "(any)"
    return str(req.specifier)


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found", file=sys.stderr)
        return 1

    try:
        deps = parse_pyproject(pyproject_path)
    except Exception as e:
        print(f"Error parsing pyproject.toml: {e}", file=sys.stderr)
        return 1

    if not deps:
        print("No dependencies found in pyproject.toml")
        return 0

    print(f"Checking {len(deps)} dependencies...\n")

    outdated: list[Requirement] = []
    with httpx.Client() as client:
        for req in deps:
            latest = get_latest_version(req.name, client)
            if latest is None:
                print(f"⚠️  {req.name}: could not fetch version")
                continue

            spec_str = format_spec(req)
            if version_is_outdated(req, latest):
                print(f"🔄 {req.name}: declared {spec_str}, latest {latest}")
                outdated.append(req)
            else:
                print(f"✓  {req.name}: up to date ({spec_str})")

    print()
    if outdated:
        print(f"Found {len(outdated)} outdated dependencies")
        return 1
    else:
        print("All dependencies are up to date!")
        return 0


