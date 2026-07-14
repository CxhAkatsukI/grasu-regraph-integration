#!/usr/bin/env python3
"""Export a compact reproducibility bundle for the pure-pipeline goal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_COMPARISON = "results/pure_pipeline_smoke_compare_stage1_with_spine/comparison.tsv"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
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


def newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def default_audit(repo: Path) -> Path:
    candidate = newest(list(repo.glob("results/pure_pipeline_requirement_audit_*/audit.json")))
    if candidate is None:
        raise FileNotFoundError("no pure pipeline audit.json found under results/")
    return candidate


def read_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def artifact_by_name(audit: dict[str, Any], name: str) -> dict[str, Any] | None:
    for artifact in audit.get("artifacts", []):
        if artifact.get("name") == name:
            return artifact
    return None


def status_counts(requirements: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for req in requirements:
        status = str(req.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def requirement_rows(audit: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for req in audit.get("requirements", []):
        rows.append({
            "id": str(req.get("id", "")),
            "status": str(req.get("status", "")),
            "requirement": str(req.get("title", "")),
            "gaps": "; ".join(str(gap) for gap in req.get("gaps", [])),
            "evidence": "; ".join(str(item) for item in req.get("evidence", [])),
        })
    return rows


def target_rows(audit: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for target, state in sorted(audit.get("targets", {}).items()):
        smoke = state.get("smoke_summary", {})
        xclbin = state.get("xclbin", {})
        readiness = artifact_by_name(audit, f"latest_{target}_readiness")
        if readiness is None and target == "hw_emu":
            readiness = artifact_by_name(audit, "latest_hw_emu_readiness")
        rows.append({
            "target": target,
            "xclbin_exists": "yes" if xclbin.get("exists") else "no",
            "xclbin_sha256": xclbin.get("sha256") or "",
            "smoke_pass": "yes" if smoke.get("all_expected_pass") else "no",
            "smoke_summary": str(smoke.get("path", "MISSING")),
            "readiness_report": str(readiness.get("path", "MISSING")) if readiness else "MISSING",
            "readiness_sha256": str(readiness.get("sha256", "")) if readiness else "",
        })
    return rows


def artifact_rows(audit: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for item in audit.get("artifacts", []):
        rows.append({
            "name": str(item.get("name", "")),
            "exists": "yes" if item.get("exists") else "no",
            "sha256": item.get("sha256") or "",
            "size_bytes": str(item.get("size_bytes") or ""),
            "path": str(item.get("path", "")),
        })
    return rows


def case_rows(comparison_path: Path | None) -> list[dict[str, str]]:
    rows = read_tsv(comparison_path)
    compact_columns = [
        "case",
        "family",
        "vertices",
        "final_edges",
        "host_status",
        "host_zero_cost_ms",
        "spine_status",
        "spine_kernel_e2e_ms",
        "host_zero_over_spine_kernel",
        "pure_status",
        "pure_target",
        "pure_event_e2e_ms",
        "notes",
    ]
    compact_rows = []
    for row in rows:
        compact_rows.append({column: row.get(column, "") for column in compact_columns})
    return compact_rows


def markdown_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")).replace("|", "\\|") for column in columns) + " |")
    return "\n".join(lines)


def write_summary_md(
    path: Path,
    *,
    repo: Path,
    audit_path: Path,
    comparison_path: Path | None,
    audit: dict[str, Any],
    targets: list[dict[str, str]],
    requirements: list[dict[str, str]],
    cases: list[dict[str, str]],
) -> None:
    counts = status_counts(audit.get("requirements", []))
    git = audit.get("git", {})
    command_block = "\n".join(audit.get("next_commands", []))
    case_columns = [
        "case",
        "family",
        "host_zero_cost_ms",
        "spine_kernel_e2e_ms",
        "pure_target",
        "pure_event_e2e_ms",
        "notes",
    ]
    req_columns = ["id", "status", "requirement", "gaps"]
    target_columns = ["target", "xclbin_exists", "smoke_pass", "readiness_report"]
    lines = [
        "# Pure Pipeline Evidence Bundle",
        "",
        f"- Repository: `{repo}`",
        f"- Branch: `{git.get('branch', run_git(repo, ['branch', '--show-current']))}`",
        f"- Commit: `{git.get('head', run_git(repo, ['rev-parse', 'HEAD']))}`",
        f"- Audit: `{display_path(repo, audit_path)}`",
        f"- Audit SHA-256: `{sha256(audit_path) or ''}`",
        f"- Smoke comparison: `{display_path(repo, comparison_path)}`",
        f"- Smoke comparison SHA-256: `{sha256(comparison_path) if comparison_path is not None else ''}`",
        "",
        "## Status Counts",
        "",
        markdown_table(["status", "count"], [{"status": key, "count": counts[key]} for key in sorted(counts)]),
        "",
        "## Targets",
        "",
        markdown_table(target_columns, targets),
        "",
        "## Requirements",
        "",
        markdown_table(req_columns, requirements),
        "",
        "## Smoke Cases",
        "",
        markdown_table(case_columns, cases),
        "",
        "Pure `sw_emu` timing is correctness/control-flow evidence only; it is not a hardware performance claim.",
        "",
        "## Next Commands",
        "",
        "```bash",
        "cd " + str(repo),
        command_block,
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument("--comparison", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    audit_path = args.audit.resolve() if args.audit is not None else default_audit(repo).resolve()
    comparison_path = args.comparison
    if comparison_path is None:
        default_comparison_path = repo / DEFAULT_COMPARISON
        comparison_path = default_comparison_path if default_comparison_path.is_file() else None
    elif not comparison_path.is_absolute():
        comparison_path = repo / comparison_path
    if comparison_path is not None:
        comparison_path = comparison_path.resolve()

    audit = json.loads(audit_path.read_text(encoding="ascii"))
    requirements = requirement_rows(audit)
    targets = target_rows(audit)
    artifacts = artifact_rows(audit)
    cases = case_rows(comparison_path)

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    write_tsv(out_dir / "requirement_matrix.tsv", requirements, ["id", "status", "requirement", "gaps", "evidence"])
    write_tsv(out_dir / "target_matrix.tsv", targets, [
        "target",
        "xclbin_exists",
        "xclbin_sha256",
        "smoke_pass",
        "smoke_summary",
        "readiness_report",
        "readiness_sha256",
    ])
    write_tsv(out_dir / "artifact_matrix.tsv", artifacts, ["name", "exists", "sha256", "size_bytes", "path"])
    write_tsv(out_dir / "case_matrix.tsv", cases, [
        "case",
        "family",
        "vertices",
        "final_edges",
        "host_status",
        "host_zero_cost_ms",
        "spine_status",
        "spine_kernel_e2e_ms",
        "host_zero_over_spine_kernel",
        "pure_status",
        "pure_target",
        "pure_event_e2e_ms",
        "notes",
    ])
    write_summary_md(
        out_dir / "summary.md",
        repo=repo,
        audit_path=audit_path,
        comparison_path=comparison_path,
        audit=audit,
        targets=targets,
        requirements=requirements,
        cases=cases,
    )
    bundle_manifest = {
        "repo": str(repo),
        "audit": display_path(repo, audit_path),
        "audit_sha256": sha256(audit_path),
        "comparison": display_path(repo, comparison_path),
        "comparison_sha256": sha256(comparison_path) if comparison_path is not None else None,
        "outputs": {
            name: {
                "path": display_path(repo, out_dir / name),
                "sha256": sha256(out_dir / name),
            }
            for name in (
                "requirement_matrix.tsv",
                "target_matrix.tsv",
                "artifact_matrix.tsv",
                "case_matrix.tsv",
                "summary.md",
            )
        },
    }
    (out_dir / "bundle_manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )

    print(f"summary_md={display_path(repo, out_dir / 'summary.md')}")
    print(f"bundle_manifest={display_path(repo, out_dir / 'bundle_manifest.json')}")
    print("status_counts=" + json.dumps(status_counts(audit.get("requirements", [])), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
