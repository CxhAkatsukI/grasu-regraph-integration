#!/usr/bin/env python3
"""Run post-build validation on an already-built pure-pipeline xclbin.

This wrapper is intentionally post-build only: it never invokes Vitis compile or
link. It sequences the commands that should run after a manually produced
hw_emu/hw xclbin appears:

1. target-flow postrun validation with --skip-build
2. same-input pure_stage0 matrix comparison
3. artifact manifest sealing for the requested proof level
4. machine-checkable claim validation for the requested proof level
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from report_pure_pipeline_next_steps import (  # noqa: E402
    TARGET_TIMEOUTS,
    make_report,
    postrun_evidence_label,
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


def label_mismatch_detail(target: str, label: str, state: dict[str, Any]) -> str:
    current_label = state.get("current_launch_packet_flow_label") or ""
    if current_label == label:
        return ""
    return (
        f"target={target} requested_label={label} "
        f"current_launch_packet_flow_label={current_label or 'none'}"
    )


def labels_from_report(report: dict[str, Any]) -> tuple[str, str]:
    followup = report["stage0_followup"]
    return followup["pure_label"], followup["baseline"]["label"]


def default_labels(repo: Path) -> tuple[str, str]:
    return labels_from_report(make_report(repo))


def claim_level_for(mode: str, skip_matrix: bool) -> str:
    if skip_matrix:
        return "build"
    return mode


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
    skip_artifact_manifest: bool,
    skip_claim_check: bool,
) -> list[list[str]]:
    commands: list[list[str]] = []
    claim_level = claim_level_for(mode, skip_matrix)
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
    if not skip_artifact_manifest:
        commands.append([
            "./scripts/collect_pure_pipeline_artifact_manifest.py",
            "--target",
            target,
            "--label",
            label,
            "--baseline-label",
            baseline_label,
            "--mode",
            mode,
            "--level",
            claim_level,
        ])
    if not skip_claim_check:
        commands.append([
            "./scripts/check_pure_pipeline_claim.py",
            "--target",
            target,
            "--level",
            claim_level,
        ])
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
    parser.add_argument("--skip-artifact-manifest", action="store_true")
    parser.add_argument("--skip-claim-check", action="store_true")
    parser.add_argument("--allow-label-mismatch", action="store_true", help="Debug only: continue when --label does not match the target launch packet label.")
    parser.add_argument("--allow-missing-xclbin", action="store_true", help="Only useful with --dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    if args.skip_postrun and args.skip_matrix:
        print("nothing to do: both --skip-postrun and --skip-matrix were set", file=sys.stderr)
        return 2

    report = make_report(repo)
    report_label, report_baseline_label = labels_from_report(report)
    label = args.label or report_label
    baseline_label = args.baseline_label or report_baseline_label
    gate_timeout = args.gate_timeout or TARGET_TIMEOUTS[args.target]
    xclbin = target_xclbin(repo, args.target)
    state = target_state(report, args.target) or {}
    claim = state.get("claim_status", {})

    print(f"repo={repo}")
    print(f"target={args.target}")
    print(f"xclbin={xclbin}")
    print(f"label={label}")
    print(f"baseline_label={baseline_label}")
    print(f"mode={args.mode}")
    print(f"source_fingerprint_sha256={report.get('source_fingerprint_sha256', '')}")
    if state.get("current_launch_packet_command"):
        print(f"launch_command={state['current_launch_packet_command']}")
    if state.get("current_launch_packet_flow_label"):
        print(f"current_launch_packet_flow_label={state['current_launch_packet_flow_label']}")
    if claim:
        print(f"build_claimable={'yes' if claim.get('build_claimable') else 'no'}")
        print(f"build_missing={','.join(claim.get('build_missing') or []) or 'none'}")
        print(f"gate_claimable={'yes' if claim.get('gate_claimable') else 'no'}")
        print(f"gate_missing={','.join(claim.get('gate_missing') or []) or 'none'}")

    mismatch = label_mismatch_detail(args.target, label, state)
    if mismatch:
        print(f"label_mismatch={mismatch}")
        if args.dry_run:
            print("label_mismatch_action=warning_dry_run")
        elif not args.allow_label_mismatch:
            print(
                "label mismatch: postbuild manifest and claim checks are keyed by the current launch packet label",
                file=sys.stderr,
            )
            print(
                "Regenerate the launch packet, use the report's label, or pass --allow-label-mismatch for debugging only.",
                file=sys.stderr,
            )
            return 2
        else:
            print("label_mismatch_action=allowed_debug")

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
        args.skip_artifact_manifest,
        args.skip_claim_check,
    )
    for command in commands:
        run_command(command, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
