"""Case-local hashing retains the current input and every non-workload pin."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.cache_extent import host_matrix


class HostMatrixTest(unittest.TestCase):
    def fixture(self):
        pins = [{"path": path, "sha256": path} for path in ("a.graph", "b.graph", "source", "host")]
        plan = {"workloads": [{"graph": name} for name in ("a.graph", "b.graph")],
                "pins": pins + [pins[0]], "unchanged": {"boundary": "resident"}}
        row = {"workload": plan["workloads"][0]}
        return plan, row

    def test_only_unused_workload_pins_removed_parent_not_mutated(self):
        plan, row = self.fixture()
        before = copy.deepcopy(plan)
        extra = [{"path": "parent-plan", "sha256": "frozen"}, plan["pins"][0]]
        scoped = host_matrix.case_plan(plan, row, extra)
        self.assertEqual([pin["path"] for pin in scoped["pins"]],
                         ["a.graph", "source", "host", "parent-plan"])
        self.assertEqual(scoped["workloads"], plan["workloads"])
        self.assertEqual(scoped["unchanged"], plan["unchanged"])
        self.assertEqual(plan, before)

    def test_missing_selected_input_and_conflicting_pin_rejected(self):
        for kind in ("not-workload", "not-pinned", "conflict"):
            with self.subTest(kind=kind):
                plan, row = self.fixture()
                extra = []
                if kind == "not-workload":
                    row = {"workload": {"graph": "unknown"}}
                elif kind == "not-pinned":
                    plan["pins"] = [pin for pin in plan["pins"] if pin["path"] != "a.graph"]
                else:
                    extra = [{"path": "host", "sha256": "modified"}]
                with self.assertRaises(ValueError):
                    host_matrix.case_plan(plan, row, extra)

    def test_optional_size_does_not_change_identical_hash_identity(self):
        plan, row = self.fixture()
        plan["pins"][0]["size"] = 123
        scoped = host_matrix.case_plan(plan, row, [{"path": "a.graph", "sha256": "a.graph"}])
        self.assertEqual(scoped["pins"][0], {"path": "a.graph", "sha256": "a.graph", "size": 123})
        with self.assertRaisesRegex(ValueError, "conflicting evidence pins"):
            host_matrix.case_plan(plan, row, [{"path": "a.graph", "sha256": "a.graph", "size": 124}])

    def test_full_runner_checks_parent_twice_and_preserves_failed_au_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, _ = self.fixture()
            plan.update(boundary=host_matrix.BOUNDARY,
                        repeats={"warmup_pairs": 1, "measured_pairs": 3})
            plan["workloads"] = [{"algorithm": algorithm, "dataset": dataset, "graph": "a.graph"}
                for algorithm in host_matrix.inputs.ALGORITHMS.values()
                for dataset in host_matrix.inputs.DATASETS]
            path = root / "plan.json"
            path.write_text(json.dumps(plan))

            def measured(scoped, row, bits, pins, output):
                row["status"] = "FAILED_RETAINED" if row["algorithm"] == "cc" else "RESIDENT_PAIR_PASS"

            with patch.object(host_matrix.inputs, "unchanged") as checked, \
                    patch.object(host_matrix.matrix, "artifacts", return_value=("ready", {}, [])), \
                    patch.object(host_matrix.matrix, "measure", side_effect=measured) as measure:
                report = host_matrix.run(path, root / "results")
            self.assertEqual(checked.call_count, 2)
            self.assertEqual(checked.call_args_list[0].args[0], plan["pins"])
            self.assertEqual(checked.call_args_list[1].args[0][:len(plan["pins"])], plan["pins"])
            self.assertEqual(report["status"], "FPGA_MATRIX_INCOMPLETE_RETAINED")
            self.assertEqual(report["passed_cases"], 16)
            self.assertEqual(measure.call_count, 17)
            cc = [row for row in report["cases"] if row["algorithm"] == "cc"]
            self.assertEqual(cc[0]["status"], "FAILED_RETAINED")
            self.assertTrue(all(row["status"] == "BLOCKED_BY_FAILED_AU_GATE" for row in cc[1:]))


if __name__ == "__main__":
    unittest.main()
