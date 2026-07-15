#!/usr/bin/env python3
"""Collect a post-build artifact manifest for a pure-pipeline target.

The manifest binds a target xclbin to the launch packet, postrun evidence,
same-input stage0 evidence, and baseline inputs used by the postbuild
acceptance flow. It is intentionally lightweight: it hashes files that already
exist and does not run Vitis or hardware tests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any


TARGETS = ("sw_emu", "hw_emu", "hw")
MODES = ("gate", "full")
LEVELS = ("build", "gate", "full")
PACKET_LOCAL_HELPERS = (
    "postbuild_acceptance_gate",
    "wait_then_accept_gate",
    "postbuild_acceptance_full",
    "wait_then_accept_full",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def display_path(repo: Path, path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def target_xclbin(repo: Path, target: str) -> Path:
    return repo / ".tmp_build" / f"pure_pipeline_{target}_stage0" / "build" / (
        f"grasu_regraph_pure_pipeline.{target}.xclbin"
    )


def postrun_evidence_label(label: str) -> str:
    if label.startswith("postrun_after_"):
        return label
    if label.startswith("after_"):
        return "postrun_" + label
    return "postrun_after_" + label


def read_kv_file(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if path is None or not path.is_file():
        return values
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if "=" not in line or line.startswith(" "):
            continue
        key, value = line.split("=", 1)
        if key:
            values[key] = value
    return values


def path_from_text(repo: Path, text: str | None) -> Path | None:
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else repo / path


def find_launch_packet(repo: Path, target: str, label: str) -> Path | None:
    candidates: list[Path] = []
    for env_file in repo.glob(".tmp_build/pure_pipeline_launch_packet_*/launch_packet.env"):
        values = read_kv_file(env_file)
        if values.get("target") == target and values.get("flow_label") == label:
            candidates.append(env_file.parent)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def artifact_row(
    repo: Path,
    category: str,
    name: str,
    path: Path | None,
    required: bool,
    detail: str,
) -> dict[str, str]:
    exists = bool(path is not None and path.is_file())
    size = path.stat().st_size if exists and path is not None else ""
    digest = sha256(path) if exists and path is not None else ""
    status = "PASS" if exists or not required else "MISSING"
    return {
        "category": category,
        "name": name,
        "path": display_path(repo, path),
        "exists": "yes" if exists else "no",
        "sha256": digest,
        "size_bytes": str(size),
        "required": "yes" if required else "no",
        "status": status,
        "detail": detail,
    }


def add_artifact(
    rows: list[dict[str, str]],
    repo: Path,
    category: str,
    name: str,
    path: Path | None,
    required: bool,
    detail: str,
) -> None:
    rows.append(artifact_row(repo, category, name, path, required, detail))


def build_manifest_rows(
    repo: Path,
    target: str,
    label: str,
    baseline_label: str,
    mode: str,
    level: str,
    *,
    xclbin: Path | None = None,
    launch_packet_dir: Path | None = None,
) -> list[dict[str, str]]:
    xclbin_path = xclbin or target_xclbin(repo, target)
    if not xclbin_path.is_absolute():
        xclbin_path = repo / xclbin_path
    build_root = repo / ".tmp_build" / f"pure_pipeline_{target}_stage0"
    run_logs = build_root / "run_logs"
    postrun_label = postrun_evidence_label(label)

    if launch_packet_dir is None:
        launch_packet_dir = find_launch_packet(repo, target, label)
    elif not launch_packet_dir.is_absolute():
        launch_packet_dir = repo / launch_packet_dir
    launch_env = launch_packet_dir / "launch_packet.env" if launch_packet_dir is not None else None
    launch_values = read_kv_file(launch_env)

    rows: list[dict[str, str]] = []
    add_artifact(rows, repo, "target", "xclbin", xclbin_path, True, "target pure-pipeline xclbin")
    add_artifact(rows, repo, "target", "xclbin_info", Path(str(xclbin_path) + ".info"), True, "xclbin metadata used by contract checks")
    add_artifact(rows, repo, "target", "xclbin_link_summary", Path(str(xclbin_path) + ".link_summary"), False, "optional Vitis link summary next to xclbin")

    add_artifact(rows, repo, "launch_packet", "launch_packet_env", launch_env, True, "selected launch packet env")
    add_artifact(rows, repo, "launch_packet", "launch_command", path_from_text(repo, launch_values.get("launch_command")), True, "recorded target-flow launch command")
    add_artifact(rows, repo, "launch_packet", "source_contracts", path_from_text(repo, launch_values.get("source_contract_out")), True, "prelaunch source-level contract check")
    add_artifact(rows, repo, "launch_packet", "source_fingerprints", path_from_text(repo, launch_values.get("source_fingerprints_out")), True, "prelaunch source fingerprints")
    add_artifact(rows, repo, "launch_packet", "readiness", path_from_text(repo, launch_values.get("readiness_out")), True, "launch packet readiness report")
    add_artifact(rows, repo, "launch_packet", "acceptance_gates", path_from_text(repo, launch_values.get("acceptance_gates")), True, "launch packet acceptance-gate specification")
    add_artifact(rows, repo, "launch_packet", "acceptance_check_prelaunch", path_from_text(repo, launch_values.get("acceptance_check_prelaunch")), True, "prelaunch acceptance-gate result")
    for helper in PACKET_LOCAL_HELPERS:
        add_artifact(
            rows,
            repo,
            "launch_packet",
            helper,
            path_from_text(repo, launch_values.get(helper)),
            target in ("hw_emu", "hw"),
            f"packet-local {helper.replace('_', '-')} helper",
        )
    add_artifact(rows, repo, "launch_packet", "artifact_hashes", launch_packet_dir / "artifact_hashes.tsv" if launch_packet_dir else None, False, "launch-packet internal artifact hashes")

    add_artifact(rows, repo, "build_scripts", "manifest_env", build_root / "manifest.env", True, "generated target build manifest")
    add_artifact(rows, repo, "build_scripts", "compile_commands", build_root / "compile_commands.sh", True, "generated target compile command")
    add_artifact(rows, repo, "build_scripts", "link_command", build_root / "link_command.sh", True, "generated target link command")
    add_artifact(rows, repo, "build_logs", "compile_log", run_logs / f"compile_{label}.log", False, "compile log when xclbin was built by target flow")
    add_artifact(rows, repo, "build_logs", "link_log", run_logs / f"link_{label}.log", False, "link log when xclbin was built by target flow")

    add_artifact(rows, repo, "postrun", "target_flow_env", run_logs / f"target_flow_{postrun_label}.env", True, "skip-build postrun target-flow env")
    add_artifact(rows, repo, "postrun", "source_contracts", run_logs / f"source_contracts_target_flow_{postrun_label}.tsv", True, "postrun source contract check")
    add_artifact(rows, repo, "postrun", "source_fingerprints", run_logs / f"source_fingerprints_target_flow_{postrun_label}.tsv", True, "postrun source fingerprints")
    add_artifact(rows, repo, "postrun", "readiness", run_logs / f"readiness_target_flow_{postrun_label}.txt", True, "postrun readiness report")
    add_artifact(rows, repo, "postrun", "xclbin_contract", run_logs / f"xclbin_contract_{target}_{postrun_label}.tsv", True, "postrun xclbin metadata contract result")
    add_artifact(rows, repo, "postrun", "finalize_env", run_logs / f"finalize_{postrun_label}.env", True, "postrun finalize env")
    add_artifact(rows, repo, "postrun", "finalize_evidence", run_logs / f"finalize_{postrun_label}_evidence.tsv", True, "postrun finalize artifact evidence")
    add_artifact(rows, repo, "postrun", "acceptance_check_postrun", run_logs / f"acceptance_check_postrun_target_flow_{postrun_label}.tsv", True, "postrun acceptance-gate result")
    add_artifact(rows, repo, "postrun", "smoke_summary", repo / "results" / f"pure_pipeline_{target}_smoke_{postrun_label}" / "summary.tsv", True, "postrun smoke correctness and timing summary")
    add_artifact(rows, repo, "postrun", "same_input_comparison", repo / "results" / f"pure_pipeline_{target}_compare_{postrun_label}" / "comparison.tsv", True, "postrun same-input smoke comparison")
    add_artifact(rows, repo, "postrun", "requirement_audit", repo / "results" / f"pure_pipeline_requirement_audit_{postrun_label}" / "audit.json", True, "postrun requirement audit")
    add_artifact(rows, repo, "postrun", "evidence_bundle_manifest", repo / "results" / f"pure_pipeline_evidence_bundle_{postrun_label}" / "bundle_manifest.json", True, "postrun compact evidence bundle")

    stage0_required = level in ("gate", "full")
    add_artifact(rows, repo, "baseline", "comparison_plan", repo / "results" / f"pure_stage0_comparison_plan_{baseline_label}" / "comparison_plan.tsv", stage0_required, "baseline comparison plan")
    add_artifact(rows, repo, "baseline", "input_identity_plan", repo / "results" / f"pure_stage0_comparison_plan_{baseline_label}" / "input_identity.tsv", stage0_required, "baseline input identity plan")
    add_artifact(rows, repo, "baseline", "host_summary", repo / "results" / f"grasu_regraph_sssp_pure_stage0_{baseline_label}" / "summary.tsv", stage0_required, "host/zero-cost baseline summary")
    add_artifact(rows, repo, "baseline", "host_identity", repo / "results" / f"grasu_regraph_sssp_pure_stage0_identity_{baseline_label}" / "input_identity_check.tsv", stage0_required, "host baseline input identity audit")
    add_artifact(rows, repo, "baseline", "spine_summary", repo / "results" / f"spine_edge_file_pure_stage0_{baseline_label}" / "summary.tsv", stage0_required, "Spine same-input summary")

    add_artifact(rows, repo, "stage0", "postbuild_env", repo / "results" / f"pure_pipeline_{target}_pure_stage0_{mode}_{label}" / "postbuild_matrix.env", stage0_required, "pure stage0 postbuild matrix env")
    add_artifact(rows, repo, "stage0", "summary", repo / "results" / f"pure_pipeline_{target}_pure_stage0_{mode}_{label}" / "summary.tsv", stage0_required, "pure stage0 matrix summary")
    add_artifact(rows, repo, "stage0", "input_identity", repo / "results" / f"pure_pipeline_{target}_pure_stage0_identity_{mode}_{label}" / "input_identity_check.tsv", stage0_required, "pure stage0 input identity audit")
    add_artifact(rows, repo, "stage0", "comparison", repo / "results" / f"pure_pipeline_{target}_pure_stage0_compare_{label}" / "comparison.tsv", stage0_required, "pure stage0 same-input comparison")
    return rows


def missing_required(rows: list[dict[str, str]]) -> list[str]:
    return [row["name"] for row in rows if row["required"] == "yes" and row["exists"] != "yes"]


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ("category", "name", "path", "exists", "sha256", "size_bytes", "required", "status", "detail")
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--target", choices=TARGETS, default="hw_emu")
    parser.add_argument("--label", required=True)
    parser.add_argument("--baseline-label", default="")
    parser.add_argument("--mode", choices=MODES, default="gate")
    parser.add_argument("--level", choices=LEVELS, default="")
    parser.add_argument("--xclbin", type=Path, default=None)
    parser.add_argument("--launch-packet-dir", type=Path, default=None)
    parser.add_argument("--out-file", type=Path, default=None)
    parser.add_argument("--allow-missing-required", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    label = args.label
    baseline_label = args.baseline_label or label
    level = args.level or args.mode
    out_file = args.out_file
    if out_file is None:
        out_file = repo / ".tmp_build" / "pure_pipeline_artifact_manifests" / (
            f"artifact_manifest_{args.target}_{level}_{label}.tsv"
        )
    elif not out_file.is_absolute():
        out_file = repo / out_file

    rows = build_manifest_rows(
        repo,
        args.target,
        label,
        baseline_label,
        args.mode,
        level,
        xclbin=args.xclbin,
        launch_packet_dir=args.launch_packet_dir,
    )
    write_manifest(out_file, rows)
    missing = missing_required(rows)
    xclbin_row = next((row for row in rows if row["name"] == "xclbin"), {})

    print("pure_pipeline_artifact_manifest")
    print(f"repo={repo}")
    print(f"target={args.target}")
    print(f"label={label}")
    print(f"baseline_label={baseline_label}")
    print(f"mode={args.mode}")
    print(f"level={level}")
    print(f"git_head={run_git(repo, ['rev-parse', 'HEAD'])}")
    print(f"out_file={display_path(repo, out_file)}")
    print(f"row_count={len(rows)}")
    print(f"required_missing_count={len(missing)}")
    print(f"xclbin_sha256={xclbin_row.get('sha256', '')}")
    if missing:
        print("missing_required=" + ",".join(missing))
        if not args.allow_missing_required:
            return 1
    print("PASS artifact manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
