from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.check_pipeline_master_budget import project_master_count


MASTER_COUNTS = {
    "bin_search": 2,
    "dispatch_degree": 0,
    "process_cache": 1,
    "process_ddr": 2,
    "grasu_degree_update": 1,
    "regraph_pagerank_source_prepare": 4,
    "pma_to_regraph_adapter": 4,
    "lksg_stream": 0,
    "kernelLittleGSMerger": 0,
    "regraph_pagerank_apply": 2,
    "kernelHBMWrapper": 2,
    "regraph_frontend_mux": 0,
}


def write_xo(path: Path, master_count: int) -> None:
    interfaces = {
        f"m_axi_gmem{index}": {"type": "axi4", "mode": "master"}
        for index in range(master_count)
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "kernel/kernel.json", json.dumps({"Interfaces": interfaces})
        )


class PipelineMasterBudgetTests(unittest.TestCase):
    def test_full_pagerank_k1_and_k2_master_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build_dir = Path(temporary)
            for kernel, count in MASTER_COUNTS.items():
                write_xo(build_dir / f"{kernel}.hw.xo", count)

            k1, breakdown = project_master_count(build_dir, 1)
            k2, _ = project_master_count(build_dir, 2)

            self.assertEqual(k1, 27)
            self.assertEqual(k2, 35)
            self.assertEqual(
                breakdown["pma_to_regraph_adapter"]["master_instances"], 4
            )

    def test_rejects_non_positive_pipeline_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be positive"):
            project_master_count(Path("unused"), 0)

    def test_sharded_k4_residual_pagerank_fits_u55c_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build_dir = Path(temporary)
            sharded_counts = dict(MASTER_COUNTS)
            sharded_counts["process_ddr"] = 4
            sharded_counts["regraph_pagerank_source_prepare"] = 5
            sharded_counts["pma_to_regraph_adapter"] = 1
            sharded_counts["regraph_pagerank_apply"] = 3
            for kernel, count in sharded_counts.items():
                write_xo(build_dir / f"{kernel}.hw.xo", count)

            total, breakdown = project_master_count(
                build_dir, 4, pipeline_mode="sharded-k4"
            )

            self.assertEqual(total, 33)
            self.assertEqual(
                breakdown["kernelHBMWrapper"]["masters_per_compute_unit"], 2
            )
            self.assertEqual(
                breakdown["pma_to_regraph_adapter"]["master_instances"], 4
            )


if __name__ == "__main__":
    unittest.main()
