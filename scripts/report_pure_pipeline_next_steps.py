#!/usr/bin/env python3
"""Print the current pure-pipeline build status and next target command.

This helper is intentionally read-only: it does not prepare, build, finalize,
or write evidence files. Use it before launching a long Vitis flow to avoid
confusing historical combined artifacts with the current pure-pipeline target.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


TARGETS = ("sw_emu", "hw_emu", "hw")
TARGET_TIMEOUTS = {"sw_emu": 180, "hw_emu": 900, "hw": 300}
SOURCE_ROLES = (
    ("integration_scripts", ("scripts",), (".sh", ".py")),
    ("integration_kernels", ("kernels",), (".cpp", ".h", ".hpp")),
    ("integration_tools", ("tools",), (".cpp", ".h", ".hpp")),
    ("grasu_kernel_src", ("repos", "GraSU", "GraSU", "GraSU_kernels", "src"), (".cpp", ".h", ".hpp")),
    ("grasu_host_src", ("repos", "GraSU", "GraSU", "GraSU", "src"), (".cpp", ".h", ".hpp")),
    ("grasu_u55c_scripts", ("repos", "GraSU", "u55c_hbm"), (".sh", ".cfg", ".ini")),
    ("regraph_acc_template", ("repos", "ReGraph", "acc_template"), (".cpp", ".h", ".hpp", ".cfg", ".mk")),
    ("regraph_acc_udfs", ("repos", "ReGraph", "acc_udfs"), (".cpp", ".h", ".hpp")),
    ("regraph_host_src", ("repos", "ReGraph", "host"), (".cpp", ".h", ".hpp", ".mk")),
)
BUILDER_COMMANDS = {
    "v++",
    "vpl",
    "vivado",
    "vrs",
    "xocc",
    "xelab",
    "xsim",
    "xsimk",
    "xsc",
    "xvlog",
    "xvhdl",
}


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def parse_kv_file(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if path is None or not path.is_file():
        return values
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if "=" not in line or line.startswith(" "):
            continue
        key, value = line.split("=", 1)
        if key and "\t" not in key:
            values[key] = value
    return values


def read_source_fingerprints(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if not line or line.startswith("role\t"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows[parts[0]] = parts[2]
    return rows


def read_tsv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def hash_source_role(root: Path, suffixes: tuple[str, ...]) -> tuple[str, str]:
    if not root.is_dir():
        return "missing", "-"
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name.endswith(suffixes)
    )
    if not files:
        return "empty", "-"
    lines = []
    for path in files:
        digest = sha256(path)
        lines.append(f"{digest}  {path}\n")
    return "present", sha256_bytes("".join(lines).encode("utf-8"))


def current_source_fingerprints(repo: Path) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for role, root_parts, suffixes in SOURCE_ROLES:
        _status, digest = hash_source_role(repo.joinpath(*root_parts), suffixes)
        fingerprints[role] = digest
    return fingerprints


def fingerprints_match(recorded: dict[str, str], current: dict[str, str]) -> bool | None:
    if not recorded:
        return None
    for role, digest in current.items():
        if recorded.get(role) != digest:
            return False
    return True


def source_fingerprint_digest(fingerprints: dict[str, str]) -> str:
    lines = [f"{role}\t{fingerprints[role]}\n" for role in sorted(fingerprints)]
    return sha256_bytes("".join(lines).encode("utf-8"))


def target_xclbin(repo: Path, target: str) -> Path:
    return repo / ".tmp_build" / f"pure_pipeline_{target}_stage0" / "build" / (
        f"grasu_regraph_pure_pipeline.{target}.xclbin"
    )


def newest_readiness(run_logs: Path, allow_active: bool | None = None) -> Path | None:
    candidates = list(run_logs.glob("readiness*.txt"))
    if allow_active is not None:
        marker = f"allow_active_builders={1 if allow_active else 0}"
        candidates = [
            path
            for path in candidates
            if marker in path.read_text(encoding="ascii", errors="replace")
        ]
    return newest(candidates)


def launch_packets(
    repo: Path,
    target: str,
    current_fingerprints: dict[str, str],
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for env_file in repo.glob(".tmp_build/pure_pipeline_launch_packet_*/launch_packet.env"):
        values = parse_kv_file(env_file)
        if values.get("target") != target:
            continue
        source_fingerprints_path_text = values.get("source_fingerprints_out")
        source_fingerprints_path = Path(source_fingerprints_path_text) if source_fingerprints_path_text else None
        source_fingerprints = read_source_fingerprints(source_fingerprints_path)
        source_fingerprints_match = fingerprints_match(source_fingerprints, current_fingerprints)
        launch_command_text = values.get("launch_command")
        launch_command = Path(launch_command_text) if launch_command_text else None
        packets.append({
            "packet_dir": env_file.parent,
            "launch_packet_env": env_file,
            "flow_label": values.get("flow_label"),
            "integration_head": values.get("integration_head"),
            "integration_tracked_dirty": values.get("integration_tracked_dirty"),
            "source_fingerprints": source_fingerprints_path,
            "source_fingerprints_match_current": source_fingerprints_match,
            "launch_command": launch_command,
            "launch_command_exists": bool(launch_command and launch_command.is_file()),
            "mtime": env_file.stat().st_mtime,
        })
    return sorted(packets, key=lambda item: item["mtime"], reverse=True)


def newest_current_launch_packet(
    repo: Path,
    target: str,
    current_fingerprints: dict[str, str],
) -> dict[str, Any] | None:
    for packet in launch_packets(repo, target, current_fingerprints):
        if packet["source_fingerprints_match_current"] is True and packet["launch_command_exists"]:
            return packet
    return None


def summarize_acceptance(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "status": "missing",
            "counts": {},
            "detail": "missing",
        }
    rows = read_tsv_rows(path)
    if not rows:
        return {
            "status": "fail",
            "counts": {},
            "detail": "empty",
        }
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    required = [row for row in rows if row.get("required") == "yes"]
    failures = [row.get("gate", "unknown") for row in required if row.get("status") == "FAIL"]
    pending = [row.get("gate", "unknown") for row in required if row.get("status") == "PENDING"]
    missing_status = [
        row.get("gate", "unknown")
        for row in required
        if row.get("status") not in {"PASS", "FAIL", "PENDING", "SKIP"}
    ]
    if failures:
        return {
            "status": "fail",
            "counts": counts,
            "detail": "FAIL=" + ",".join(failures),
        }
    if pending:
        return {
            "status": "pending",
            "counts": counts,
            "detail": "PENDING=" + ",".join(pending),
        }
    if missing_status:
        return {
            "status": "fail",
            "counts": counts,
            "detail": "UNKNOWN=" + ",".join(missing_status),
        }
    if required and all(row.get("status") == "PASS" for row in required):
        return {
            "status": "pass",
            "counts": counts,
            "detail": "required gates PASS",
        }
    return {
        "status": "fail",
        "counts": counts,
        "detail": "no required PASS gates",
    }


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    ordered = [key for key in ("PASS", "PENDING", "FAIL", "SKIP") if key in counts]
    ordered.extend(sorted(key for key in counts if key not in ordered))
    return ",".join(f"{key}={counts[key]}" for key in ordered)


def postrun_label(summary: dict[str, Any]) -> str:
    counts = format_counts(summary.get("counts", {}))
    if counts:
        return f"{summary['status']}:{counts}"
    return summary["status"]


def target_state(
    repo: Path,
    target: str,
    current_head: str,
    current_fingerprints: dict[str, str],
) -> dict[str, Any]:
    build_root = repo / ".tmp_build" / f"pure_pipeline_{target}_stage0"
    run_logs = build_root / "run_logs"
    xclbin = target_xclbin(repo, target)
    readiness = newest_readiness(run_logs)
    strict_readiness = newest_readiness(run_logs, allow_active=False)
    allow_active_readiness = newest_readiness(run_logs, allow_active=True)
    readiness_values = parse_kv_file(readiness)
    strict_readiness_values = parse_kv_file(strict_readiness)
    allow_active_readiness_values = parse_kv_file(allow_active_readiness)
    target_flow_env = newest(list(run_logs.glob("target_flow_*.env")))
    target_flow_values = parse_kv_file(target_flow_env)
    target_flow_head = target_flow_values.get("git_head")
    target_flow_matches_head = None
    if target_flow_head:
        target_flow_matches_head = target_flow_head == current_head
    source_fingerprints_path_text = target_flow_values.get("source_fingerprints_out")
    source_fingerprints_path = Path(source_fingerprints_path_text) if source_fingerprints_path_text else None
    source_fingerprints = read_source_fingerprints(source_fingerprints_path)
    source_fingerprints_match = fingerprints_match(source_fingerprints, current_fingerprints)
    flow_matches_current = source_fingerprints_match
    if flow_matches_current is None:
        flow_matches_current = target_flow_matches_head
    acceptance_prelaunch = newest(list(run_logs.glob("acceptance_check_prelaunch*.tsv")))
    acceptance_postrun = newest(list(run_logs.glob("acceptance_check_postrun*.tsv")))
    acceptance_prelaunch_summary = summarize_acceptance(acceptance_prelaunch)
    acceptance_postrun_summary = summarize_acceptance(acceptance_postrun)
    launch_packet = newest_current_launch_packet(repo, target, current_fingerprints)
    return {
        "target": target,
        "build_root": rel(repo, build_root),
        "xclbin": rel(repo, xclbin),
        "xclbin_exists": xclbin.is_file(),
        "xclbin_sha256": sha256(xclbin),
        "xclbin_size_bytes": xclbin.stat().st_size if xclbin.is_file() else None,
        "latest_readiness": rel(repo, readiness) if readiness else None,
        "latest_readiness_allow_active_builders": readiness_values.get("allow_active_builders"),
        "latest_readiness_ready": readiness_values.get("ready"),
        "latest_readiness_blocking_count": readiness_values.get("blocking_count"),
        "latest_readiness_warning_count": readiness_values.get("warning_count"),
        "latest_strict_readiness": rel(repo, strict_readiness) if strict_readiness else None,
        "latest_strict_readiness_ready": strict_readiness_values.get("ready"),
        "latest_strict_readiness_blocking_count": strict_readiness_values.get("blocking_count"),
        "latest_allow_active_readiness": rel(repo, allow_active_readiness) if allow_active_readiness else None,
        "latest_allow_active_readiness_ready": allow_active_readiness_values.get("ready"),
        "latest_allow_active_readiness_blocking_count": allow_active_readiness_values.get("blocking_count"),
        "latest_target_flow_env": rel(repo, target_flow_env) if target_flow_env else None,
        "latest_target_flow_git_head": target_flow_head,
        "latest_target_flow_matches_head": target_flow_matches_head,
        "latest_source_fingerprints": rel(repo, source_fingerprints_path) if source_fingerprints_path else None,
        "latest_source_fingerprints_match_current": source_fingerprints_match,
        "latest_flow_matches_current": flow_matches_current,
        "current_launch_packet": rel(repo, launch_packet["packet_dir"]) if launch_packet else None,
        "current_launch_packet_flow_label": launch_packet["flow_label"] if launch_packet else None,
        "current_launch_packet_integration_head": launch_packet["integration_head"] if launch_packet else None,
        "current_launch_packet_integration_tracked_dirty": launch_packet["integration_tracked_dirty"] if launch_packet else None,
        "current_launch_packet_command": rel(repo, launch_packet["launch_command"]) if launch_packet else None,
        "latest_acceptance_prelaunch": rel(repo, acceptance_prelaunch) if acceptance_prelaunch else None,
        "latest_acceptance_postrun": rel(repo, acceptance_postrun) if acceptance_postrun else None,
        "latest_acceptance_prelaunch_status": acceptance_prelaunch_summary["status"],
        "latest_acceptance_prelaunch_counts": acceptance_prelaunch_summary["counts"],
        "latest_acceptance_prelaunch_detail": acceptance_prelaunch_summary["detail"],
        "latest_acceptance_postrun_status": acceptance_postrun_summary["status"],
        "latest_acceptance_postrun_counts": acceptance_postrun_summary["counts"],
        "latest_acceptance_postrun_detail": acceptance_postrun_summary["detail"],
        "latest_acceptance_postrun_label": (
            postrun_label(acceptance_postrun_summary)
            if xclbin.is_file()
            else "waiting_xclbin"
        ),
    }


def ps_rows() -> list[dict[str, str]]:
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,etimes=,stat=,pcpu=,pmem=,comm=,args="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid, ppid, etimes, stat, pcpu, pmem, comm, args = parts
        if comm not in BUILDER_COMMANDS and "run_pure_pipeline" not in args:
            continue
        rows.append({
            "pid": pid,
            "ppid": ppid,
            "etimes": etimes,
            "stat": stat,
            "pcpu": pcpu,
            "pmem": pmem,
            "comm": comm,
            "args": args,
        })
    return rows


def classify_builders(repo: Path, rows: list[dict[str, str]]) -> dict[str, Any]:
    repo_text = str(repo)
    target_roots = [str(repo / ".tmp_build" / f"pure_pipeline_{target}_stage0") for target in TARGETS]
    related = []
    external = []
    for row in rows:
        args = row["args"]
        if repo_text in args or any(root in args for root in target_roots) or "run_pure_pipeline" in args:
            related.append(row)
        else:
            external.append(row)
    return {
        "related_count": len(related),
        "external_count": len(external),
        "related": related,
        "external": external,
    }


def first_incomplete_action(states: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    by_target = {state["target"]: state for state in states}
    if not by_target["hw_emu"]["xclbin_exists"]:
        return "hw_emu", "build"
    if by_target["hw_emu"]["latest_acceptance_postrun_status"] != "pass":
        return "hw_emu", "postrun"
    if not by_target["hw"]["xclbin_exists"]:
        return "hw", "build"
    if by_target["hw"]["latest_acceptance_postrun_status"] != "pass":
        return "hw", "postrun"
    return None, None


def target_flow_command(target: str, git_short: str) -> str:
    return (
        f"./scripts/run_pure_pipeline_target_flow.sh --target {target} "
        f"--label after_{git_short} --prepare --wait-idle 7200 --idle-poll 60 "
        f"--idle-settle 120 --clean-build-artifacts --gate-case tiny_star_v16_u12 "
        f"--gate-timeout {TARGET_TIMEOUTS[target]}"
    )


def postrun_command(target: str, git_short: str) -> str:
    return (
        f"./scripts/run_pure_pipeline_target_flow.sh --target {target} "
        f"--label postrun_after_{git_short} --skip-build "
        f"--gate-case tiny_star_v16_u12 --gate-timeout {TARGET_TIMEOUTS[target]}"
    )


def stage0_baseline_state(repo: Path, label: str) -> dict[str, Any]:
    plan_dir = repo / "results" / f"pure_stage0_comparison_plan_{label}"
    host_summary = repo / "results" / f"grasu_regraph_sssp_pure_stage0_{label}" / "summary.tsv"
    spine_summary = repo / "results" / f"spine_edge_file_pure_stage0_{label}" / "summary.tsv"
    return {
        "label": label,
        "plan_dir": rel(repo, plan_dir),
        "plan_tsv": rel(repo, plan_dir / "comparison_plan.tsv"),
        "plan_exists": (plan_dir / "comparison_plan.tsv").is_file(),
        "host_summary": rel(repo, host_summary),
        "host_summary_exists": host_summary.is_file(),
        "spine_summary": rel(repo, spine_summary),
        "spine_summary_exists": spine_summary.is_file(),
        "plan_command": (
            f"./scripts/export_pure_stage0_comparison_plan.py --label {label} "
            f"--out-dir results/pure_stage0_comparison_plan_{label}"
        ),
    }


def postbuild_matrix_command(target: str, mode: str, label: str, baseline_label: str) -> str:
    return (
        f"./scripts/run_pure_stage0_postbuild_matrix.sh --target {target} "
        f"--mode {mode} --label {label} --baseline-label {baseline_label} "
        "--require-compare"
    )


def stage0_followup_commands(label: str, baseline_label: str) -> list[dict[str, str]]:
    return [
        {
            "name": "hw_emu_gate",
            "when": "after hw_emu xclbin exists and postrun acceptance is PASS",
            "command": postbuild_matrix_command("hw_emu", "gate", label, baseline_label),
        },
        {
            "name": "hw_gate",
            "when": "after hw xclbin exists and postrun acceptance is PASS",
            "command": postbuild_matrix_command("hw", "gate", label, baseline_label),
        },
        {
            "name": "hw_full",
            "when": "after hw gate passes; proves tracked V<=65536 stage0 matrix",
            "command": postbuild_matrix_command("hw", "full", label, baseline_label),
        },
    ]


def stage0_label_from_packets(
    states: list[dict[str, Any]],
    git_short: str,
) -> tuple[str, str]:
    by_target = {state["target"]: state for state in states}
    for target in ("hw_emu", "hw", "sw_emu"):
        label = by_target.get(target, {}).get("current_launch_packet_flow_label")
        if label:
            return label, f"{target}_launch_packet"
    return f"after_{git_short}", "git_head"


def make_report(repo: Path) -> dict[str, Any]:
    git_short = run_git(repo, ["rev-parse", "--short", "HEAD"])
    current_head = run_git(repo, ["rev-parse", "HEAD"])
    current_fingerprints = current_source_fingerprints(repo)
    current_fingerprint_digest = source_fingerprint_digest(current_fingerprints)
    states = [target_state(repo, target, current_head, current_fingerprints) for target in TARGETS]
    builders = classify_builders(repo, ps_rows())
    next_target, next_action = first_incomplete_action(states)
    stale_targets = [
        state["target"]
        for state in states
        if state["latest_flow_matches_current"] is False
    ]
    next_commands: list[str]
    next_launch_packet_command = None
    if next_target is not None:
        next_state = next(state for state in states if state["target"] == next_target)
        next_launch_packet_command = next_state.get("current_launch_packet_command")
    if next_target is None:
        next_commands = [
            f"./scripts/audit_pure_pipeline_status.py --label after_{git_short}",
            f"./scripts/export_pure_pipeline_evidence_bundle.py --out-dir results/pure_pipeline_evidence_bundle_after_{git_short}",
        ]
    elif next_action == "postrun":
        next_commands = [postrun_command(next_target, git_short)]
    elif next_launch_packet_command:
        next_commands = [next_launch_packet_command]
    else:
        next_commands = [
            f"./scripts/check_pure_pipeline_build_readiness.sh --target {next_target} --label after_{git_short}",
            target_flow_command(next_target, git_short),
        ]
    stage0_label, stage0_label_source = stage0_label_from_packets(states, git_short)
    stage0_baseline = stage0_baseline_state(repo, stage0_label)
    return {
        "repo": str(repo),
        "branch": run_git(repo, ["branch", "--show-current"]),
        "head": current_head,
        "source_fingerprint_sha256": current_fingerprint_digest,
        "dirty": bool(run_git(repo, ["status", "--porcelain"])),
        "targets": states,
        "active_builders": {
            "related_count": builders["related_count"],
            "external_count": builders["external_count"],
            "related_preview": builders["related"][:5],
            "external_preview": builders["external"][:5],
        },
        "next_target": next_target,
        "next_action": next_action,
        "next_launch_packet_command": next_launch_packet_command,
        "stale_target_flow_targets": stale_targets,
        "next_commands": next_commands,
        "stage0_followup": {
            "label_source": stage0_label_source,
            "baseline": stage0_baseline,
            "commands": stage0_followup_commands(stage0_label, stage0_label),
        },
    }


def print_text(report: dict[str, Any]) -> None:
    print("pure_pipeline_next_steps")
    print(f"repo={report['repo']}")
    print(f"branch={report['branch']}")
    print(f"head={report['head']}")
    print(f"source_fingerprint_sha256={report['source_fingerprint_sha256']}")
    print(f"dirty={str(report['dirty']).lower()}")
    print()
    print("targets")
    print("target\txclbin\tsha256\treadiness_ready\tstrict_ready\tstrict_blockers\tflow_current\tpacket_current\tpostrun\tlatest_readiness")
    for state in report["targets"]:
        if state["latest_flow_matches_current"] is None:
            flow_current = ""
        else:
            flow_current = "yes" if state["latest_flow_matches_current"] else "no"
        packet_current = "yes" if state["current_launch_packet"] else "no"
        print(
            "\t".join([
                state["target"],
                "yes" if state["xclbin_exists"] else "no",
                state["xclbin_sha256"] or "",
                state["latest_readiness_ready"] or "",
                state["latest_strict_readiness_ready"] or "",
                state["latest_strict_readiness_blocking_count"] or "",
                flow_current,
                packet_current,
                state["latest_acceptance_postrun_label"],
                state["latest_readiness"] or "",
            ])
        )
    print()
    builders = report["active_builders"]
    print(
        "active_builders="
        f"related:{builders['related_count']} external:{builders['external_count']}"
    )
    for kind in ("related_preview", "external_preview"):
        for row in builders[kind]:
            print(
                f"{kind}\tpid={row['pid']}\tetimes={row['etimes']}\t"
                f"comm={row['comm']}\targs={row['args'][:180]}"
            )
    print()
    if report["next_target"] is None:
        print("next_target=none")
        print("next_action=none")
        print("interpretation=hw_emu and hw xclbins are present and postrun acceptance gates passed; refresh audit/bundle next.")
    else:
        print(f"next_target={report['next_target']}")
        print(f"next_action={report['next_action']}")
        if report["next_action"] == "postrun":
            print("interpretation=target xclbin exists but postrun acceptance is not PASS; next command reuses the xclbin and runs smoke/compare/audit/bundle.")
        if report.get("next_launch_packet_command") and report["next_action"] == "build":
            print("interpretation=current launch packet matches build-relevant source; next command uses that packet.")
        if report["stale_target_flow_targets"]:
            stale = ",".join(report["stale_target_flow_targets"])
            print(f"stale_target_flow_targets={stale}")
            print("interpretation=latest target-flow evidence is from an older commit; the next target-flow command will refresh it.")
        if builders["related_count"] or builders["external_count"]:
            print("interpretation=Vitis/Vivado builders are active; use the target-flow wait-idle guard or wait manually.")
        if not report["stale_target_flow_targets"] and not (
            builders["related_count"] or builders["external_count"]
        ):
            print("interpretation=no active builders detected; the next target-flow command can start when intended.")
    print()
    print("next_commands")
    for command in report["next_commands"]:
        print(command)
    print()
    print("stage0_followup")
    baseline = report["stage0_followup"]["baseline"]
    print(
        "baseline\t"
        f"label={baseline['label']}\t"
        f"label_source={report['stage0_followup']['label_source']}\t"
        f"plan={'yes' if baseline['plan_exists'] else 'no'}\t"
        f"host_summary={'yes' if baseline['host_summary_exists'] else 'no'}\t"
        f"spine_summary={'yes' if baseline['spine_summary_exists'] else 'no'}"
    )
    print(f"baseline_plan\t{baseline['plan_command']}")
    print(f"host_summary\t{baseline['host_summary']}")
    print(f"spine_summary\t{baseline['spine_summary']}")
    for item in report["stage0_followup"]["commands"]:
        print(f"{item['name']}\twhen={item['when']}\tcommand={item['command']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = make_report(args.repo_root.resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
