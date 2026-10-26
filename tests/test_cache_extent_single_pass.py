"""Single-pass delivery keeps raw observations, rather than median fields."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from validation.cache_extent.single_pass import inherited_pins, recover_unstarted, save
from validation.cache_extent import board_memory


class SinglePassTests(unittest.TestCase):
    def test_only_stopped_unexecuted_admission_can_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            destination = output / "cc-r19"
            destination.mkdir()
            captured = {"status": "WAITING_FOR_FREE_BOARD_AND_MEMORY", "samples": [], "board_tested": False}
            (destination / "results.json").write_text(json.dumps(captured))
            for suffix in (".json", ".driver.log"):
                (output / ("cc-r19" + suffix)).write_text("{}")
            row = {"algorithm": "cc", "dataset": "R19", "status": "RUNNING"}
            report = {"cases": [row]}
            with patch("validation.cache_extent.single_pass.subprocess.run", return_value=Mock(returncode=0)):
                with self.assertRaisesRegex(ValueError, "possibly executed"):
                    recover_unstarted(output, report)
            (destination / "sample-1").mkdir()
            with patch("validation.cache_extent.single_pass.subprocess.run", return_value=Mock(returncode=3)):
                with self.assertRaisesRegex(ValueError, "possibly executed"):
                    recover_unstarted(output, report)
                (destination / "sample-1").rmdir()
                recover_unstarted(output, report)
            self.assertEqual(report["cases"], [])
            self.assertTrue((output / "admission-interruptions/cc-r19/cc-r19/results.json").exists())
            self.assertEqual(len(report["admission_interruptions"]), 1)

    def test_board_admission_retains_bounded_peers_and_records_unbounded(self):
        lease = Mock(own=Path("/own"))
        lease.sample.return_value = {"admitted": True}
        policy = {"reserve_gib": 64, "allow_observed_unbounded_builds": True}
        records = [{"pid": 11, "bounded": False, "reason": "unbounded"},
                   {"pids": [22], "bounded": True, "memory_max_bytes": 1024}]
        with patch.object(board_memory.admission, "reservations", return_value=records):
            result = board_memory.sample(lease, 1000, ["11 v++", "22 vivado"], policy)
        lease.sample.assert_called_once_with(1000, ["22 vivado"], policy, commit=True)
        self.assertFalse(result["external_growth_hard_bounded"])
        self.assertEqual(result["unbounded_background_observed"], records[:1])
        with self.assertRaises(ValueError):
            board_memory.sample(lease, 1000, [], dict(policy, reserve_gib=24))

    def test_prior_execution_manifest_supplies_missing_config_pin(self):
        pins = [{"path": name, "sha256": "hash-" + name}
                for name in ("graph", "gr_binary", "spine_binary", "spine_host")]
        config = {pin["path"]: pin["path"] for pin in pins}
        config["expected_pins"] = pins[:2]
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path(temporary)
            (previous / "cc-au").mkdir()
            manifest = previous / "cc-au" / "manifest.json"
            manifest.write_text(json.dumps({"pins": pins}))
            self.assertEqual(inherited_pins(previous, "cc-au", config), pins)
            config["expected_pins"] = [{"path": "graph", "sha256": "different"}]
            with self.assertRaisesRegex(ValueError, "conflicting"):
                inherited_pins(previous, "cc-au", config)

    def test_csv_preserves_the_one_pair_and_failure(self):
        report = {"cases": [
            {"algorithm": "sssp", "dataset": "AU", "status": "RESIDENT_PAIR_PASS",
             "summary": {"gr_wall_ms": 18.0, "spine_wall_ms": 6.0,
                         "speedup_gr_over_spine": 3.0, "gr_rounds": 2, "spine_rounds": 2}},
            {"algorithm": "cc", "dataset": "SU", "status": "FAILED_RETAINED"}]}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            save(output, report)
            with (output / "summary.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(report["passed_cases"], 1)
            self.assertEqual(rows[0]["gr_wall_ms"], "18.0")
            self.assertEqual(rows[0]["speedup_gr_over_spine"], "3.0")
            self.assertEqual(rows[1]["status"], "FAILED_RETAINED")
            self.assertEqual(rows[1]["speedup_gr_over_spine"], "")


if __name__ == "__main__":
    unittest.main()
