#!/usr/bin/env python3
"""Compare Spine and GraSU->ReGraph SSSP summary TSV files.

The two runners currently use different workload front ends, so this script
does not assume identical inputs. Pair rows explicitly with --pair when doing
scenario-level comparisons.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PAIR_COLUMNS = [
    "label",
    "chain_case",
    "spine_case",
    "chain_status",
    "spine_status",
    "chain_vertices",
    "chain_final_edges",
    "spine_vertices",
    "spine_input_edges",
    "chain_total_ms",
    "grasu_ms",
    "regraph_e2e_ms",
    "spine_kernel_e2e_ms",
    "spine_maint_conv_ms",
    "chain_over_spine_kernel",
    "chain_over_spine_maint_conv",
    "notes",
]


@dataclass(frozen=True)
class PairSpec:
    chain_case: str
    spine_case: str
    label: str


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="ascii", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def by_case(rows: Iterable[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        case = row.get("case", "")
        if case:
            out[case] = row
    return out


def parse_float(text: str | None) -> float | None:
    if text is None or text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt_num(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6g}"


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def parse_pair(text: str) -> PairSpec:
    if "=" not in text:
        raise argparse.ArgumentTypeError("--pair must look like chain_case=spine_case[:label]")
    chain_case, rhs = text.split("=", 1)
    if ":" in rhs:
        spine_case, label = rhs.split(":", 1)
    else:
        spine_case = rhs
        label = f"{chain_case}_vs_{spine_case}"
    if not chain_case or not spine_case:
        raise argparse.ArgumentTypeError("--pair must include both case names")
    return PairSpec(chain_case=chain_case, spine_case=spine_case, label=label)


def default_pairs(chain: dict[str, dict[str, str]], spine: dict[str, dict[str, str]]) -> list[PairSpec]:
    common = sorted(set(chain) & set(spine))
    return [PairSpec(case, case, case) for case in common]


def paired_row(pair: PairSpec, chain: dict[str, dict[str, str]], spine: dict[str, dict[str, str]]) -> dict[str, str]:
    chain_row = chain.get(pair.chain_case)
    spine_row = spine.get(pair.spine_case)

    notes: list[str] = []
    if chain_row is None:
        notes.append("missing chain case")
        chain_row = {}
    if spine_row is None:
        notes.append("missing spine case")
        spine_row = {}

    grasu_ms = parse_float(chain_row.get("grasu_ms"))
    regraph_ms = parse_float(chain_row.get("regraph_e2e_ms"))
    chain_total = None if grasu_ms is None or regraph_ms is None else grasu_ms + regraph_ms

    spine_kernel_ms = parse_float(spine_row.get("kernel_e2e_ms"))
    maint_ms = parse_float(spine_row.get("maint_ms"))
    conv_ms = parse_float(spine_row.get("conv_ms"))
    spine_maint_conv = None if maint_ms is None or conv_ms is None else maint_ms + conv_ms

    chain_status = chain_row.get("status", "")
    spine_status = spine_row.get("status", "")
    if chain_status != "PASS":
        notes.append("chain not PASS")
    if spine_status != "PASS":
        notes.append("spine not PASS")

    return {
        "label": pair.label,
        "chain_case": pair.chain_case,
        "spine_case": pair.spine_case,
        "chain_status": chain_status,
        "spine_status": spine_status,
        "chain_vertices": chain_row.get("vertices", ""),
        "chain_final_edges": chain_row.get("final_edges", ""),
        "spine_vertices": spine_row.get("vertices", ""),
        "spine_input_edges": spine_row.get("input_edges", ""),
        "chain_total_ms": fmt_num(chain_total),
        "grasu_ms": fmt_num(grasu_ms),
        "regraph_e2e_ms": fmt_num(regraph_ms),
        "spine_kernel_e2e_ms": fmt_num(spine_kernel_ms),
        "spine_maint_conv_ms": fmt_num(spine_maint_conv),
        "chain_over_spine_kernel": fmt_num(ratio(chain_total, spine_kernel_ms)),
        "chain_over_spine_maint_conv": fmt_num(ratio(chain_total, spine_maint_conv)),
        "notes": "; ".join(notes),
    }


def markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "_No paired rows. Pass `--pair chain_case=spine_case[:label]` for scenario-level comparison._\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = [row.get(col, "").replace("|", "\\|") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def write_tsv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(
    path: Path,
    rows: list[dict[str, str]],
    *,
    chain_summary: Path,
    spine_summary: Path,
    pairs: list[PairSpec],
) -> None:
    compact_cols = [
        "label",
        "chain_case",
        "spine_case",
        "chain_total_ms",
        "spine_kernel_e2e_ms",
        "spine_maint_conv_ms",
        "chain_over_spine_kernel",
        "chain_over_spine_maint_conv",
        "notes",
    ]
    text = [
        "# Spine vs GraSU+ReGraph Comparison",
        "",
        "This is a summary-table join. It is only an identical-input comparison if",
        "the selected pairs are known to represent the same graph/update/SSSP workload.",
        "",
        "## Inputs",
        "",
        f"- GraSU+ReGraph summary: `{chain_summary}`",
        f"- Spine summary: `{spine_summary}`",
        f"- Pairs: {len(pairs)}",
        "",
        "## Timing Columns",
        "",
        "- `chain_total_ms = grasu_ms + regraph_e2e_ms`.",
        "- `spine_kernel_e2e_ms` is Spine's kernel e2e field when present.",
        "- `spine_maint_conv_ms = maint_ms + conv_ms` when both fields are present.",
        "- `chain_over_spine_* > 1` means the chain is slower than that Spine timing column.",
        "",
        "## Paired Results",
        "",
        markdown_table(rows, compact_cols),
    ]
    path.write_text("\n".join(text), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain-summary", type=Path, required=True)
    parser.add_argument("--spine-summary", type=Path, required=True)
    parser.add_argument("--pair", action="append", type=parse_pair, default=[])
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    chain_summary = args.chain_summary.resolve()
    spine_summary = args.spine_summary.resolve()
    chain = by_case(read_tsv(chain_summary))
    spine = by_case(read_tsv(spine_summary))

    pairs = args.pair or default_pairs(chain, spine)
    rows = [paired_row(pair, chain, spine) for pair in pairs]

    if args.out_dir is None:
        print(markdown_table(rows, PAIR_COLUMNS), end="")
        return 0

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(out_dir / "comparison.tsv", rows, PAIR_COLUMNS)
    write_markdown(
        out_dir / "comparison.md",
        rows,
        chain_summary=chain_summary,
        spine_summary=spine_summary,
        pairs=pairs,
    )
    print(f"DONE comparison_tsv={out_dir / 'comparison.tsv'}")
    print(f"DONE comparison_md={out_dir / 'comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
