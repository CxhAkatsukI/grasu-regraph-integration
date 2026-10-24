"""A passing caption cannot hide negative, missing or malformed timing values."""
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_routed_timing_summary.py"
SPEC = importlib.util.spec_from_file_location("timing_check", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
TEXT = """| Tool Version : Vivado v.2024.1 (lin64)
| Design State : Routed
| Design Timing Summary
-----------------------
    WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints
    ------- ------- ------- ------- ------- ------- ------- ------- ------- ------- ------- -------
    0.050 0.000 0 100 0.006 0.000 0 100 0.000 0.000 0 50

All user specified timing constraints are met.
| Clock Summary
-----------------------
"""


class RoutedTimingTests(unittest.TestCase):
    def test_complete_pass_and_physopt_state(self):
        for state in ("Routed", "Physopt postRoute"):
            result = CHECK.parse_report(TEXT.replace("Routed", state))
            self.assertTrue(result["status"].startswith("ROUTED_TIMING_PASS"))
            self.assertEqual(result["values"]["setup_total"], 100)

    def test_negative_slack_or_nonzero_failure_rejects_pass_caption(self):
        for before, after in (("0.050", "-0.001"), ("0.006", "-0.001"),
                              ("0.000 0 100", "0.000 1 100"),
                              ("0.000 0 50", "-0.001 1 50")):
            with self.subTest(after=after):
                self.assertEqual(CHECK.parse_report(TEXT.replace(before, after))["status"],
                                 "ROUTED_TIMING_FAILED")

    def test_missing_pass_caption_or_conflicting_caption_rejects(self):
        for text in (TEXT.replace("All user specified timing constraints are met.", ""),
                     TEXT.replace("| Clock Summary", "Timing constraints are not met.\n| Clock Summary")):
            self.assertEqual(CHECK.parse_report(text)["status"], "ROUTED_TIMING_FAILED")

    def test_bad_version_state_incomplete_duplicate_and_nonfinite_reject(self):
        invalid = (TEXT.replace("2024.1", "2025.1"), TEXT.replace("Routed", "Placed"),
                   TEXT.replace("| Clock Summary", ""), TEXT + "| Design Timing Summary\n",
                   TEXT.replace("0.050", "nan"), TEXT.replace("0.050", "inf"),
                   TEXT.replace("0 100", "0.5 100"), TEXT.replace("0 100", "0 0"),
                   TEXT.replace("0 50", "0"))
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                CHECK.parse_report(text)


if __name__ == "__main__":
    unittest.main()
