#!/usr/bin/env python3

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_matched_fpga_matrix import summarize  # noqa: E402


class MatchedFpgaSummaryTest(unittest.TestCase):
    def test_admits_only_two_correct_timing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            matrix = root / "matrix.tsv"
            with matrix.open("w", newline="") as sink:
                writer = csv.DictWriter(
                    sink,
                    fieldnames=("case", "algorithm", "graph", "source", "gr_host", "gr_xclbin"),
                    delimiter="\t",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case": "row0",
                        "algorithm": "weighted_sssp",
                        "graph": "/tmp/g.graph",
                        "source": "0",
                        "gr_host": "/tmp/gr-host",
                        "gr_xclbin": "/tmp/gr.xclbin",
                    }
                )
            gr = root / "row0" / "grasu_regraph"
            spine = root / "row0" / "spine" / "sssp"
            gr.mkdir(parents=True)
            spine.mkdir(parents=True)
            (gr / "run.log").write_text(
                "WEIGHTED_PMA_NATIVE_TIMING event_e2e_ms=8 setup_inclusive_ms=10\n"
                "WEIGHTED_PMA_NATIVE_RESULT status=PASS mismatches=0 conversion_cost=absent\n"
            )
            (spine / "dynamic_row0.log").write_text(
                "SPINE_DYNAMIC_MAINT_PASS\n"
                "ALGORITHM_PASS name=weighted_sssp\n"
                "PARTITIONED_ALGORITHM_PASS algorithm=weighted_sssp\n"
                "SPINE_HW_TIMING dynamic_kernel_ms=2 dynamic_setup_inclusive_ms=5\n"
            )

            rows = summarize(matrix, root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["comparison_status"], "ADMITTED")
            self.assertEqual(rows[0]["kernel_speedup_gr_over_spine"], "4.000000")
            self.assertEqual(rows[0]["setup_speedup_gr_over_spine"], "2.000000")

    def test_rejects_missing_correctness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            matrix = root / "matrix.tsv"
            matrix.write_text(
                "case\talgorithm\tgraph\tsource\tgr_host\tgr_xclbin\n"
                "bad\tweighted_sssp\t/tmp/g\t0\t/tmp/h\t/tmp/x\n"
            )
            gr = root / "bad" / "grasu_regraph"
            gr.mkdir(parents=True)
            (gr / "run.log").write_text(
                "WEIGHTED_PMA_NATIVE_TIMING event_e2e_ms=8\n"
                "WEIGHTED_PMA_NATIVE_RESULT status=FAIL conversion_cost=absent\n"
            )
            rows = summarize(matrix, root)
            self.assertEqual(rows[0]["comparison_status"], "REJECTED")
            self.assertEqual(rows[0]["kernel_speedup_gr_over_spine"], "")


if __name__ == "__main__":
    unittest.main()
