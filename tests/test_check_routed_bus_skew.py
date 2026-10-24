import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("bus_skew", Path(__file__).resolve().parents[1] /
                                              "scripts/check_routed_bus_skew.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    return """| Tool Version      : Vivado v.2024.1 (lin64)
| Command           : report_bus_skew -file /tmp/bus_skew.rpt -warn_on_violation
| Design State      : Routed
1. Bus Skew Report Summary
--------------------------
Id  Position  From  To  Corner  Requirement(ns)  Actual(ns)  Slack(ns)
--  --------  ----  --  ------  ---------------  ----------  ---------
1   307       [get_cells {long source}]
              [get_cells {long destination}]
                       Slow 20.000 0.436 19.564
2   309       [get_cells {other source}] [get_cells {destination}] Fast 2.222 -0.253 2.475
2. Bus Skew Report Per Constraint
----------------------------------
"""


class BusSkewReportTest(unittest.TestCase):
    def test_multiline_summary_and_negative_actual_skew(self):
        result = MODULE.parse_report(fixture())
        self.assertEqual(result["constraints"], 2)
        self.assertEqual(result["min_slack_ns"], 2.475)
        self.assertEqual(result["design_state"], "Routed")
        self.assertEqual(MODULE.parse_report(fixture().replace("Routed", "Physopt postRoute"))[
            "constraints"], 2)

    def test_unmeasured_constraints_require_review_not_automatic_acceptance(self):
        result = MODULE.parse_report(fixture().replace(
            "Fast 2.222 -0.253 2.475", "NA 2.222 NA NA"))
        self.assertEqual(result["status"], "ROUTED_BUS_SKEW_REVIEW_REQUIRED")
        self.assertEqual(result["constraints"], 2)
        self.assertEqual(result["measured_constraints"], 1)
        self.assertEqual(result["unmeasured"][0]["id"], 2)

    def test_fail_closed(self):
        for before, after in (
            ("2024.1", "2024.2"), ("Routed", "Fully Placed"),
            ("-warn_on_violation", "-setup"),
            ("-warn_on_violation", "-cells subset"),
            ("20.000 0.436 19.564", "20.000 20.436 -0.436"),
            ("20.000 0.436 19.564", "20.000 0.436 nan"),
            ("20.000 0.436 19.564", "20.000 inf 0.000"),
            ("20.000 0.436 19.564", "20.000 0.436 19.000"),
            ("2   309", "3   309"), ("2   309", "1   309"),
            ("Fast 2.222 -0.253 2.475", "Fast incomplete"),
            ("2. Bus Skew Report Per Constraint", ""),
            ("Requirement(ns)", "Unexpected(ns)"),
        ):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                MODULE.parse_report(fixture().replace(before, after))
        for text in ("", fixture().split("1   307")[0]):
            with self.assertRaises(ValueError):
                MODULE.parse_report(text)


if __name__ == "__main__":
    unittest.main()
