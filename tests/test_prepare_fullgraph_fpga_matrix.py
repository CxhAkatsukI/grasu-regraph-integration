#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class FullGraphMatrixPreparationTest(unittest.TestCase):
    def test_binds_complete_three_algorithm_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host_root = root / "hosts"
            records = []
            host_names = {
                "weighted_sssp": "weighted_sssp/sharded_k4_sssp_native_host",
                "connected_components": "connected_components/sharded_k4_cc_native_host",
                "residual_pagerank": (
                    "residual_pagerank/sharded_k4_residual_pagerank_native_host"
                ),
            }
            xclbins = {}
            for algorithm, host_name in host_names.items():
                host = host_root / host_name
                host.parent.mkdir(parents=True, exist_ok=True)
                host.touch()
                xclbin = root / f"{algorithm}.xclbin"
                xclbin.touch()
                xclbins[algorithm] = xclbin
                graph = root / f"AU_{algorithm}.graph"
                graph.touch()
                records.append(
                    {
                        "dataset": "AU",
                        "algorithm": algorithm,
                        "graph": str(graph),
                        "source": 11 if algorithm == "weighted_sssp" else 0,
                    }
                )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"status": "pass", "records": records}),
                encoding="utf-8",
            )
            output = root / "matrix.tsv"
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/prepare_fullgraph_fpga_matrix.py"),
                    "--workload-manifest",
                    str(manifest),
                    "--host-root",
                    str(host_root),
                    "--sssp-xclbin",
                    str(xclbins["weighted_sssp"]),
                    "--cc-xclbin",
                    str(xclbins["connected_components"]),
                    "--respr-xclbin",
                    str(xclbins["residual_pagerank"]),
                    "--output",
                    str(output),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("rows=3", result.stdout)
            rows = output.read_text().splitlines()
            self.assertEqual(len(rows), 4)
            self.assertIn("\t11\t", rows[1])

    def test_rejects_missing_xclbin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text('{"status":"pass","records":[]}')
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/prepare_fullgraph_fpga_matrix.py"),
                    "--workload-manifest",
                    str(manifest),
                    "--host-root",
                    str(root),
                    "--sssp-xclbin",
                    str(root / "missing"),
                    "--cc-xclbin",
                    str(root / "missing"),
                    "--respr-xclbin",
                    str(root / "missing"),
                    "--output",
                    str(root / "matrix.tsv"),
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing SSSP xclbin", result.stderr)


if __name__ == "__main__":
    unittest.main()
