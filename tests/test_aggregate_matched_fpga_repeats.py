from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from scripts.aggregate_matched_fpga_repeats import aggregate, load_summary


FIELDNAMES = [
    "case",
    "algorithm",
    "graph",
    "gr_status",
    "spine_status",
    "comparison_status",
    "gr_event_e2e_ms",
    "spine_dynamic_kernel_ms",
    "kernel_speedup_gr_over_spine",
]


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def row(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "case": "amazon_insert",
        "algorithm": "weighted_sssp",
        "graph": "/tmp/amazon.graph",
        "gr_status": "PASS",
        "spine_status": "PASS",
        "comparison_status": "ADMITTED",
        "gr_event_e2e_ms": 2.0,
        "spine_dynamic_kernel_ms": 1.0,
        "kernel_speedup_gr_over_spine": 2.0,
    }
    result.update(overrides)
    return result


class MatchedFpgaRepeatAggregationTests(unittest.TestCase):
    def test_aggregate_reports_medians_ranges_and_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.tsv"
            second = root / "second.tsv"
            third = root / "third.tsv"
            write_summary(first, [row()])
            write_summary(
                second,
                [
                    row(
                        gr_event_e2e_ms=2.2,
                        spine_dynamic_kernel_ms=1.1,
                        kernel_speedup_gr_over_spine=2.1,
                    )
                ],
            )
            write_summary(
                third,
                [
                    row(
                        gr_event_e2e_ms=1.8,
                        spine_dynamic_kernel_ms=0.9,
                        kernel_speedup_gr_over_spine=1.9,
                    )
                ],
            )
            samples = [
                *load_summary(first),
                *load_summary(second),
                *load_summary(third),
            ]
            result = aggregate(samples)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["samples"], 3)
            self.assertEqual(result[0]["gr_event_e2e_median_ms"], 2.0)
            self.assertEqual(
                result[0]["spine_dynamic_kernel_median_ms"], 1.0
            )
            self.assertEqual(
                result[0]["kernel_speedup_gr_over_spine_median"], 2.0
            )
            self.assertEqual(result[0]["kernel_speedup_min"], 1.9)
            self.assertEqual(result[0]["kernel_speedup_max"], 2.1)
            self.assertEqual(result[0]["winner"], "Spine")

    def test_non_admitted_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.tsv"
            write_summary(path, [row(comparison_status="REJECTED")])
            with self.assertRaisesRegex(ValueError, "non-admitted"):
                load_summary(path)

    def test_graph_change_across_repeats_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.tsv"
            second = root / "second.tsv"
            write_summary(first, [row(graph="/tmp/one.graph")])
            write_summary(second, [row(graph="/tmp/two.graph")])
            with self.assertRaisesRegex(ValueError, "graph identity changed"):
                aggregate([*load_summary(first), *load_summary(second)])


if __name__ == "__main__":
    unittest.main()
