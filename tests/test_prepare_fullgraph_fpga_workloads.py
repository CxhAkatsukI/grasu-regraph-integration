#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class FullGraphWorkloadPreparationTest(unittest.TestCase):
    def test_materializes_and_reuses_algorithm_specific_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source" / "sx_askubuntu"
            source.mkdir(parents=True)

            def write_slice(path: Path, rows: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# vertices=4\n" + rows, encoding="ascii")

            directed = source / "directed.slice"
            reciprocal = source / "reciprocal.slice"
            residual = source / "residual.slice"
            directed_update = source / "directed_u8.slice"
            reciprocal_update = source / "reciprocal_u8.slice"
            residual_update = source / "residual_u8.slice"
            write_slice(directed, "0 1 2 1\n")
            write_slice(reciprocal, "0 1 1 1\n1 0 1 1\n")
            write_slice(residual, "0 1 2 1\n1 1 1 1\n")
            write_slice(directed_update, "1 2 3 1\n")
            write_slice(reciprocal_update, "1 2 1 1\n2 1 1 1\n")
            write_slice(residual_update, "1 2 3 1\n")
            manifest = {
                "status": "pass",
                "graphs": {
                    "directed": {"path": str(directed)},
                    "reciprocal": {"path": str(reciprocal)},
                    "residual_sink_free": {"path": str(residual)},
                },
                "updates": [
                    {
                        "scenario": "insert",
                        "projection": "directed",
                        "user_mutations": 8,
                        "path": str(directed_update),
                    },
                    {
                        "scenario": "insert",
                        "projection": "reciprocal",
                        "user_mutations": 8,
                        "path": str(reciprocal_update),
                    },
                    {
                        "scenario": "insert",
                        "projection": "residual_sink_free",
                        "user_mutations": 8,
                        "path": str(residual_update),
                    },
                ],
            }
            (source / "materialization_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            output = root / "output"
            command = [
                "python3",
                str(ROOT / "scripts/prepare_fullgraph_fpga_workloads.py"),
                "--materialization-root",
                str(root / "source"),
                "--out-dir",
                str(output),
                "--datasets",
                "AU",
            ]
            first = subprocess.run(command, check=True, text=True, capture_output=True)
            second = subprocess.run(command, check=True, text=True, capture_output=True)
            self.assertIn("records=3", first.stdout)
            self.assertIn("reused=1", second.stdout)
            aggregate = json.loads((output / "manifest.json").read_text())
            self.assertEqual(len(aggregate["records"]), 3)
            self.assertEqual(
                {record["algorithm"] for record in aggregate["records"]},
                {
                    "weighted_sssp",
                    "connected_components",
                    "residual_pagerank",
                },
            )


if __name__ == "__main__":
    unittest.main()
