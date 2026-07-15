#!/usr/bin/env python3
"""Fail unless the pure-pipeline evidence is strong enough to claim success."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from report_pure_pipeline_next_steps import (  # noqa: E402
    TARGETS,
    make_report,
    repo_root_from_script,
)


LEVELS = ("build", "gate", "full", "completion")


def target_state(report: dict[str, Any], target: str) -> dict[str, Any] | None:
    for state in report.get("targets", []):
        if state.get("target") == target:
            return state
    return None


def claim_for_level(
    report: dict[str, Any],
    level: str,
    target: str | None,
) -> dict[str, Any]:
    if level == "completion":
        completion = report.get("completion_claim", {})
        return {
            "level": level,
            "target": "all",
            "claimable": bool(completion.get("claimable")),
            "missing": list(completion.get("missing") or []),
            "interpretation": str(completion.get("interpretation", "")),
            "xclbin": "",
            "launch_command": "",
        }

    if not target:
        raise ValueError("--target is required for build/gate/full claim checks")

    state = target_state(report, target)
    if state is None:
        raise ValueError(f"unknown target in report: {target}")

    claim = state.get("claim_status", {})
    return {
        "level": level,
        "target": target,
        "claimable": bool(claim.get(f"{level}_claimable")),
        "missing": list(claim.get(f"{level}_missing") or []),
        "interpretation": (
            f"{target} {level} claim is proven"
            if claim.get(f"{level}_claimable")
            else f"{target} {level} claim is missing required evidence"
        ),
        "xclbin": state.get("xclbin", ""),
        "launch_command": state.get("current_launch_packet_command", ""),
    }


def print_text(report: dict[str, Any], claim: dict[str, Any]) -> None:
    print("pure_pipeline_claim")
    print(f"repo={report.get('repo', '')}")
    print(f"branch={report.get('branch', '')}")
    print(f"head={report.get('head', '')}")
    print(f"source_fingerprint_sha256={report.get('source_fingerprint_sha256', '')}")
    print(f"target={claim['target']}")
    print(f"level={claim['level']}")
    print(f"claimable={'yes' if claim['claimable'] else 'no'}")
    print(f"missing={','.join(claim['missing']) or 'none'}")
    if claim.get("xclbin"):
        print(f"xclbin={claim['xclbin']}")
    if claim.get("launch_command"):
        print(f"launch_command={claim['launch_command']}")
    print(f"interpretation={claim['interpretation']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--level", choices=LEVELS, default="completion")
    parser.add_argument("--target", choices=TARGETS, default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.level != "completion" and not args.target:
        parser.error("--target is required unless --level completion is used")

    report = make_report(args.repo_root.resolve())
    try:
        claim = claim_for_level(report, args.level, args.target or None)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"claim": claim, "report": report}, indent=2, sort_keys=True))
    else:
        print_text(report, claim)
    return 0 if claim["claimable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
