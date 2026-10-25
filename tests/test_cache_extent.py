"""Bounded-cache gates must reject unrelated ABI and result changes."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from validation.cache_extent import abi, matrix, matrix_inputs, route, study
from validation.grasu_complete import analysis


def legacy():
    return {"protocol": "ap_ctrl_chain", "arguments": [{"name": "memory"}, {"name": "stream"}],
        "ports": {"S_AXI_CONTROL": {"range": "0x1C"}, "m_axi": {"dataWidth": "512"}},
        "registers": {"CTRL": {"addressOffset": "0", "size": "32", "access": "read-write"}},
        "wires": {name: {"left": "4", "right": "0", "direction": "in"}
                  for name in ("s_axi_control_ARADDR", "s_axi_control_AWADDR")},
        "buses": {"m_axi": [("ARADDR", "m_axi_ARADDR")]}}


def bounded(prior):
    result = copy.deepcopy(prior)
    result["arguments"].append({"name": "valid_segments", "addressQualifier": "0", "id": "2",
        "port": "S_AXI_CONTROL", "size": "0x4", "offset": "0x1C", "hostOffset": "0x0",
        "hostSize": "0x4", "type": "unsigned int"})
    result["ports"]["S_AXI_CONTROL"]["range"] = "0x24"
    result["registers"]["valid_segments"] = {"addressOffset": "28", "size": "32", "access": "write-only"}
    for wire in result["wires"].values():
        wire["left"] = "5"
    return result


class CacheExtentTests(unittest.TestCase):
    def compare(self, candidate, reference):
        with patch.object(abi, "snapshot", side_effect=[candidate, reference]):
            return abi.compare({}, {})

    def test_only_scalar_and_control_aperture_may_change(self):
        prior = legacy()
        self.assertEqual(self.compare(bounded(prior), copy.deepcopy(prior))["status"], "CACHE_EXTENT_ABI_PASS")
        for mutation in ("offset", "port", "bus", "register", "protocol"):
            candidate = bounded(prior)
            if mutation == "offset":
                candidate["arguments"][-1]["offset"] = "0x20"
            elif mutation == "port":
                candidate["ports"]["m_axi"]["dataWidth"] = "256"
            elif mutation == "bus":
                candidate["buses"]["m_axi"] = []
            elif mutation == "register":
                candidate["registers"]["CTRL"]["size"] = "64"
            else:
                candidate["protocol"] = "ap_ctrl_hs"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.compare(candidate, copy.deepcopy(prior))

    def test_link_output_isolation_requires_exact_complete_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "input.cfg"
            keys = ("messageDb", "temp_dir", "report_dir", "log_dir", "remote_ip_cache")
            original.write_text("\n".join(key + "=/old/" + key for key in keys) + "\n[connectivity]\nnk=cache:1\n")
            output = route.isolate_config(original, root).read_text()
            self.assertNotIn("/old/", output)
            self.assertIn("nk=cache:1", output)
            for text in ("\n".join(key + "=old" for key in keys[:-1]), original.read_text() + "temp_dir=duplicate\n"):
                original.write_text(text)
                with self.assertRaises(ValueError):
                    route.isolate_config(original, root)

    def test_finite_caps_zero_swap_and_group_oom_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {"memory.max": str(64 * route.GIB), "memory.high": str(56 * route.GIB),
                      "memory.swap.max": "0", "memory.oom.group": "1"}
            for key, value in values.items():
                (root / key).write_text(value)
            route.verify(root, memory_gib=64)
            for budget in (48, 56, 64):
                (root / "memory.max").write_text(str(budget * route.GIB))
                (root / "memory.high").write_text(str((budget - 4) * route.GIB))
                route.verify(root, memory_gib=budget)
            for key, value in values.items():
                (root / key).write_text(value)
            for key, invalid in (("memory.max", "max"), ("memory.high", values["memory.max"]),
                                 ("memory.swap.max", "1"), ("memory.oom.group", "0")):
                (root / key).write_text(invalid)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    route.verify(root, memory_gib=64)
                (root / key).write_text(values[key])

    def test_small_source_stage_accepts_large_bounded_peers_without_changing_own_bounds(self):
        class BoundsReached(Exception):
            pass

        def check_stage(stage):
            self.assertEqual(stage, "source")
            self.assertIs(study.concurrent.verify, route.verify)
            raise BoundsReached

        with patch.object(study.concurrent, "verify"), \
                patch.object(study.runtime, "bounds", side_effect=check_stage) as own_bounds:
            with self.assertRaises(BoundsReached):
                study.run(SimpleNamespace(stage="source"))
            own_bounds.assert_called_once_with("source")

    def test_source_and_hls_keep_exact_small_stage_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(study.runtime, "current", return_value=root), \
                    patch.object(study.runtime, "Lease"):
                for stage, cap, high in (("source", route.GIB, 768 * 1024**2),
                                         ("hls", 8 * route.GIB, 7 * route.GIB)):
                    values = {"memory.max": str(cap), "memory.high": str(high),
                              "memory.swap.max": "0", "memory.oom.group": "1"}
                    for key, value in values.items():
                        (root / key).write_text(value)
                    self.assertEqual(study.runtime.bounds(stage)[2]["tree_memory_gib"], cap // route.GIB)
                    (root / "memory.max").write_text(str(2 * cap))
                    with self.subTest(stage=stage), self.assertRaises(ValueError):
                        study.runtime.bounds(stage)

    def test_bounded_functional_rows_cannot_be_replaced_by_legacy_success(self):
        for variant in ("cache-token", "cache-plain"):
            token = int(variant == "cache-token")
            rows = [(count, conflict, 131072) for count, conflict in analysis.CACHE_ROWS]
            rows += [(0, 0, 0)]
            rows += [(64, conflict, extent) for extent in (1, 15, 16, 17, 131071, 131072)
                     for conflict in (1, 0)]
            rows += [(16, 1, extent) for extent in (1, 131072)]
            text = "".join(f"PRODUCTION_CACHE_PASS updates={count} conflict={conflict} "
                f"capacity=131072 token={token} valid_segments={extent}\n"
                for count, conflict, extent in rows)
            self.assertEqual(len(analysis.bounded_functional(text, variant)), 21)
            for invalid in (text + text, text.replace("capacity=131072", "capacity=16"), ""):
                with self.assertRaises(ValueError):
                    analysis.bounded_functional(invalid, variant)

    def test_matrix_requires_every_algorithm_dataset_once(self):
        rows = [{"algorithm": algorithm, "dataset": dataset, "batch_size": 8, "updates": 8}
                for algorithm in matrix_inputs.ALGORITHMS.values() for dataset in matrix_inputs.DATASETS]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workloads.json"
            path.write_text(json.dumps({"records": list(reversed(rows))}))
            ordered = matrix_inputs.workloads(path)
            self.assertEqual(len(ordered), 24)
            self.assertEqual(ordered[0]["dataset"], "AU")
            for invalid in (rows[:-1], rows + rows[:1], [{**row, "batch_size": 1} for row in rows]):
                path.write_text(json.dumps({"records": invalid}))
                with self.assertRaises(ValueError):
                    matrix_inputs.workloads(path)

    def test_missing_or_failed_route_never_selects_old_hardware(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {"build_root": str(root)}
            self.assertEqual(matrix.artifacts(plan, "sssp"), ("waiting", {}, []))
            path = root / "route-v1/sssp/results.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"status": "FAILED_RETAINED"}))
            self.assertEqual(matrix.artifacts(plan, "sssp"), ("failed", {}, []))
            path.write_text(json.dumps({"status": "ROUTED_NOT_BOARD_TESTED"}))
            manifest = path.with_name("manifest.json")
            manifest.write_text(json.dumps({"abi": {"status": "LEGACY_ONLY"}}))
            with self.assertRaises(ValueError):
                matrix.artifacts(plan, "sssp")

    def test_matrix_summary_preserves_missing_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = {"cases": [{"algorithm": "cc", "dataset": "SO", "status": "BLOCKED_BY_FAILED_BUILD"}]}
            matrix.summarize(root, report)
            self.assertEqual(report["passed_cases"], 0)
            self.assertIn("BLOCKED_BY_FAILED_BUILD", (root / "summary.csv").read_text())

    def test_new_attempt_waits_for_its_own_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "route-v1/sssp/results.json"
            old.parent.mkdir(parents=True)
            old.write_text(json.dumps({"status": "ROUTED_NOT_BOARD_TESTED"}))
            plan = {"build_root": str(root), "route_directory": "route-v2",
                    "spine_directory": "spine-respr-v2"}
            self.assertEqual(matrix.artifacts(plan, "sssp"), ("waiting", {}, []))
            new = root / "route-v2/sssp/results.json"
            new.parent.mkdir(parents=True)
            new.write_text(json.dumps({"status": "FAILED_RETAINED"}))
            self.assertEqual(matrix.artifacts(plan, "sssp"), ("failed", {}, []))


if __name__ == "__main__":
    unittest.main()
