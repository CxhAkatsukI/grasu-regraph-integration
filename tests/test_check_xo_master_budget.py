from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.check_xo_master_budget import master_interfaces


class XoMasterBudgetTests(unittest.TestCase):
    def test_counts_only_axi_memory_masters(self) -> None:
        metadata = {
            "Interfaces": {
                "m_axi_a": {"type": "axi4", "mode": "master"},
                "m_axi_b": {"type": "axi4full", "mode": "master"},
                "interrupt": {"type": "interrupt", "mode": "master"},
                "s_axi_control": {"type": "axi4lite", "mode": "slave"},
                "axis_out": {"type": "axis", "mode": "write_only"},
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            xo = Path(temporary) / "kernel.xo"
            with zipfile.ZipFile(xo, "w") as archive:
                archive.writestr("kernel/kernel.json", json.dumps(metadata))
            self.assertEqual(master_interfaces(xo), ["m_axi_a", "m_axi_b"])

    def test_rejects_ambiguous_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            xo = Path(temporary) / "kernel.xo"
            with zipfile.ZipFile(xo, "w") as archive:
                archive.writestr("a/kernel.json", "{}")
                archive.writestr("b/kernel.json", "{}")
            with self.assertRaisesRegex(ValueError, "expected one kernel.json"):
                master_interfaces(xo)


if __name__ == "__main__":
    unittest.main()
