#!/usr/bin/env python3
"""Run post-build validation on an already-built pure-pipeline xclbin.

This wrapper is intentionally post-build only: it never invokes Vitis compile or
link. It sequences the two commands that should run after a manually produced
hw_emu/hw xclbin appears:

1. target-flow postrun validation with --skip-build
2. same-input pure_stage0 matrix comparison
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from report_pure_pipeline_next_steps import (  # noqa: E402
    TARGET_TIMEOUTS,
    make_report,
    postrun_evidence_label,
    repo_root_from_script,
    target_xclbin,
)


def quote_cmd(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def default_labels(repo: Path) -> tuple[str, str]:
    report = make_report(repo)
    return (
        report["stage0_followup"]["pure_label"],
        report["stage0_followup"]["baseline"]["label"],
    )


def build_commands(
    target: str,
    label: str,
    baseline_label: str,
    mode: str,
    gate_case: str,
    gate_timeout: int,
    require_compare: bool,
    skip_postrun: bool,
    skip_matrix: bool,
) -> list[list[str]]:
    commands: list[list[str]] = []
    if not skip_postrun:
        commands.append([
            "./scripts/run_pure_pipeline_target_flow.sh",
            "--target",
            target,
            "--label",
            postrun_evidence_label(label),
            "--skip-build",
            "--gate-case",
            gate_case,
            "--gate-timeout",
            str(gate_timeout),
        ])
    if not skip_matrix:
        matrix = [
            "./scripts/run_pure_stage0_postbuild_matrix.sh",
            "--target",
            target,
            "--mode",
            mode,
            "--label",
            label,
            "--baseline-label",
            baseline_label,
        ]
        if require_compare:
            matrix.append("--require-compare")
        commands.append(matrix)
    return commands


def run_command(command: list[str], dry_run: bool) -> None:
    print("+ " + quote_cmd(command))
    if not dry_run:
        subprocess.check_call(command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--target", choices=("hw_emu", "hw"), default="hw_emu")
    parser.add_argument("--label", default="", help="Pure-pipeline result label. Default: current report pure_label.")
    parser.add_argument("--baseline-label", default="", help="Baseline label. Default: current report baseline label.")
    parser.add_argument("--mode", choices=("gate", "full"), default="gate")
    parser.add_argument("--gate-case", default="tiny_star_v16_u12")
    parser.add_argument("--gate-timeout", type=int, default=0)
    parser.add_argument("--no-require-compare", action="store_true")
    parser.add_argument("--skip-postrun", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true")
    parser.add_argument("--allow-missing-xclbin", action="store_true", help="Only useful with --dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    if args.skip_postrun and args.skip_matrix:
        print("nothing to do: both --skip-postrun and --skip-matrix were set", file=sys.stderr)
        return 2

    report_label, report_baseline_label = default_labels(repo)
    label = args.label or report_label
    baseline_label = args.baseline_label or report_baseline_label
    gate_timeout = args.gate_timeout or TARGET_TIMEOUTS[args.target]
    xclbin = target_xclbin(repo, args.target)

    print(f"repo={repo}")
    print(f"target={args.target}")
    print(f"xclbin={xclbin}")
    print(f"label={label}")
    print(f"baseline_label={baseline_label}")
    print(f"mode={args.mode}")

    if not xclbin.is_file() and not (args.dry_run and args.allow_missing_xclbin):
        print(f"missing xclbin: {xclbin}", file=sys.stderr)
        print("Run the target launch packet first, or pass --dry-run --allow-missing-xclbin to preview.", file=sys.stderr)
        return 1

    commands = build_commands(
        args.target,
        label,
        baseline_label,
        args.mode,
        args.gate_case,
        gate_timeout,
        not args.no_require_compare,
        args.skip_postrun,
        args.skip_matrix,
    )
    for command in commands:
        run_command(command, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
