"""Recover wrapper-only failures without promoting compiler failures or stale files."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.cache_extent import spine_recovery as recovery
from validation.grasu_complete import preparation


def fixture(root):
    build = root / "build/respr"
    paths = {
        "build_provenance.json": json.dumps({"target": "hw", "git_dirty": False,
            "algorithm": "thresholded_residual_pagerank", "residual_sparse_apply": 1,
            "git_commit": "frozen", "host_memory_probe_sha256": "unused"}),
        "reports/link/imp/impl_1_hw_bb_locked_timing_summary_routed.rpt":
            "| Design Timing Summary\n -0.007 -0.014 3 100 0.009 0 0 100 0 0 0 100\n",
        "reports/link/imp/impl_1_bus_skew_routed.rpt": "bus skew report\n",
        "logs/link/vivado.log": "WARNING: [AUTO-FREQ-SCALING-07] scaled HBM clock\n",
        "xclbin/spine_partitioned_split_e2e.respr.hw.xclbin": "fixture-not-a-bitstream"}
    for name, text in paths.items():
        path = build / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    stdout = root / "raw/spine-respr-compile-route.stdout.txt"
    stdout.parent.mkdir()
    stdout.write_text("BUILD_PASS target=hw algorithm=thresholded_residual_pagerank root=" + str(build) + "\n")
    probe = root / "host_memory.py"
    probe.write_text("fixture")
    provenance = json.loads((build / "build_provenance.json").read_text())
    provenance["host_memory_probe_sha256"] = preparation.pin(probe)["sha256"]
    (build / "build_provenance.json").write_text(json.dumps(provenance))
    command = ["bash", str(root / "build_partitioned_algorithms.sh"), "hw", str(root / "build"), "respr"]
    manifest = {"pins": [preparation.pin(probe)], "command": command,
                "selector": "SPINE_RESIDUAL_SPARSE_APPLY=1", "source_commit": "frozen"}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return {"status": "FAILED_RETAINED", "board_tested": False,
            "error": "FileNotFoundError(2, 'No such file or directory')", "pins": [preparation.pin(probe)],
            "memory_events_after": "oom 0\noom_kill 0\noom_group_kill 0\n",
            "steps": [{"phase": "compile-route", "variant": "spine-respr", "command": command,
                       "exit_code": 0, "stop_reason": "process_exit", "cleanup_snapshot_error": None}]}


class RecoveryTests(unittest.TestCase):
    def test_exact_failure_is_auditable_without_mutating_source_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            path = root / "results.json"
            path.write_text(json.dumps(report))
            original = path.read_bytes()
            audit = recovery.validate(root)
            self.assertEqual(audit["timing"]["wns_ns"], -0.007)
            self.assertEqual(path.read_bytes(), original)
            self.assertIn(preparation.pin(path), audit["pins"])

    def test_other_failures_are_not_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = fixture(root)
            for mutation in ("status", "error", "exit", "stop", "cleanup", "command", "oom", "pin"):
                report = copy.deepcopy(original)
                if mutation == "status":
                    report["status"] = "RUNNING"
                elif mutation == "error":
                    report["error"] = "other error"
                elif mutation in ("exit", "stop", "cleanup", "command"):
                    key = {"exit": "exit_code", "stop": "stop_reason",
                           "cleanup": "cleanup_snapshot_error", "command": "command"}[mutation]
                    report["steps"][0][key] = {"exit": 1, "stop": "timeout", "cleanup": "failed",
                                              "command": ["bash", "other.sh"]}[mutation]
                elif mutation == "oom":
                    report["memory_events_after"] = "oom 1\noom_kill 0\noom_group_kill 0\n"
                else:
                    report["pins"][0]["sha256"] = "wrong"
                (root / "results.json").write_text(json.dumps(report))
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    recovery.validate(root)

    def test_missing_success_marker_and_changed_selector_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            (root / "results.json").write_text(json.dumps(report))
            stdout = root / "raw/spine-respr-compile-route.stdout.txt"
            stdout.write_text("compiler failed\n")
            with self.assertRaises(ValueError):
                recovery.validate(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["selector"] = "SPINE_RESIDUAL_SPARSE_APPLY=0"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                recovery.validate(root)

    def test_failed_binary_inspection_stays_failed_in_a_fresh_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            report = fixture(source)
            (source / "results.json").write_text(json.dumps(report))
            with patch.object(recovery, "clocks", side_effect=ValueError("invalid xclbin")):
                with self.assertRaises(ValueError):
                    recovery.run(source, root / "audit")
            audited = json.loads((root / "audit/results.json").read_text())
            self.assertEqual(audited["status"], "FAILED_RETAINED")
            self.assertFalse(audited["board_tested"])
            self.assertEqual(json.loads((source / "results.json").read_text()), report)


if __name__ == "__main__":
    unittest.main()
