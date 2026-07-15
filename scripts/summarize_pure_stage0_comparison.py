#!/usr/bin/env python3
"""Summarize pure_stage0 host, Spine, and optional pure-pipeline results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "workloads" / "sssp_benchmark_pure_stage0" / "manifest.tsv"
GATE_CASES = {
    "tiny_chain_v16",
    "tiny_star_v16_u12",
    "tiny_spread_v16_u8",
    "tiny_hotdst_v64_u32",
}

COLUMNS = [
    "case",
    "family",
    "tier",
    "vertices",
    "update_edges",
    "final_edges",
    "source",
    "supersteps",
    "host_status",
    "host_grasu_ms",
    "host_regraph_e2e_ms",
    "host_zero_cost_ms",
    "host_mismatch_count",
    "spine_status",
    "spine_maint_ms",
    "spine_conv_ms",
    "spine_kernel_e2e_ms",
    "spine_errors",
    "host_zero_over_spine_kernel",
    "pure_status",
    "pure_target",
    "pure_event_e2e_ms",
    "pure_grasu_ms",
    "pure_barrier_ms",
    "pure_adapter_ms",
    "pure_lksg_ms",
    "pure_apply_ms",
    "pure_hbm_ms",
    "pure_mismatches",
    "notes",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def by_case(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.is_file():
        return {}
    return {row["case"]: row for row in read_tsv(path) if row.get("case")}


def read_env(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return "MISSING"
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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def parse_float(text: str | None) -> float | None:
    if text is None or text in ("", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def timing_map(line: str | None) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line or "")}


def value_map(line: str | None) -> dict[str, str]:
    return timing_map(line)


def tier_for(row: dict[str, str], identity_rows: dict[str, dict[str, str]]) -> str:
    case = row.get("case", "")
    if case in identity_rows and identity_rows[case].get("tier"):
        return identity_rows[case]["tier"]
    if case in GATE_CASES:
        return "gate"
    if row.get("vertices") == "65536":
        return "boundary"
    return "review"


def status_counts(rows: list[dict[str, str]], field: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(field, "")
        counts[value or "MISSING"] += 1
    return counts


def count_identity(path: Path | None) -> tuple[int, int]:
    if path is None or not path.is_file():
        return 0, 0
    rows = read_tsv(path)
    failures = sum(1 for row in rows if row.get("ok") != "yes")
    return len(rows), failures


def joined_rows(
    manifest_rows: list[dict[str, str]],
    identity_rows: dict[str, dict[str, str]],
    host_rows: dict[str, dict[str, str]],
    spine_rows: dict[str, dict[str, str]],
    pure_rows: dict[str, dict[str, str]],
    pure_target: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for manifest in manifest_rows:
        case = manifest["case"]
        host = host_rows.get(case, {})
        spine = spine_rows.get(case, {})
        pure = pure_rows.get(case, {})
        pure_timing = timing_map(pure.get("timing_line"))
        pure_result = value_map(pure.get("result_line"))

        grasu_ms = parse_float(host.get("grasu_ms"))
        regraph_ms = parse_float(host.get("regraph_e2e_ms"))
        zero_cost_ms = None if grasu_ms is None or regraph_ms is None else grasu_ms + regraph_ms
        spine_kernel_ms = parse_float(spine.get("kernel_e2e_ms"))
        zero_over_spine = None
        if zero_cost_ms is not None and spine_kernel_ms not in (None, 0.0):
            zero_over_spine = zero_cost_ms / spine_kernel_ms

        notes: list[str] = []
        if not host:
            notes.append("missing host baseline")
        elif host.get("status") != "PASS":
            notes.append("host baseline not PASS")
        if host.get("mismatch_count") not in ("", "0", "0.0"):
            notes.append("host mismatches")
        if spine_rows:
            if not spine:
                notes.append("missing spine baseline")
            elif spine.get("status") != "PASS":
                notes.append("spine not PASS")
            if spine.get("errors") not in ("", "0", "0.0"):
                notes.append("spine errors")
        if pure_rows:
            if not pure:
                notes.append("missing pure pipeline")
            else:
                if pure.get("status") != "PASS":
                    notes.append("pure pipeline not PASS")
                if pure_result.get("mismatches") not in ("", "0", "0.0"):
                    notes.append("pure mismatches")
                if pure_target != "hw":
                    notes.append(f"pure timing is {pure_target}, not hw")

        out.append(
            {
                "case": case,
                "family": manifest.get("family", ""),
                "tier": tier_for(manifest, identity_rows),
                "vertices": manifest.get("vertices", ""),
                "update_edges": manifest.get("update_edges", ""),
                "final_edges": manifest.get("final_edges", ""),
                "source": manifest.get("source", ""),
                "supersteps": manifest.get("supersteps", ""),
                "host_status": host.get("status", ""),
                "host_grasu_ms": fmt(grasu_ms),
                "host_regraph_e2e_ms": fmt(regraph_ms),
                "host_zero_cost_ms": fmt(zero_cost_ms),
                "host_mismatch_count": host.get("mismatch_count", ""),
                "spine_status": spine.get("status", ""),
                "spine_maint_ms": spine.get("maint_ms", ""),
                "spine_conv_ms": spine.get("conv_ms", ""),
                "spine_kernel_e2e_ms": spine.get("kernel_e2e_ms", ""),
                "spine_errors": spine.get("errors", ""),
                "host_zero_over_spine_kernel": fmt(zero_over_spine),
                "pure_status": pure.get("status", ""),
                "pure_target": pure_target if pure else "",
                "pure_event_e2e_ms": pure_timing.get("event_e2e_ms", ""),
                "pure_grasu_ms": pure_timing.get("grasu_ms", ""),
                "pure_barrier_ms": pure_timing.get("barrier_ms", ""),
                "pure_adapter_ms": pure_timing.get("adapter_ms", ""),
                "pure_lksg_ms": pure_timing.get("lksg_ms", ""),
                "pure_apply_ms": pure_timing.get("apply_ms", ""),
                "pure_hbm_ms": pure_timing.get("hbm_ms", ""),
                "pure_mismatches": pure_result.get("mismatches", ""),
                "notes": "; ".join(notes),
            }
        )
    return out


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, str]]) -> str:
    cols = [
        "case",
        "tier",
        "vertices",
        "final_edges",
        "host_zero_cost_ms",
        "spine_kernel_e2e_ms",
        "host_zero_over_spine_kernel",
        "pure_target",
        "pure_event_e2e_ms",
        "host_status",
        "spine_status",
        "pure_status",
        "notes",
    ]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(col, "").replace("|", "\\|") for col in cols) + " |")
    return "\n".join(lines)


def write_markdown(
    path: Path,
    rows: list[dict[str, str]],
    *,
    manifest: Path,
    input_identity: Path | None,
    host_summary: Path,
    spine_summary: Path | None,
    host_identity: Path | None,
    pure_summary: Path | None,
    pure_env: Path | None,
    pure_target: str,
) -> None:
    identity_checks, identity_failures = count_identity(host_identity)
    lines = [
        "# Pure Stage0 Comparison",
        "",
        "This report joins the tracked pure_stage0 manifest with the accepted",
        "`GraSU -> host -> ReGraph` baseline, the zero-cost handoff timing",
        "`grasu_ms + regraph_e2e_ms`, the split-Spine edge-file baseline, and",
        "an optional pure-pipeline run.",
        "",
        "## Inputs",
        "",
        f"- Manifest: `{rel(manifest)}` sha256={sha256(manifest)}",
        f"- Input identity: `{rel(input_identity)}` sha256={sha256(input_identity)}",
        f"- Host summary: `{rel(host_summary)}` sha256={sha256(host_summary)}",
        f"- Host identity audit: `{rel(host_identity)}` sha256={sha256(host_identity)}",
        f"- Spine summary: `{rel(spine_summary)}` sha256={sha256(spine_summary)}",
        f"- Pure summary: `{rel(pure_summary)}` sha256={sha256(pure_summary)}",
        f"- Pure env: `{rel(pure_env)}` sha256={sha256(pure_env)}",
        f"- Pure target: `{pure_target}`",
        "",
        "## Status Counts",
        "",
        f"- Host: {dict(status_counts(rows, 'host_status'))}",
        f"- Spine: {dict(status_counts(rows, 'spine_status'))}",
        f"- Pure: {dict(status_counts(rows, 'pure_status'))}",
        f"- Host identity audit: checks={identity_checks} failures={identity_failures}",
        "",
        "## Timing",
        "",
        "`host_zero_cost_ms` intentionally excludes graph D2H, host conversion,",
        "and graph H2D handoff time. `host_zero_over_spine_kernel > 1` means the",
        "zero-cost host baseline is slower than Spine kernel time.",
        "",
        markdown_table(rows),
        "",
    ]
    path.write_text("\n".join(lines), encoding="ascii")


def write_run_env(
    path: Path,
    *,
    label: str,
    manifest: Path,
    input_identity: Path | None,
    host_summary: Path,
    spine_summary: Path | None,
    host_identity: Path | None,
    pure_summary: Path | None,
    pure_env: Path | None,
    pure_target: str,
    comparison_tsv: Path,
    comparison_md: Path,
) -> None:
    lines = [
        f"label={label}",
        f"git_head={git_head()}",
        f"manifest={manifest.resolve()}",
        f"manifest_sha256={sha256(manifest)}",
        f"input_identity={input_identity.resolve() if input_identity else ''}",
        f"input_identity_sha256={sha256(input_identity)}",
        f"host_summary={host_summary.resolve()}",
        f"host_summary_sha256={sha256(host_summary)}",
        f"host_identity={host_identity.resolve() if host_identity else ''}",
        f"host_identity_sha256={sha256(host_identity)}",
        f"spine_summary={spine_summary.resolve() if spine_summary else ''}",
        f"spine_summary_sha256={sha256(spine_summary)}",
        f"pure_summary={pure_summary.resolve() if pure_summary else ''}",
        f"pure_summary_sha256={sha256(pure_summary)}",
        f"pure_env={pure_env.resolve() if pure_env else ''}",
        f"pure_env_sha256={sha256(pure_env)}",
        f"pure_target={pure_target}",
        f"comparison_tsv={comparison_tsv.resolve()}",
        f"comparison_md={comparison_md.resolve()}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--input-identity", type=Path, default=None)
    parser.add_argument("--host-summary", type=Path, required=True)
    parser.add_argument("--spine-summary", type=Path, default=None)
    parser.add_argument("--host-identity", type=Path, default=None)
    parser.add_argument("--pure-summary", type=Path, default=None)
    parser.add_argument("--pure-env", type=Path, default=None)
    parser.add_argument("--pure-target", default=None)
    parser.add_argument("--label", default="")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    input_identity = args.input_identity.resolve() if args.input_identity else None
    host_summary = args.host_summary.resolve()
    spine_summary = args.spine_summary.resolve() if args.spine_summary else None
    host_identity = args.host_identity.resolve() if args.host_identity else None
    pure_summary = args.pure_summary.resolve() if args.pure_summary else None
    pure_env = args.pure_env.resolve() if args.pure_env else None
    pure_env_values = read_env(pure_env)
    pure_target = args.pure_target or pure_env_values.get("target", "")

    manifest_rows = read_tsv(manifest)
    identity_rows = by_case(input_identity)
    rows = joined_rows(
        manifest_rows,
        identity_rows,
        by_case(host_summary),
        by_case(spine_summary),
        by_case(pure_summary),
        pure_target,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    comparison_tsv = args.out_dir / "comparison.tsv"
    comparison_md = args.out_dir / "comparison.md"
    run_env = args.out_dir / "run.env"
    write_tsv(comparison_tsv, rows)
    write_markdown(
        comparison_md,
        rows,
        manifest=manifest,
        input_identity=input_identity,
        host_summary=host_summary,
        spine_summary=spine_summary,
        host_identity=host_identity,
        pure_summary=pure_summary,
        pure_env=pure_env,
        pure_target=pure_target,
    )
    write_run_env(
        run_env,
        label=args.label,
        manifest=manifest,
        input_identity=input_identity,
        host_summary=host_summary,
        spine_summary=spine_summary,
        host_identity=host_identity,
        pure_summary=pure_summary,
        pure_env=pure_env,
        pure_target=pure_target,
        comparison_tsv=comparison_tsv,
        comparison_md=comparison_md,
    )
    print(f"DONE comparison_tsv={comparison_tsv}")
    print(f"DONE comparison_md={comparison_md}")
    print(f"DONE run_env={run_env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
