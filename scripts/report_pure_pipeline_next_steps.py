#!/usr/bin/env python3
"""Print the current pure-pipeline build status and next target command.

This helper is intentionally read-only: it does not prepare, build, finalize,
or write evidence files. Use it before launching a long Vitis flow to avoid
confusing historical combined artifacts with the current pure-pipeline target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


TARGETS = ("sw_emu", "hw_emu", "hw")
TARGET_TIMEOUTS = {"sw_emu": 180, "hw_emu": 900, "hw": 300}
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


def target_xclbin(repo: Path, target: str) -> Path:
    return repo / ".tmp_build" / f"pure_pipeline_{target}_stage0" / "build" / (
        f"grasu_regraph_pure_pipeline.{target}.xclbin"
    )


def target_state(repo: Path, target: str) -> dict[str, Any]:
    build_root = repo / ".tmp_build" / f"pure_pipeline_{target}_stage0"
    run_logs = build_root / "run_logs"
    xclbin = target_xclbin(repo, target)
    readiness = newest(list(run_logs.glob("readiness*.txt")))
    readiness_values = parse_kv_file(readiness)
    acceptance_prelaunch = newest(list(run_logs.glob("acceptance_check_prelaunch*.tsv")))
    acceptance_postrun = newest(list(run_logs.glob("acceptance_check_postrun*.tsv")))
    return {
        "target": target,
        "build_root": rel(repo, build_root),
        "xclbin": rel(repo, xclbin),
        "xclbin_exists": xclbin.is_file(),
        "xclbin_sha256": sha256(xclbin),
        "xclbin_size_bytes": xclbin.stat().st_size if xclbin.is_file() else None,
        "latest_readiness": rel(repo, readiness) if readiness else None,
        "latest_readiness_ready": readiness_values.get("ready"),
        "latest_readiness_blocking_count": readiness_values.get("blocking_count"),
        "latest_readiness_warning_count": readiness_values.get("warning_count"),
        "latest_acceptance_prelaunch": rel(repo, acceptance_prelaunch) if acceptance_prelaunch else None,
        "latest_acceptance_postrun": rel(repo, acceptance_postrun) if acceptance_postrun else None,
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


def first_missing_target(states: list[dict[str, Any]]) -> str | None:
    by_target = {state["target"]: state for state in states}
    if not by_target["hw_emu"]["xclbin_exists"]:
        return "hw_emu"
    if not by_target["hw"]["xclbin_exists"]:
        return "hw"
    return None


def target_flow_command(target: str, git_short: str) -> str:
    return (
        f"./scripts/run_pure_pipeline_target_flow.sh --target {target} "
        f"--label after_{git_short} --prepare --wait-idle 7200 --idle-poll 60 "
        f"--idle-settle 120 --clean-build-artifacts --gate-case tiny_star_v16_u12 "
        f"--gate-timeout {TARGET_TIMEOUTS[target]}"
    )


def make_report(repo: Path) -> dict[str, Any]:
    git_short = run_git(repo, ["rev-parse", "--short", "HEAD"])
    states = [target_state(repo, target) for target in TARGETS]
    builders = classify_builders(repo, ps_rows())
    next_target = first_missing_target(states)
    next_commands: list[str]
    if next_target is None:
        next_commands = [
            f"./scripts/audit_pure_pipeline_status.py --label after_{git_short}",
            f"./scripts/export_pure_pipeline_evidence_bundle.py --out-dir results/pure_pipeline_evidence_bundle_after_{git_short}",
        ]
    else:
        next_commands = [
            f"./scripts/check_pure_pipeline_build_readiness.sh --target {next_target} --label after_{git_short}",
            target_flow_command(next_target, git_short),
        ]
    return {
        "repo": str(repo),
        "branch": run_git(repo, ["branch", "--show-current"]),
        "head": run_git(repo, ["rev-parse", "HEAD"]),
        "dirty": bool(run_git(repo, ["status", "--porcelain"])),
        "targets": states,
        "active_builders": {
            "related_count": builders["related_count"],
            "external_count": builders["external_count"],
            "related_preview": builders["related"][:5],
            "external_preview": builders["external"][:5],
        },
        "next_target": next_target,
        "next_commands": next_commands,
    }


def print_text(report: dict[str, Any]) -> None:
    print("pure_pipeline_next_steps")
    print(f"repo={report['repo']}")
    print(f"branch={report['branch']}")
    print(f"head={report['head']}")
    print(f"dirty={str(report['dirty']).lower()}")
    print()
    print("targets")
    print("target\txclbin\tsha256\treadiness_ready\tlatest_readiness")
    for state in report["targets"]:
        print(
            "\t".join([
                state["target"],
                "yes" if state["xclbin_exists"] else "no",
                state["xclbin_sha256"] or "",
                state["latest_readiness_ready"] or "",
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
        print("interpretation=hw_emu and hw xclbins are present; refresh audit/bundle next.")
    else:
        print(f"next_target={report['next_target']}")
        if builders["related_count"] or builders["external_count"]:
            print("interpretation=Vitis/Vivado builders are active; use the target-flow wait-idle guard or wait manually.")
        else:
            print("interpretation=no active builders detected; the next target-flow command can start when intended.")
    print()
    print("next_commands")
    for command in report["next_commands"]:
        print(command)


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
