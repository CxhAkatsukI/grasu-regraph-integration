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
    spine_dynamic_device_e2e_ms: float | None = None
    device_speedup: float | None = None
    gr_setup_inclusive_ms: float | None = None
    spine_dynamic_setup_inclusive_ms: float | None = None
    setup_speedup: float | None = None


def load_summary(
    path: Path,
    *,
    skip_rejected: bool = False,
) -> list[MatchedSample]:
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
            if skip_rejected:
                continue
            raise ValueError(f"non-admitted row in {path}: {identity}")
        try:
            sample = MatchedSample(
                case=row["case"],
                algorithm=row["algorithm"],
                graph=str(Path(row["graph"]).resolve()),
                gr_event_e2e_ms=float(row["gr_event_e2e_ms"]),
                spine_dynamic_kernel_ms=float(row["spine_dynamic_kernel_ms"]),
                speedup=float(row["kernel_speedup_gr_over_spine"]),
                spine_dynamic_device_e2e_ms=(
                    float(row["spine_dynamic_device_e2e_ms"])
                    if row.get("spine_dynamic_device_e2e_ms")
                    else None
                ),
                device_speedup=(
                    float(row["device_e2e_speedup_gr_over_spine"])
                    if row.get("device_e2e_speedup_gr_over_spine")
                    else None
                ),
                gr_setup_inclusive_ms=(
                    float(row["gr_setup_inclusive_ms"])
                    if row.get("gr_setup_inclusive_ms")
                    else None
                ),
                spine_dynamic_setup_inclusive_ms=(
                    float(row["spine_dynamic_setup_inclusive_ms"])
                    if row.get("spine_dynamic_setup_inclusive_ms")
                    else None
                ),
                setup_speedup=(
                    float(row["setup_speedup_gr_over_spine"])
                    if row.get("setup_speedup_gr_over_spine")
                    else None
                ),
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
        device_spine = [
            sample.spine_dynamic_device_e2e_ms
            for sample in group
            if sample.spine_dynamic_device_e2e_ms is not None
        ]
        device_speedups = [
            sample.device_speedup
            for sample in group
            if sample.device_speedup is not None
        ]
        gr_setup = [
            sample.gr_setup_inclusive_ms
            for sample in group
            if sample.gr_setup_inclusive_ms is not None
        ]
        spine_setup = [
            sample.spine_dynamic_setup_inclusive_ms
            for sample in group
            if sample.spine_dynamic_setup_inclusive_ms is not None
        ]
        setup_speedups = [
            sample.setup_speedup
            for sample in group
            if sample.setup_speedup is not None
        ]
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
                "spine_dynamic_device_e2e_median_ms": (
                    statistics.median(device_spine) if device_spine else ""
                ),
                "spine_dynamic_device_e2e_cv_pct": (
                    coefficient_of_variation_pct(device_spine)
                    if device_spine
                    else ""
                ),
                "device_e2e_speedup_median": (
                    statistics.median(device_speedups)
                    if device_speedups
                    else ""
                ),
                "device_e2e_speedup_min": (
                    min(device_speedups) if device_speedups else ""
                ),
                "device_e2e_speedup_max": (
                    max(device_speedups) if device_speedups else ""
                ),
                "gr_setup_inclusive_median_ms": (
                    statistics.median(gr_setup) if gr_setup else ""
                ),
                "spine_setup_inclusive_median_ms": (
                    statistics.median(spine_setup) if spine_setup else ""
                ),
                "setup_speedup_median": (
                    statistics.median(setup_speedups)
                    if setup_speedups
                    else ""
                ),
                "winner": "Spine" if (
                    statistics.median(device_speedups)
                    if device_speedups
                    else median_speedup
                ) > 1.0 else "G+R",
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
    parser.add_argument("--skip-rejected", action="store_true")
    parser.add_argument("--require-samples", type=int, default=1)
    args = parser.parse_args()

    samples = []
    for path in args.summary:
        samples.extend(
            load_summary(path.resolve(), skip_rejected=args.skip_rejected)
        )
    rows = aggregate(samples)
    undersampled = [
        f"{row['algorithm']}:{row['case']}={row['samples']}"
        for row in rows
        if int(row["samples"]) < args.require_samples
    ]
    if undersampled:
        raise ValueError(
            "matched FPGA groups do not meet --require-samples: " +
            ", ".join(undersampled)
        )
    write_tsv(args.output, rows)
    print(
        "MATCHED_FPGA_REPEAT_AGGREGATION_PASS "
        f"summaries={len(args.summary)} groups={len(rows)} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
