#!/usr/bin/env python3
"""Check that smoke baselines and pure-pipeline runs use identical inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shlex
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = "workloads/sssp_benchmark_smoke/manifest.tsv"
DEFAULT_HOST_SUMMARY = "results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv"
DEFAULT_SPINE_SUMMARY = "results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv"
DEFAULT_PURE_SUMMARY = "results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/summary.tsv"

IDENTITY_COLUMNS = [
    "case",
    "family",
    "ok",
    "manifest_vertices",
    "host_vertices",
    "spine_vertices",
    "pure_vertices",
    "manifest_final_edges",
    "host_final_edges",
    "spine_input_edges",
    "pure_final_edges",
    "manifest_source",
    "host_source",
    "pure_source",
    "manifest_supersteps",
    "host_supersteps",
    "pure_supersteps",
    "manifest_edge_sha256",
    "host_edge_sha256",
    "spine_edge_sha256",
    "graph_sha256",
    "result_sha256",
    "expected_sha256",
    "host_status",
    "spine_status",
    "pure_status",
    "host_mismatch_count",
    "spine_errors",
    "pure_mismatches",
    "host_edge_file",
    "spine_edge_file",
    "notes",
]


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_under_repo(repo: Path, path: Path | str | None) -> Path | None:
    if path is None:
        return None
    p = Path(path)
    return p if p.is_absolute() else repo / p


def display_path(repo: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def by_case(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("case", ""): row for row in rows if row.get("case")}


def read_env(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


def parse_spine_edge_file(row: dict[str, str], repo: Path) -> Path | None:
    args = row.get("args", "")
    try:
        parts = shlex.split(args)
    except ValueError:
        parts = args.split()
    for index, part in enumerate(parts):
        if part == "--edge-file" and index + 1 < len(parts):
            return resolve_under_repo(repo, parts[index + 1])
        if part.startswith("--edge-file="):
            return resolve_under_repo(repo, part.split("=", 1)[1])
    return None


def host_edge_file(row: dict[str, str], repo: Path) -> Path | None:
    case = row.get("case", "")
    result_dir = row.get("result_dir", "")
    if not case or not result_dir:
        return None
    return resolve_under_repo(repo, Path(result_dir) / f"{case}.from_grasu.sssp.edges")


def parse_pure_mismatches(row: dict[str, str]) -> str:
    result = row.get("result_line", "")
    for item in result.split():
        if item.startswith("mismatches="):
            return item.split("=", 1)[1]
    return ""


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(column, "").replace("|", "\\|") for column in columns) + " |")
    return "\n".join(lines)


def write_markdown(path: Path, rows: list[dict[str, str]], args: argparse.Namespace, repo: Path) -> None:
    compact = [
        {
            "case": row["case"],
            "ok": row["ok"],
            "vertices": row["manifest_vertices"],
            "final_edges": row["manifest_final_edges"],
            "source": row["manifest_source"],
            "supersteps": row["manifest_supersteps"],
            "edge_sha256": row["manifest_edge_sha256"],
            "notes": row["notes"],
        }
        for row in rows
    ]
    lines = [
        "# Smoke Input Identity",
        "",
        "This file proves whether the tracked smoke comparison is using the same",
        "manifest rows and edge files across the current host baseline, Spine",
        "edge-file baseline, and an optional pure-pipeline summary.",
        "",
        "## Inputs",
        "",
        f"- Manifest: `{display_path(repo, args.manifest)}`",
        f"- Host summary: `{display_path(repo, args.host_summary)}`",
        f"- Spine summary: `{display_path(repo, args.spine_summary)}`",
        f"- Pure summary: `{display_path(repo, args.pure_summary) if args.pure_summary else ''}`",
        "",
        "## Result",
        "",
        markdown_table(compact, ["case", "ok", "vertices", "final_edges", "source", "supersteps", "edge_sha256", "notes"]),
        "",
        "The strict edge-file identity check compares the workload manifest",
        "`.sssp.edges` file, the host-exported `.from_grasu.sssp.edges` file,",
        "and the Spine `--edge-file` argument.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="ascii")


def identity_row(
    repo: Path,
    manifest_row: dict[str, str],
    host_row: dict[str, str],
    spine_row: dict[str, str],
    pure_row: dict[str, str],
) -> dict[str, str]:
    notes: list[str] = []
    case = manifest_row["case"]
    manifest_edge = resolve_under_repo(repo, manifest_row.get("regraph_sssp_edges", ""))
    graph = resolve_under_repo(repo, manifest_row.get("graph", ""))
    result = resolve_under_repo(repo, manifest_row.get("result", ""))
    expected = resolve_under_repo(repo, manifest_row.get("expected", ""))
    host_edge = host_edge_file(host_row, repo)
    spine_edge = parse_spine_edge_file(spine_row, repo)

    checks: list[tuple[str, bool]] = []
    for label, expected_value, actual_value in [
        ("host_vertices", manifest_row.get("vertices", ""), host_row.get("vertices", "")),
        ("spine_vertices", manifest_row.get("vertices", ""), spine_row.get("vertices", "")),
        ("pure_vertices", manifest_row.get("vertices", ""), pure_row.get("vertices", "")),
        ("host_final_edges", manifest_row.get("final_edges", ""), host_row.get("final_edges", "")),
        ("spine_input_edges", manifest_row.get("final_edges", ""), spine_row.get("input_edges", "")),
        ("pure_final_edges", manifest_row.get("final_edges", ""), pure_row.get("final_edges", "")),
        ("host_source", manifest_row.get("source", ""), host_row.get("source", "")),
        ("pure_source", manifest_row.get("source", ""), pure_row.get("source", "")),
        ("host_supersteps", manifest_row.get("supersteps", ""), host_row.get("supersteps", "")),
        ("pure_supersteps", manifest_row.get("supersteps", ""), pure_row.get("supersteps", "")),
    ]:
        ok = bool(actual_value) and expected_value == actual_value
        checks.append((label, ok))
        if not ok:
            notes.append(f"{label}_mismatch expected={expected_value} actual={actual_value}")

    manifest_edge_hash = sha256(manifest_edge)
    host_edge_hash = sha256(host_edge)
    spine_edge_hash = sha256(spine_edge)
    if not manifest_edge_hash:
        notes.append("manifest_edge_missing")
    if host_edge_hash != manifest_edge_hash:
        notes.append("host_edge_hash_mismatch")
    if spine_edge_hash != manifest_edge_hash:
        notes.append("spine_edge_hash_mismatch")

    host_status = host_row.get("status", "")
    spine_status = spine_row.get("status", "")
    pure_status = pure_row.get("status", "")
    host_mismatch = host_row.get("mismatch_count", "")
    spine_errors = spine_row.get("errors", "")
    pure_mismatches = parse_pure_mismatches(pure_row)
    if host_status != "PASS":
        notes.append("host_not_PASS")
    if spine_status != "PASS":
        notes.append("spine_not_PASS")
    if pure_row and pure_status != "PASS":
        notes.append("pure_not_PASS")
    if host_mismatch not in ("0", "0.0"):
        notes.append("host_mismatch_nonzero")
    if spine_errors not in ("0", "0.0"):
        notes.append("spine_errors_nonzero")
    if pure_row and pure_mismatches != "0":
        notes.append("pure_mismatches_nonzero")

    ok = (
        all(flag for _, flag in checks)
        and manifest_edge_hash
        and host_edge_hash == manifest_edge_hash
        and spine_edge_hash == manifest_edge_hash
        and host_status == "PASS"
        and spine_status == "PASS"
        and host_mismatch in ("0", "0.0")
        and spine_errors in ("0", "0.0")
        and (not pure_row or (pure_status == "PASS" and pure_mismatches == "0"))
    )

    return {
        "case": case,
        "family": manifest_row.get("family", ""),
        "ok": "yes" if ok else "no",
        "manifest_vertices": manifest_row.get("vertices", ""),
        "host_vertices": host_row.get("vertices", ""),
        "spine_vertices": spine_row.get("vertices", ""),
        "pure_vertices": pure_row.get("vertices", ""),
        "manifest_final_edges": manifest_row.get("final_edges", ""),
        "host_final_edges": host_row.get("final_edges", ""),
        "spine_input_edges": spine_row.get("input_edges", ""),
        "pure_final_edges": pure_row.get("final_edges", ""),
        "manifest_source": manifest_row.get("source", ""),
        "host_source": host_row.get("source", ""),
        "pure_source": pure_row.get("source", ""),
        "manifest_supersteps": manifest_row.get("supersteps", ""),
        "host_supersteps": host_row.get("supersteps", ""),
        "pure_supersteps": pure_row.get("supersteps", ""),
        "manifest_edge_sha256": manifest_edge_hash,
        "host_edge_sha256": host_edge_hash,
        "spine_edge_sha256": spine_edge_hash,
        "graph_sha256": sha256(graph),
        "result_sha256": sha256(result),
        "expected_sha256": sha256(expected),
        "host_status": host_status,
        "spine_status": spine_status,
        "pure_status": pure_status,
        "host_mismatch_count": host_mismatch,
        "spine_errors": spine_errors,
        "pure_mismatches": pure_mismatches,
        "host_edge_file": display_path(repo, host_edge),
        "spine_edge_file": display_path(repo, spine_edge),
        "notes": "; ".join(notes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--host-summary", type=Path, default=DEFAULT_HOST_SUMMARY)
    parser.add_argument("--spine-summary", type=Path, default=DEFAULT_SPINE_SUMMARY)
    parser.add_argument("--pure-summary", type=Path, default=DEFAULT_PURE_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    args.manifest = resolve_under_repo(repo, args.manifest)
    args.host_summary = resolve_under_repo(repo, args.host_summary)
    args.spine_summary = resolve_under_repo(repo, args.spine_summary)
    args.pure_summary = resolve_under_repo(repo, args.pure_summary) if args.pure_summary else None

    label = args.label or "current"
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = repo / "results" / f"smoke_input_identity_{label}"
    else:
        out_dir = resolve_under_repo(repo, out_dir)
    assert out_dir is not None

    manifest_rows = read_tsv(args.manifest)
    host = by_case(read_tsv(args.host_summary))
    spine = by_case(read_tsv(args.spine_summary))
    pure = by_case(read_tsv(args.pure_summary))

    rows: list[dict[str, str]] = []
    for manifest_row in manifest_rows:
        case = manifest_row.get("case", "")
        if not case:
            continue
        rows.append(identity_row(repo, manifest_row, host.get(case, {}), spine.get(case, {}), pure.get(case, {})))

    write_tsv(out_dir / "identity.tsv", rows, IDENTITY_COLUMNS)
    write_markdown(out_dir / "identity.md", rows, args, repo)

    failed = [row["case"] for row in rows if row["ok"] != "yes"]
    print(f"identity_tsv={display_path(repo, out_dir / 'identity.tsv')}")
    print(f"identity_md={display_path(repo, out_dir / 'identity.md')}")
    print(f"case_count={len(rows)}")
    print(f"failed_count={len(failed)}")
    if failed:
        print("FAILED cases=" + ",".join(failed))
        return 3
    print("PASS smoke input identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
