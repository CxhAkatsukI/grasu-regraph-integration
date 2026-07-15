#!/usr/bin/env python3
"""Wait for a pure-pipeline xclbin, then run post-build acceptance.

This helper is intentionally post-build only. It is useful when a long
hw_emu/hw Vitis launch packet is running in another terminal: this script waits
for the expected xclbin path to appear, then delegates to
run_pure_pipeline_postbuild_acceptance.py for skip-build validation and the
same-input stage0 matrix, followed by machine-checkable claim validation.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from report_pure_pipeline_next_steps import (  # noqa: E402
    TARGET_TIMEOUTS,
    make_report,
    repo_root_from_script,
    target_xclbin,
)


def quote_cmd(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def target_state(report: dict[str, Any], target: str) -> dict[str, Any] | None:
    for state in report.get("targets", []):
        if state.get("target") == target:
            return state
    return None


def default_labels(report: dict[str, Any]) -> tuple[str, str]:
    followup = report["stage0_followup"]
    return followup["pure_label"], followup["baseline"]["label"]


def build_acceptance_command(
    target: str,
    label: str,
    baseline_label: str,
    mode: str,
    gate_case: str,
    gate_timeout: int,
    require_compare: bool,
    skip_postrun: bool,
    skip_matrix: bool,
    skip_claim_check: bool,
) -> list[str]:
    command = [
        "./scripts/run_pure_pipeline_postbuild_acceptance.py",
        "--target",
        target,
        "--label",
        label,
        "--baseline-label",
        baseline_label,
        "--mode",
        mode,
        "--gate-case",
        gate_case,
        "--gate-timeout",
        str(gate_timeout),
    ]
    if not require_compare:
        command.append("--no-require-compare")
    if skip_postrun:
        command.append("--skip-postrun")
    if skip_matrix:
        command.append("--skip-matrix")
    if skip_claim_check:
        command.append("--skip-claim-check")
    return command


def wait_for_xclbin(
    xclbin: Path,
    timeout_seconds: int,
    poll_seconds: int,
    once: bool,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    start = now()
    announced = False
    while True:
        if xclbin.is_file():
            return True
        elapsed = now() - start
        if once:
            return False
        if timeout_seconds > 0 and elapsed >= timeout_seconds:
            return False
        if not announced:
            timeout_text = "forever" if timeout_seconds <= 0 else f"{timeout_seconds}s"
            print(f"waiting for xclbin: {xclbin}")
            print(f"poll_seconds={poll_seconds} timeout={timeout_text}")
            announced = True
        sleep_for = max(1, poll_seconds)
        if timeout_seconds > 0:
            remaining = max(0.0, timeout_seconds - elapsed)
            sleep_for = min(sleep_for, remaining)
            if sleep_for <= 0:
                return False
        sleep(sleep_for)


def run_command(repo: Path, command: list[str], dry_run: bool) -> int:
    print("+ " + quote_cmd(command))
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=repo, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--target", choices=("hw_emu", "hw"), default="hw_emu")
    parser.add_argument("--label", default="", help="Pure-pipeline result label. Default: current report pure_label.")
    parser.add_argument("--baseline-label", default="", help="Baseline label. Default: current report baseline label.")
    parser.add_argument("--mode", choices=("gate", "full"), default="gate")
    parser.add_argument("--gate-case", default="tiny_star_v16_u12")
    parser.add_argument("--gate-timeout", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=0, help="0 means wait without a deadline.")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--once", action="store_true", help="Check once and exit if the xclbin is missing.")
    parser.add_argument("--no-require-compare", action="store_true")
    parser.add_argument("--skip-postrun", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true")
    parser.add_argument("--skip-claim-check", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print the wait target and acceptance command without waiting.")
    args = parser.parse_args()

    if args.skip_postrun and args.skip_matrix:
        print("nothing to do: both --skip-postrun and --skip-matrix were set", file=sys.stderr)
        return 2
    if args.poll_seconds <= 0:
        print("--poll-seconds must be positive", file=sys.stderr)
        return 2
    if args.timeout_seconds < 0:
        print("--timeout-seconds must be non-negative", file=sys.stderr)
        return 2

    repo = args.repo_root.resolve()
    report = make_report(repo)
    report_label, report_baseline_label = default_labels(report)
    label = args.label or report_label
    baseline_label = args.baseline_label or report_baseline_label
    gate_timeout = args.gate_timeout or TARGET_TIMEOUTS[args.target]
    xclbin = target_xclbin(repo, args.target)
    state = target_state(report, args.target) or {}
    launch_command = state.get("current_launch_packet_command")
    claim = state.get("claim_status", {})

    command = build_acceptance_command(
        args.target,
        label,
        baseline_label,
        args.mode,
        args.gate_case,
        gate_timeout,
        not args.no_require_compare,
        args.skip_postrun,
        args.skip_matrix,
        args.skip_claim_check,
    )

    print(f"repo={repo}")
    print(f"target={args.target}")
    print(f"xclbin={xclbin}")
    print(f"xclbin_exists={'yes' if xclbin.is_file() else 'no'}")
    print(f"label={label}")
    print(f"baseline_label={baseline_label}")
    print(f"mode={args.mode}")
    print(f"source_fingerprint_sha256={report.get('source_fingerprint_sha256', '')}")
    if launch_command:
        print(f"launch_command={launch_command}")
    if claim:
        print(f"build_claimable={'yes' if claim.get('build_claimable') else 'no'}")
        print(f"build_missing={','.join(claim.get('build_missing') or []) or 'none'}")
        print(f"gate_claimable={'yes' if claim.get('gate_claimable') else 'no'}")
        print(f"gate_missing={','.join(claim.get('gate_missing') or []) or 'none'}")

    if args.dry_run:
        print("dry_run=yes")
        print("acceptance_command=" + quote_cmd(command))
        return 0

    if not wait_for_xclbin(xclbin, args.timeout_seconds, args.poll_seconds, args.once):
        print(f"missing xclbin: {xclbin}", file=sys.stderr)
        if launch_command:
            print(f"run launch packet first: {launch_command}", file=sys.stderr)
        return 1

    return run_command(repo, command, dry_run=False)


if __name__ == "__main__":
    raise SystemExit(main())
