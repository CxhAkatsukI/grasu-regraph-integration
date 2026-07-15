#!/usr/bin/env python3
"""Collect a reproducible prebuild snapshot for a pure-pipeline target.

The snapshot is intentionally prebuild-only: it records the current launch
packet, source fingerprint, missing claim evidence, same-input baseline label,
and an allow-missing artifact manifest without launching Vitis or hardware
tests. Use it before handing a long hw_emu/hw build command to another shell.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from collect_pure_pipeline_artifact_manifest import build_manifest_rows, read_kv_file, write_manifest
from report_pure_pipeline_next_steps import TARGETS, make_report, print_text, repo_root_from_script


LEVELS = ("build", "gate", "full")
MODES = ("gate", "full")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(repo: Path, path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def path_from_text(repo: Path, text: str | None) -> Path | None:
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else repo / path


def target_state(report: dict[str, Any], target: str) -> dict[str, Any]:
    for state in report.get("targets", []):
        if state.get("target") == target:
            return state
    raise ValueError(f"target not found in report: {target}")


def default_label(report: dict[str, Any], target: str) -> str:
    state = target_state(report, target)
    label = state.get("current_launch_packet_flow_label")
    if label:
        return str(label)
    stage0_label = report.get("stage0_followup", {}).get("pure_label")
    if stage0_label:
        return str(stage0_label)
    raise ValueError(f"no current launch-packet label for target {target}")


def default_baseline_label(report: dict[str, Any]) -> str:
    baseline = report.get("stage0_followup", {}).get("baseline", {})
    label = baseline.get("label")
    if not label:
        raise ValueError("no stage0 baseline label in next-step report")
    return str(label)


def render_next_steps_text(report: dict[str, Any]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_text(report)
    return buffer.getvalue()


def claim_rows(report: dict[str, Any], target: str) -> list[dict[str, str]]:
    state = target_state(report, target)
    rows: list[dict[str, str]] = []
    completion = report.get("completion_claim", {})
    rows.append({
        "scope": "completion",
        "target": "all",
        "level": "completion",
        "claimable": "yes" if completion.get("claimable") else "no",
        "missing": ",".join(completion.get("missing") or []),
        "xclbin": "",
        "launch_command": "",
        "interpretation": str(completion.get("interpretation", "")),
    })

    claim = state.get("claim_status", {})
    for level in LEVELS:
        rows.append({
            "scope": "target",
            "target": target,
            "level": level,
            "claimable": "yes" if claim.get(f"{level}_claimable") else "no",
            "missing": ",".join(claim.get(f"{level}_missing") or []),
            "xclbin": str(state.get("xclbin") or ""),
            "launch_command": str(state.get("current_launch_packet_command") or ""),
            "interpretation": (
                f"{target} {level} claim is proven"
                if claim.get(f"{level}_claimable")
                else f"{target} {level} claim is missing required evidence"
            ),
        })
    return rows


def target_next_command(report: dict[str, Any], target: str) -> str:
    state = target_state(report, target)
    command = state.get("current_launch_packet_command")
    if command:
        return str(command)
    if report.get("next_target") == target:
        next_commands = report.get("next_commands") or []
        if next_commands:
            return str(next_commands[0])
    return ""


def write_claims(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "scope",
        "target",
        "level",
        "claimable",
        "missing",
        "xclbin",
        "launch_command",
        "interpretation",
    )
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def artifact_row(
    repo: Path,
    category: str,
    name: str,
    path: Path | None,
    required: bool,
    detail: str,
) -> dict[str, str]:
    exists = bool(path is not None and path.exists())
    is_file = bool(path is not None and path.is_file())
    return {
        "category": category,
        "name": name,
        "path": display_path(repo, path),
        "exists": "yes" if exists else "no",
        "sha256": sha256(path) if is_file and path is not None else "",
        "size_bytes": str(path.stat().st_size) if is_file and path is not None else "",
        "required": "yes" if required else "no",
        "status": "PASS" if exists or not required else "MISSING",
        "detail": detail,
    }


def snapshot_artifact_rows(
    repo: Path,
    report: dict[str, Any],
    target: str,
    out_dir: Path,
    next_steps_json: Path,
    next_steps_txt: Path,
    claims_tsv: Path,
    manifest_tsv: Path,
    readme_md: Path,
) -> list[dict[str, str]]:
    state = target_state(report, target)
    packet_dir = path_from_text(repo, state.get("current_launch_packet"))
    packet_env = packet_dir / "launch_packet.env" if packet_dir is not None else None
    packet_values = read_kv_file(packet_env)
    build_root = path_from_text(repo, state.get("build_root"))

    rows = [
        artifact_row(repo, "snapshot", "next_steps_json", next_steps_json, True, "machine-readable current next-step report"),
        artifact_row(repo, "snapshot", "next_steps_text", next_steps_txt, True, "human-readable current next-step report"),
        artifact_row(repo, "snapshot", "claim_status", claims_tsv, True, "build/gate/full claim status for this target"),
        artifact_row(repo, "snapshot", "artifact_manifest_allow_missing", manifest_tsv, True, "allow-missing prebuild artifact manifest"),
        artifact_row(repo, "snapshot", "readme", readme_md, True, "prebuild snapshot summary"),
        artifact_row(repo, "target", "xclbin", path_from_text(repo, state.get("xclbin")), False, "expected missing before hw_emu/hw build completes"),
        artifact_row(repo, "launch_packet", "launch_packet_dir", packet_dir, True, "current source-matching launch packet directory"),
        artifact_row(repo, "launch_packet", "launch_packet_env", packet_env, True, "current launch packet environment"),
        artifact_row(repo, "launch_packet", "launch_command", path_from_text(repo, state.get("current_launch_packet_command")), True, "long build command pinned by launch packet"),
        artifact_row(repo, "launch_packet", "source_contracts", path_from_text(repo, packet_values.get("source_contract_out")), True, "prelaunch source contracts"),
        artifact_row(repo, "launch_packet", "source_fingerprints", path_from_text(repo, packet_values.get("source_fingerprints_out")), True, "prelaunch source fingerprints"),
        artifact_row(repo, "launch_packet", "readiness", path_from_text(repo, packet_values.get("readiness_out")), True, "prelaunch readiness report"),
        artifact_row(repo, "launch_packet", "acceptance_gates", path_from_text(repo, packet_values.get("acceptance_gates")), True, "prelaunch acceptance gate spec"),
        artifact_row(repo, "launch_packet", "acceptance_check_prelaunch", path_from_text(repo, packet_values.get("acceptance_check_prelaunch")), True, "prelaunch acceptance check"),
        artifact_row(repo, "build_scripts", "manifest_env", build_root / "manifest.env" if build_root else None, True, "generated target build manifest"),
        artifact_row(repo, "build_scripts", "compile_commands", build_root / "compile_commands.sh" if build_root else None, True, "generated target compile commands"),
        artifact_row(repo, "build_scripts", "link_command", build_root / "link_command.sh" if build_root else None, True, "generated target link command"),
    ]

    helpers = state.get("current_launch_packet_helpers") or {}
    for name, helper_path in sorted(helpers.items()):
        rows.append(artifact_row(
            repo,
            "launch_packet",
            name,
            path_from_text(repo, helper_path),
            target in ("hw_emu", "hw"),
            f"packet-local {name} helper",
        ))
    return rows


def write_snapshot_artifacts(path: Path, rows: list[dict[str, str]]) -> None:
    columns = ("category", "name", "path", "exists", "sha256", "size_bytes", "required", "status", "detail")
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def readme_text(
    report: dict[str, Any],
    target: str,
    label: str,
    baseline_label: str,
    mode: str,
    level: str,
    out_dir: Path,
    claims: list[dict[str, str]],
) -> str:
    state = target_state(report, target)
    missing_by_level = {
        row["level"]: row["missing"] or "none"
        for row in claims
        if row["scope"] == "target"
    }
    next_command = target_next_command(report, target)
    return "\n".join([
        "# Pure Pipeline Prebuild Snapshot",
        "",
        f"Generated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
        "",
        f"Target: `{target}`",
        f"Label: `{label}`",
        f"Baseline label: `{baseline_label}`",
        f"Mode: `{mode}`",
        f"Manifest level: `{level}`",
        f"Integration head: `{report.get('head', '')}`",
        f"Source fingerprint: `{report.get('source_fingerprint_sha256', '')}`",
        f"Dirty: `{str(report.get('dirty', '')).lower()}`",
        "",
        "## Current Claim State",
        "",
        f"- build missing: `{missing_by_level.get('build', 'unknown')}`",
        f"- gate missing: `{missing_by_level.get('gate', 'unknown')}`",
        f"- full missing: `{missing_by_level.get('full', 'unknown')}`",
        f"- xclbin exists: `{'yes' if state.get('xclbin_exists') else 'no'}`",
        f"- xclbin path: `{state.get('xclbin', '')}`",
        "",
        "## Next Command",
        "",
        "```bash",
        next_command,
        "```",
        "",
        "## Snapshot Files",
        "",
        "```text",
        display_path(Path(report.get("repo", ".")), out_dir / "next_steps.json"),
        display_path(Path(report.get("repo", ".")), out_dir / "next_steps.txt"),
        display_path(Path(report.get("repo", ".")), out_dir / "claim_status.tsv"),
        display_path(Path(report.get("repo", ".")), out_dir / f"artifact_manifest_{target}_{level}_{label}_allow_missing.tsv"),
        display_path(Path(report.get("repo", ".")), out_dir / "snapshot_artifacts.tsv"),
        "```",
        "",
        "This snapshot does not launch Vitis. Missing xclbin/postrun/stage0 rows are expected before the long build and postbuild acceptance run.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--target", choices=TARGETS, default="hw_emu")
    parser.add_argument("--label", default="")
    parser.add_argument("--baseline-label", default="")
    parser.add_argument("--mode", choices=MODES, default="gate")
    parser.add_argument("--level", choices=LEVELS, default="gate")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    report = make_report(repo)
    try:
        label = args.label or default_label(report, args.target)
        baseline_label = args.baseline_label or default_baseline_label(report)
        state = target_state(report, args.target)
    except ValueError as exc:
        print(f"ERROR {exc}")
        return 2

    current_label = state.get("current_launch_packet_flow_label")
    if current_label and label != current_label:
        print(f"ERROR label {label} does not match current launch packet label {current_label}")
        return 2

    out_dir = args.out_dir or repo / ".tmp_build" / f"pure_pipeline_prebuild_snapshot_{args.target}_{label}"
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    next_steps_json = out_dir / "next_steps.json"
    next_steps_txt = out_dir / "next_steps.txt"
    claims_tsv = out_dir / "claim_status.tsv"
    manifest_tsv = out_dir / f"artifact_manifest_{args.target}_{args.level}_{label}_allow_missing.tsv"
    readme_md = out_dir / "README.md"
    snapshot_tsv = out_dir / "snapshot_artifacts.tsv"

    next_steps_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii")
    next_steps_txt.write_text(render_next_steps_text(report), encoding="ascii")

    claims = claim_rows(report, args.target)
    write_claims(claims_tsv, claims)

    manifest_rows = build_manifest_rows(repo, args.target, label, baseline_label, args.mode, args.level)
    write_manifest(manifest_tsv, manifest_rows)

    readme_md.write_text(
        readme_text(report, args.target, label, baseline_label, args.mode, args.level, out_dir, claims),
        encoding="ascii",
    )
    snapshot_rows = snapshot_artifact_rows(
        repo,
        report,
        args.target,
        out_dir,
        next_steps_json,
        next_steps_txt,
        claims_tsv,
        manifest_tsv,
        readme_md,
    )
    write_snapshot_artifacts(snapshot_tsv, snapshot_rows)

    missing_snapshot = [
        row["name"]
        for row in snapshot_rows
        if row["required"] == "yes" and row["exists"] != "yes"
    ]
    missing_manifest = [
        row["name"]
        for row in manifest_rows
        if row["required"] == "yes" and row["exists"] != "yes"
    ]

    print("pure_pipeline_prebuild_snapshot")
    print(f"repo={repo}")
    print(f"target={args.target}")
    print(f"label={label}")
    print(f"baseline_label={baseline_label}")
    print(f"mode={args.mode}")
    print(f"level={args.level}")
    print(f"out_dir={display_path(repo, out_dir)}")
    print(f"source_fingerprint_sha256={report.get('source_fingerprint_sha256', '')}")
    print(f"xclbin_exists={'yes' if state.get('xclbin_exists') else 'no'}")
    print(f"snapshot_required_missing_count={len(missing_snapshot)}")
    print(f"manifest_required_missing_count={len(missing_manifest)}")
    print(f"next_command={target_next_command(report, args.target)}")
    print(f"DONE next_steps_json={display_path(repo, next_steps_json)}")
    print(f"DONE next_steps_txt={display_path(repo, next_steps_txt)}")
    print(f"DONE claim_status={display_path(repo, claims_tsv)}")
    print(f"DONE artifact_manifest_allow_missing={display_path(repo, manifest_tsv)}")
    print(f"DONE snapshot_artifacts={display_path(repo, snapshot_tsv)}")
    print(f"DONE readme={display_path(repo, readme_md)}")
    return 0 if not missing_snapshot else 1


if __name__ == "__main__":
    raise SystemExit(main())
