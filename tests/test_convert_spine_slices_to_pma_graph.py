#!/usr/bin/env python3

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from convert_spine_slices_to_pma_graph import convert  # noqa: E402


class SliceConversionTest(unittest.TestCase):
    def test_preserves_weighted_insert_delete_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            initial = root / "initial.slice"
            update = root / "update.slice"
            output = root / "case.graph"
            metadata = root / "case.json"
            initial.write_text(
                "# vertices=4\n# columns=src dst weight diff\n0 1 7 1\n2 3 9 1\n"
            )
            update.write_text(
                "# vertices=4\n# columns=src dst weight diff\n0 1 7 -1\n0 1 3 1\n"
            )
            manifest = convert(initial, update, output, metadata)
            self.assertEqual(
                output.read_text(),
                "4 2 2\n0 1 7\n2 3 9\n0 1 7 0\n0 1 3 1\n",
            )
            self.assertEqual(manifest["updates"], 2)
            self.assertTrue(metadata.is_file())

    def test_rejects_vertex_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            initial = root / "initial.slice"
            update = root / "update.slice"
            initial.write_text("# vertices=4\n0 1 1 1\n")
            update.write_text("# vertices=5\n0 1 1 1\n")
            with self.assertRaisesRegex(ValueError, "different vertex counts"):
                convert(initial, update, root / "x.graph", root / "x.json")

    def test_reciprocal_mode_mirrors_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            initial = root / "initial.slice"
            update = root / "update.slice"
            output = root / "case.graph"
            initial.write_text(
                "# vertices=3\n0 1 2 1\n1 0 2 1\n2 2 4 1\n"
            )
            update.write_text("# vertices=3\n0 2 3 1\n")
            manifest = convert(
                initial,
                update,
                output,
                root / "case.json",
                reciprocal=True,
            )
            self.assertEqual(
                output.read_text(),
                "3 3 2\n0 1 2\n1 0 2\n2 2 4\n0 2 3 1\n2 0 3 1\n",
            )
            self.assertTrue(manifest["reciprocal_expansion"])


if __name__ == "__main__":
    unittest.main()
