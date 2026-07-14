#!/usr/bin/env python3
"""Join pure-pipeline and GraSU->host->ReGraph smoke summaries."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


COLUMNS = [
    "case",
    "family",
    "vertices",
    "final_edges",
    "source",
    "supersteps",
    "host_status",
    "host_wall_seconds",
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
    "pure_adapter_ms",
    "pure_lksg_ms",
    "pure_apply_ms",
    "pure_hbm_ms",
    "pure_wall_ms",
    "notes",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def rows_by_case(path: Path) -> dict[str, dict[str, str]]:
    return {row["case"]: row for row in read_tsv(path) if row.get("case")}


def read_env(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key] = value
    return out


def parse_float(text: str | None) -> float | None:
    if text is None or text == "" or text == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def timing_map(line: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line or "")}


def case_union(*tables: dict[str, dict[str, str]]) -> list[str]:
    names: set[str] = set()
    for table in tables:
        names.update(table)
    return sorted(names)


def joined_rows(
    host_rows: dict[str, dict[str, str]],
    pure_rows: dict[str, dict[str, str]],
    spine_rows: dict[str, dict[str, str]],
    pure_target: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for case in case_union(host_rows, pure_rows, spine_rows):
        host = host_rows.get(case, {})
        pure = pure_rows.get(case, {})
        spine = spine_rows.get(case, {})
        timing = timing_map(pure.get("timing_line", ""))
        grasu_ms = parse_float(host.get("grasu_ms"))
        regraph_ms = parse_float(host.get("regraph_e2e_ms"))
        zero_cost_ms = None if grasu_ms is None or regraph_ms is None else grasu_ms + regraph_ms
        spine_kernel_ms = parse_float(spine.get("kernel_e2e_ms"))
        host_over_spine = None
        if zero_cost_ms is not None and spine_kernel_ms not in (None, 0.0):
            host_over_spine = zero_cost_ms / spine_kernel_ms

        notes = []
        if host.get("status") != "PASS":
            notes.append("host baseline not PASS")
        if spine_rows and spine.get("status") != "PASS":
            notes.append("spine not PASS")
        if pure.get("status") != "PASS":
            notes.append("pure pipeline not PASS")
        if pure_target != "hw":
            notes.append(f"pure timing is {pure_target}, not hw performance")

        row = {
            "case": case,
            "family": host.get("family", pure.get("family", "")),
            "vertices": host.get("vertices", pure.get("vertices", "")),
            "final_edges": host.get("final_edges", pure.get("final_edges", "")),
            "source": host.get("source", pure.get("source", "")),
            "supersteps": host.get("supersteps", pure.get("supersteps", "")),
            "host_status": host.get("status", ""),
            "host_wall_seconds": host.get("wall_seconds", ""),
            "host_grasu_ms": fmt(grasu_ms),
            "host_regraph_e2e_ms": fmt(regraph_ms),
            "host_zero_cost_ms": fmt(zero_cost_ms),
            "host_mismatch_count": host.get("mismatch_count", ""),
            "spine_status": spine.get("status", ""),
            "spine_maint_ms": spine.get("maint_ms", ""),
            "spine_conv_ms": spine.get("conv_ms", ""),
            "spine_kernel_e2e_ms": spine.get("kernel_e2e_ms", ""),
            "spine_errors": spine.get("errors", ""),
            "host_zero_over_spine_kernel": fmt(host_over_spine),
            "pure_status": pure.get("status", ""),
            "pure_target": pure_target,
            "pure_event_e2e_ms": timing.get("event_e2e_ms", ""),
            "pure_grasu_ms": timing.get("grasu_ms", ""),
            "pure_adapter_ms": timing.get("adapter_ms", ""),
            "pure_lksg_ms": timing.get("lksg_ms", ""),
            "pure_apply_ms": timing.get("apply_ms", ""),
            "pure_hbm_ms": timing.get("hbm_ms", ""),
            "pure_wall_ms": timing.get("wall_ms", ""),
            "notes": "; ".join(notes),
        }
        out.append(row)
    return out


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, str]]) -> str:
    columns = [
        "case",
        "host_zero_cost_ms",
        "host_grasu_ms",
        "host_regraph_e2e_ms",
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
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(col, "").replace("|", "\\|") for col in columns) + " |")
    return "\n".join(lines) + "\n"


def write_markdown(
    path: Path,
    rows: list[dict[str, str]],
    *,
    host_summary: Path,
    pure_summary: Path,
    spine_summary: Path | None,
    pure_env: Path | None,
) -> None:
    lines = [
        "# Pure Pipeline Smoke Comparison",
        "",
        "This table aligns the same smoke cases across the current host baseline",
        "and the pure-pipeline runner. `host_zero_cost_ms` is computed as",
        "`host_grasu_ms + host_regraph_e2e_ms`, so the host graph handoff cost is",
        "intentionally set to zero.",
        "",
        f"- Host baseline summary: `{host_summary}`",
        f"- Pure pipeline summary: `{pure_summary}`",
    ]
    if spine_summary is not None:
        lines.append(f"- Spine summary: `{spine_summary}`")
    if pure_env is not None:
        lines.append(f"- Pure pipeline environment: `{pure_env}`")
    lines.extend(("", markdown_table(rows)))
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-summary", type=Path, required=True)
    parser.add_argument("--pure-summary", type=Path, required=True)
    parser.add_argument("--spine-summary", type=Path, default=None)
    parser.add_argument("--pure-env", type=Path, default=None)
    parser.add_argument("--pure-target", default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    pure_env = read_env(args.pure_env)
    pure_target = args.pure_target or pure_env.get("target", "unknown")
    spine_rows = rows_by_case(args.spine_summary) if args.spine_summary is not None else {}
    rows = joined_rows(
        rows_by_case(args.host_summary),
        rows_by_case(args.pure_summary),
        spine_rows,
        pure_target,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(args.out_dir / "comparison.tsv", rows)
    write_markdown(
        args.out_dir / "comparison.md",
        rows,
        host_summary=args.host_summary.resolve(),
        pure_summary=args.pure_summary.resolve(),
        spine_summary=args.spine_summary.resolve() if args.spine_summary is not None else None,
        pure_env=args.pure_env.resolve() if args.pure_env is not None else None,
    )
    print(f"DONE comparison_tsv={args.out_dir / 'comparison.tsv'}")
    print(f"DONE comparison_md={args.out_dir / 'comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
