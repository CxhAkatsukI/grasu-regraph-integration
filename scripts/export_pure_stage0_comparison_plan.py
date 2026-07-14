#!/usr/bin/env python3
"""Export a same-input comparison plan for the tracked pure_stage0 workloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "workloads" / "sssp_benchmark_pure_stage0" / "manifest.tsv"
STAGE0_VERTEX_LIMIT = 65_536
GATE_CASES = ("tiny_chain_v16", "tiny_star_v16_u12", "tiny_spread_v16_u8", "tiny_hotdst_v64_u32")
BOUNDARY_CASES = (
    "medium_star_v65536_u8192",
    "medium_spread_v65536_u16384",
    "boundary_hotdst_v65536_u4096",
)


@dataclass(frozen=True)
class InputRow:
    case: str
    family: str
    vertices: str
    static_edges: str
    update_edges: str
    final_edges: str
    source: str
    supersteps: str
    default_weight: str
    graph: str
    result: str
    regraph_sssp_edges: str
    expected: str
    metadata: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def read_manifest(path: Path) -> list[InputRow]:
    with path.open("r", encoding="ascii", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append(
                InputRow(
                    case=row["case"],
                    family=row["family"],
                    vertices=row["vertices"],
                    static_edges=row["static_edges"],
                    update_edges=row["update_edges"],
                    final_edges=row["final_edges"],
                    source=row["source"],
                    supersteps=row["supersteps"],
                    default_weight=row["default_weight"],
                    graph=row["graph"],
                    result=row["result"],
                    regraph_sssp_edges=row["regraph_sssp_edges"],
                    expected=row["expected"],
                    metadata=row["metadata"],
                )
            )
    return rows


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def tier(row: InputRow) -> str:
    if row.case in GATE_CASES:
        return "gate"
    if int(row.vertices) == STAGE0_VERTEX_LIMIT:
        return "boundary"
    return "review"


def validate_rows(rows: list[InputRow]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.case in seen:
            problems.append(f"{row.case}: duplicate case")
        seen.add(row.case)
        if int(row.vertices) > STAGE0_VERTEX_LIMIT:
            problems.append(f"{row.case}: vertices>{STAGE0_VERTEX_LIMIT}")
        if row.default_weight != "1":
            problems.append(f"{row.case}: default_weight={row.default_weight}")
        for field in ("graph", "result", "regraph_sssp_edges", "expected", "metadata"):
            path = Path(getattr(row, field))
            if not path.is_file():
                problems.append(f"{row.case}: missing {field}={path}")
    missing_gate = sorted(set(GATE_CASES) - {row.case for row in rows})
    if missing_gate:
        problems.append("missing gate cases=" + ",".join(missing_gate))
    return problems


def write_input_identity(path: Path, rows: list[InputRow]) -> None:
    fields = [
        "case",
        "family",
        "tier",
        "vertices",
        "static_edges",
        "update_edges",
        "final_edges",
        "source",
        "supersteps",
        "default_weight",
        "graph",
        "graph_sha256",
        "result",
        "result_sha256",
        "regraph_sssp_edges",
        "regraph_sssp_edges_sha256",
        "expected",
        "expected_sha256",
        "metadata",
        "metadata_sha256",
    ]
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            graph = Path(row.graph)
            result = Path(row.result)
            regraph = Path(row.regraph_sssp_edges)
            expected = Path(row.expected)
            metadata = Path(row.metadata)
            writer.writerow(
                {
                    "case": row.case,
                    "family": row.family,
                    "tier": tier(row),
                    "vertices": row.vertices,
                    "static_edges": row.static_edges,
                    "update_edges": row.update_edges,
                    "final_edges": row.final_edges,
                    "source": row.source,
                    "supersteps": row.supersteps,
                    "default_weight": row.default_weight,
                    "graph": rel(graph),
                    "graph_sha256": sha256_file(graph),
                    "result": rel(result),
                    "result_sha256": sha256_file(result),
                    "regraph_sssp_edges": rel(regraph),
                    "regraph_sssp_edges_sha256": sha256_file(regraph),
                    "expected": rel(expected),
                    "expected_sha256": sha256_file(expected),
                    "metadata": rel(metadata),
                    "metadata_sha256": sha256_file(metadata),
                }
            )


def shell_cases(cases: tuple[str, ...]) -> str:
    return " ".join(f"--case {case}" for case in cases)


def plan_rows(label: str, manifest: Path) -> list[dict[str, str]]:
    manifest_rel = rel(manifest)
    workload_root = rel(manifest.parent)
    host_out = f"results/grasu_regraph_sssp_pure_stage0_{label}"
    host_identity = f"results/grasu_regraph_sssp_pure_stage0_identity_{label}"
    spine_out = f"results/spine_edge_file_pure_stage0_{label}"
    pure_gate_out = f"results/pure_pipeline_<target>_pure_stage0_gate_{label}"
    pure_full_out = f"results/pure_pipeline_hw_pure_stage0_full_{label}"
    compare_out = f"results/pure_pipeline_hw_pure_stage0_compare_{label}"
    gate_cases = shell_cases(GATE_CASES)
    return [
        {
            "step": "1",
            "system": "host-baseline",
            "target": "hw",
            "requires_xclbin": "GraSU hw + ReGraph/combined hw",
            "command": (
                "./scripts/run_grasu_regraph_sssp_sweep.sh --preset pure_stage0 "
                f"--workload-root {workload_root} --out-root {host_out} "
                "--skip-generate --device-graph-export"
            ),
            "produces": f"{host_out}/summary.tsv and per-case *.from_grasu.sssp.edges",
            "same_input_contract": "Consumes tracked graph/result/source/supersteps from the manifest.",
        },
        {
            "step": "2",
            "system": "host-input-audit",
            "target": "derived",
            "requires_xclbin": "none",
            "command": (
                "python3 scripts/check_pure_stage0_input_identity.py "
                f"--input-identity results/pure_stage0_comparison_plan_{label}/input_identity.tsv "
                f"--run-root {host_out} "
                f"--summary {host_out}/summary.tsv "
                f"--out-file {host_identity}/input_identity_check.tsv"
            ),
            "produces": f"{host_identity}/input_identity_check.tsv",
            "same_input_contract": "Verifies per-case case.env hashes against input_identity.tsv.",
        },
        {
            "step": "3",
            "system": "zero-cost-handoff",
            "target": "derived",
            "requires_xclbin": "none",
            "command": "Computed as host_grasu_ms + host_regraph_e2e_ms from step 1.",
            "produces": "host_zero_cost_ms in comparison.tsv",
            "same_input_contract": "No extra run; uses step 1 timing on the same manifest rows.",
        },
        {
            "step": "4",
            "system": "spine",
            "target": "hw",
            "requires_xclbin": "Spine edge-file hw xclbin",
            "command": (
                f"./scripts/run_spine_edge_file_sweep.sh --chain-root {host_out} "
                f"--out-root {spine_out}"
            ),
            "produces": f"{spine_out}/summary.tsv",
            "same_input_contract": "Consumes final SSSP edge files exported from the host-baseline cases.",
        },
        {
            "step": "5",
            "system": "pure-pipeline-gate",
            "target": "sw_emu|hw_emu|hw",
            "requires_xclbin": "grasu_regraph_pure_pipeline.<target>.xclbin",
            "command": (
                "./scripts/run_pure_pipeline_smoke.sh --target <target> "
                f"--manifest {manifest_rel} {gate_cases} --out-dir {pure_gate_out}"
            ),
            "produces": f"{pure_gate_out}/summary.tsv",
            "same_input_contract": "Runs the four required correctness families from the tracked manifest.",
        },
        {
            "step": "6",
            "system": "pure-pipeline-full",
            "target": "hw",
            "requires_xclbin": "grasu_regraph_pure_pipeline.hw.xclbin",
            "command": (
                "./scripts/run_pure_pipeline_smoke.sh --target hw "
                f"--manifest {manifest_rel} --out-dir {pure_full_out}"
            ),
            "produces": f"{pure_full_out}/summary.tsv",
            "same_input_contract": "Runs all 12 tracked pure_stage0 cases after gate passes.",
        },
        {
            "step": "7",
            "system": "comparison",
            "target": "derived",
            "requires_xclbin": "none",
            "command": (
                "python3 scripts/summarize_pure_pipeline_smoke.py "
                f"--host-summary {host_out}/summary.tsv "
                f"--spine-summary {spine_out}/summary.tsv "
                f"--pure-summary {pure_full_out}/summary.tsv "
                f"--pure-env {pure_full_out}/run.env "
                f"--out-dir {compare_out}"
            ),
            "produces": f"{compare_out}/comparison.tsv",
            "same_input_contract": "Joins summaries by case name; input_identity.tsv proves case file hashes.",
        },
    ]


def write_plan_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ("step", "system", "target", "requires_xclbin", "command", "produces", "same_input_contract")
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[InputRow], plan: list[dict[str, str]], manifest: Path, out_dir: Path) -> None:
    family_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    for row in rows:
        family_counts[row.family] = family_counts.get(row.family, 0) + 1
        row_tier = tier(row)
        tier_counts[row_tier] = tier_counts.get(row_tier, 0) + 1
    lines = [
        "# Pure Stage0 Same-Input Comparison Plan",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Repo: `{REPO_ROOT}`",
        f"Git head: `{git_head()}`",
        f"Manifest: `{rel(manifest)}`",
        f"Manifest sha256: `{sha256_file(manifest)}`",
        "",
        "## Case Coverage",
        "",
        "| family | cases |",
        "| --- | ---: |",
    ]
    for family in sorted(family_counts):
        lines.append(f"| {family} | {family_counts[family]} |")
    lines.extend(["", "| tier | cases |", "| --- | ---: |"])
    for name in ("gate", "review", "boundary"):
        lines.append(f"| {name} | {tier_counts.get(name, 0)} |")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Input identity: `{out_dir / 'input_identity.tsv'}`",
            f"- Run plan: `{out_dir / 'comparison_plan.tsv'}`",
            f"- Run environment: `{out_dir / 'run.env'}`",
            "",
            "## Run Plan",
            "",
            "| step | system | target | command |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for row in plan:
        command = row["command"].replace("|", "\\|")
        lines.append(f"| {row['step']} | {row['system']} | {row['target']} | `{command}` |")
    lines.extend(
        [
            "",
            "## Same-Input Rule",
            "",
            "The canonical inputs are the tracked `graph`, `result`, `source`, and",
            "`supersteps` fields in the manifest. Host-baseline exported edge files",
            "are derived artifacts and must be regenerated from these same rows when",
            "a new host baseline is collected.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="ascii")


def write_env(path: Path, manifest: Path, out_dir: Path) -> None:
    identity = out_dir / "input_identity.tsv"
    plan = out_dir / "comparison_plan.tsv"
    summary = out_dir / "summary.md"
    path.write_text(
        "\n".join(
            [
                f"generated_at_utc={datetime.now(timezone.utc).isoformat()}",
                f"repo_root={REPO_ROOT}",
                f"git_head={git_head()}",
                f"manifest={manifest}",
                f"manifest_sha256={sha256_file(manifest)}",
                f"input_identity={identity}",
                f"input_identity_sha256={sha256_file(identity)}",
                f"comparison_plan={plan}",
                f"comparison_plan_sha256={sha256_file(plan)}",
                f"summary={summary}",
                f"summary_sha256={sha256_file(summary)}",
                "",
            ]
        ),
        encoding="ascii",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--label", default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    label = args.label or "tracked"
    out_dir = (args.out_dir or REPO_ROOT / "results" / f"pure_stage0_comparison_plan_{label}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(manifest)
    problems = validate_rows(rows)
    if problems:
        for problem in problems:
            print(f"ERROR {problem}")
        return 1

    plan = plan_rows(label, manifest)
    write_input_identity(out_dir / "input_identity.tsv", rows)
    write_plan_tsv(out_dir / "comparison_plan.tsv", plan)
    write_summary(out_dir / "summary.md", rows, plan, manifest, out_dir)
    write_env(out_dir / "run.env", manifest, out_dir)

    print(f"cases={len(rows)} input_identity={out_dir / 'input_identity.tsv'}")
    print(f"plan={out_dir / 'comparison_plan.tsv'}")
    print(f"summary={out_dir / 'summary.md'}")
    print(f"run_env={out_dir / 'run.env'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
