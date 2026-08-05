#!/usr/bin/env python3
"""Aggregate correctness-admitted matched FPGA repetitions."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import statistics


@dataclass(frozen=True)
class MatchedSample:
    case: str
    algorithm: str
    graph: str
    gr_event_e2e_ms: float
    spine_dynamic_kernel_ms: float
    speedup: float


def load_summary(path: Path) -> list[MatchedSample]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    samples = []
    for row in rows:
        identity = f"{row.get('algorithm', '')}:{row.get('case', '')}"
        if (
            row.get("gr_status") != "PASS"
            or row.get("spine_status") != "PASS"
            or row.get("comparison_status") != "ADMITTED"
        ):
            raise ValueError(f"non-admitted row in {path}: {identity}")
        try:
            sample = MatchedSample(
                case=row["case"],
                algorithm=row["algorithm"],
                graph=str(Path(row["graph"]).resolve()),
                gr_event_e2e_ms=float(row["gr_event_e2e_ms"]),
                spine_dynamic_kernel_ms=float(row["spine_dynamic_kernel_ms"]),
                speedup=float(row["kernel_speedup_gr_over_spine"]),
            )
        except (KeyError, ValueError) as error:
            raise ValueError(f"invalid timing row in {path}: {identity}") from error
        if (
            not sample.case
            or not sample.algorithm
            or sample.gr_event_e2e_ms <= 0.0
            or sample.spine_dynamic_kernel_ms <= 0.0
            or sample.speedup <= 0.0
        ):
            raise ValueError(f"invalid timing value in {path}: {identity}")
        samples.append(sample)
    if not samples:
        raise ValueError(f"empty matched FPGA summary: {path}")
    return samples


def coefficient_of_variation_pct(values: list[float]) -> float:
    mean = statistics.mean(values)
    return 100.0 * statistics.pstdev(values) / mean if len(values) > 1 else 0.0


def aggregate(samples: list[MatchedSample]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[MatchedSample]] = {}
    for sample in samples:
        grouped.setdefault((sample.algorithm, sample.case), []).append(sample)

    rows = []
    for (algorithm, case), group in sorted(grouped.items()):
        graphs = {sample.graph for sample in group}
        if len(graphs) != 1:
            raise ValueError(f"graph identity changed across repeats: {algorithm}:{case}")
        gr = [sample.gr_event_e2e_ms for sample in group]
        spine = [sample.spine_dynamic_kernel_ms for sample in group]
        speedups = [sample.speedup for sample in group]
        median_speedup = statistics.median(speedups)
        rows.append(
            {
                "algorithm": algorithm,
                "case": case,
                "graph": graphs.pop(),
                "samples": len(group),
                "gr_event_e2e_median_ms": statistics.median(gr),
                "gr_event_e2e_cv_pct": coefficient_of_variation_pct(gr),
                "spine_dynamic_kernel_median_ms": statistics.median(spine),
                "spine_dynamic_kernel_cv_pct": coefficient_of_variation_pct(spine),
                "kernel_speedup_gr_over_spine_median": median_speedup,
                "kernel_speedup_min": min(speedups),
                "kernel_speedup_max": max(speedups),
                "winner": "Spine" if median_speedup > 1.0 else "G+R",
            }
        )
    return rows


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    samples = []
    for path in args.summary:
        samples.extend(load_summary(path.resolve()))
    rows = aggregate(samples)
    write_tsv(args.output, rows)
    print(
        "MATCHED_FPGA_REPEAT_AGGREGATION_PASS "
        f"summaries={len(args.summary)} groups={len(rows)} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
