#!/usr/bin/env python3
"""Export the reproducible case matrix for the pure stage0 SSSP pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_sssp_benchmark_workloads import PRESETS, CaseSpec, build_case, scenario_intent  # noqa: E402


STAGE0_VERTEX_LIMIT = 65_536


@dataclass(frozen=True)
class MatrixRow:
    preset: str
    case: str
    family: str
    vertices: int
    static_edges: int
    update_edges: int
    final_edges: int
    source: int
    supersteps: int
    pure_stage0_ok: str
    run_tier: str
    default_targets: str
    stress: str
    note: str
    intent: str


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


def classify(spec: CaseSpec) -> tuple[str, str, str, str]:
    if spec.vertices > STAGE0_VERTEX_LIMIT:
        return (
            "excluded",
            "none",
            "Exceeds the first-stage V<=65536 contract.",
            "capacity-only, not valid for pure stage0 correctness claims",
        )
    if spec.name.startswith("tiny_"):
        return (
            "gate",
            "sw_emu,hw_emu,hw",
            "Tiny correctness gate.",
            "run on every target after build",
        )
    if spec.vertices <= 4096:
        return (
            "review",
            "hw_emu,hw",
            "Small review scale.",
            "use sw_emu selectively; run default review on hw_emu/hw",
        )
    return (
        "boundary",
        "hw",
        "Stage0 vertex-limit boundary.",
        "prepare-only before hw; run on hw after smoke passes",
    )


def stress_name(family: str) -> str:
    if family == "chain":
        return "diameter-superstep-overhead"
    if family == "hot-source":
        return "source-fanout-throughput"
    if family == "spread":
        return "balanced-partition-traffic"
    if family == "hot-dest":
        return "gather-min-hotspot"
    return "general"


def make_row(preset: str, spec: CaseSpec) -> MatrixRow:
    static_edges, updates, final_edges = build_case(spec)
    run_tier, default_targets, stress, note = classify(spec)
    return MatrixRow(
        preset=preset,
        case=spec.name,
        family=spec.family,
        vertices=spec.vertices,
        static_edges=len(static_edges),
        update_edges=len(updates),
        final_edges=len(final_edges),
        source=spec.source,
        supersteps=spec.supersteps,
        pure_stage0_ok="yes" if spec.vertices <= STAGE0_VERTEX_LIMIT else "no",
        run_tier=run_tier,
        default_targets=default_targets,
        stress=stress_name(spec.family),
        note=note,
        intent=scenario_intent(spec.family),
    )


def collect_rows(presets: list[str]) -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    seen: set[str] = set()
    for preset in presets:
        for spec in PRESETS[preset]:
            key = spec.name
            if key in seen:
                continue
            seen.add(key)
            rows.append(make_row(preset, spec))
    return rows


def write_tsv(path: Path, rows: list[MatrixRow]) -> None:
    fields = list(MatrixRow.__dataclass_fields__)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_env(path: Path, presets: list[str], matrix_path: Path) -> None:
    script_path = SCRIPT_DIR / "export_pure_stage0_case_matrix.py"
    generator_path = SCRIPT_DIR / "generate_sssp_benchmark_workloads.py"
    path.write_text(
        "\n".join(
            [
                f"generated_at_utc={datetime.now(timezone.utc).isoformat()}",
                f"repo_root={REPO_ROOT}",
                f"git_head={git_head()}",
                f"presets={','.join(presets)}",
                f"stage0_vertex_limit={STAGE0_VERTEX_LIMIT}",
                f"matrix={matrix_path}",
                f"matrix_sha256={sha256_file(matrix_path)}",
                f"script={script_path}",
                f"script_sha256={sha256_file(script_path)}",
                f"generator={generator_path}",
                f"generator_sha256={sha256_file(generator_path)}",
                "",
            ]
        ),
        encoding="ascii",
    )


def write_markdown(path: Path, rows: list[MatrixRow], presets: list[str], matrix_path: Path) -> None:
    family_counts = Counter(row.family for row in rows if row.pure_stage0_ok == "yes")
    tier_counts = Counter(row.run_tier for row in rows)
    target_counts = Counter()
    for row in rows:
        for target in row.default_targets.split(","):
            if target and target != "none":
                target_counts[target] += 1

    lines: list[str] = [
        "# Pure Stage0 SSSP Case Matrix",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        f"Repo: `{REPO_ROOT}`",
        f"Git head: `{git_head()}`",
        f"Presets: `{','.join(presets)}`",
        f"Stage0 vertex limit: `V <= {STAGE0_VERTEX_LIMIT}`",
        f"Matrix TSV: `{matrix_path}`",
        f"Matrix sha256: `{sha256_file(matrix_path)}`",
        "",
        "## Coverage",
        "",
        "| family | stage0 cases |",
        "| --- | ---: |",
    ]
    for family in ["chain", "hot-source", "spread", "hot-dest"]:
        lines.append(f"| {family} | {family_counts[family]} |")

    lines.extend(
        [
            "",
            "| run_tier | cases | meaning |",
            "| --- | ---: | --- |",
            f"| gate | {tier_counts['gate']} | Tiny cases to run on sw_emu, hw_emu, and hw. |",
            f"| review | {tier_counts['review']} | Small cases for regular hw_emu and hw comparison. |",
            f"| boundary | {tier_counts['boundary']} | V-limit or high-cost cases for prepare checks and hw timing. |",
            f"| excluded | {tier_counts['excluded']} | Not valid for pure stage0 correctness claims. |",
            "",
            "| default target | cases |",
            "| --- | ---: |",
        ]
    )
    for target in ["sw_emu", "hw_emu", "hw"]:
        lines.append(f"| {target} | {target_counts[target]} |")

    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "Generate the exact workload files for this matrix:",
            "",
            "```bash",
            "cd /home/chuxiao/grasu-regraph-integration",
            "./scripts/generate_sssp_benchmark_workloads.py \\",
            "  --preset pure_stage0 \\",
            "  --out-root workloads/sssp_benchmark_pure_stage0",
            "```",
            "",
            "Run prepare-only checks before expensive target runs:",
            "",
            "```bash",
            "cd /home/chuxiao/grasu-regraph-integration",
            "./scripts/run_pure_pipeline_prepare_check.sh \\",
            "  --preset pure_stage0 \\",
            "  --workload-root workloads/sssp_benchmark_pure_stage0 \\",
            "  --out-dir results/pure_pipeline_prepare_pure_stage0_<label>",
            "```",
            "",
            "Run the target smoke gate with the same manifest:",
            "",
            "```bash",
            "cd /home/chuxiao/grasu-regraph-integration",
            "./scripts/run_pure_pipeline_smoke.sh \\",
            "  --target <sw_emu|hw_emu|hw> \\",
            "  --manifest workloads/sssp_benchmark_pure_stage0/manifest.tsv \\",
            "  --family chain --family hot-source --family spread --family hot-dest \\",
            "  --max-cases 4 \\",
            "  --out-dir results/pure_pipeline_<target>_pure_stage0_gate_<label>",
            "```",
            "",
            "Run selected larger cases after the target smoke gate passes:",
            "",
            "```bash",
            "cd /home/chuxiao/grasu-regraph-integration",
            "./scripts/run_pure_pipeline_smoke.sh \\",
            "  --target hw \\",
            "  --manifest workloads/sssp_benchmark_pure_stage0/manifest.tsv \\",
            "  --case large_chain_v4096 \\",
            "  --case medium_star_v65536_u8192 \\",
            "  --case medium_spread_v65536_u16384 \\",
            "  --case boundary_hotdst_v65536_u4096 \\",
            "  --out-dir results/pure_pipeline_hw_pure_stage0_boundary_<label>",
            "```",
            "",
            "## Cases",
            "",
            "| case | family | V | updates | final_edges | supersteps | tier | default_targets | stress |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {case} | {family} | {vertices} | {update_edges} | {final_edges} | "
            "{supersteps} | {run_tier} | {default_targets} | {stress} |".format(**row.__dict__)
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        action="append",
        choices=sorted(PRESETS),
        default=None,
        help="Preset to include. Can be repeated. Default: pure_stage0.",
    )
    parser.add_argument("--label", default=None, help="Label used in the default output directory.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory for matrix files.")
    args = parser.parse_args()

    presets = args.preset or ["pure_stage0"]
    label = args.label or "_".join(presets)
    out_dir = args.out_dir or (REPO_ROOT / "results" / f"pure_pipeline_stage0_case_matrix_{label}")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect_rows(presets)
    matrix_path = out_dir / "case_matrix.tsv"
    summary_path = out_dir / "summary.md"
    env_path = out_dir / "run.env"
    write_tsv(matrix_path, rows)
    write_markdown(summary_path, rows, presets, matrix_path)
    write_env(env_path, presets, matrix_path)

    print(f"cases={len(rows)} matrix={matrix_path}")
    print(f"summary={summary_path}")
    print(f"run_env={env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
