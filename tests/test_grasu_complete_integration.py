"""Connected host harness admission; these unit tests are not kernel evidence."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.grasu_complete.integration import analysis, delivery, preparation
from validation.grasu_complete.preparation import unchanged


def line(count, generation, blocked=4):
    return (f"PRODUCTION_CONNECTED_PASS updates={count} generation={generation} capacity=131072 "
            "search=4 cache=2 cold=2 external_channels=12 internal_channels=1356 completions=4 "
            f"blocked={blocked} same_addresses=1\n")


class IntegrationTests(unittest.TestCase):
    def evidence(self, root):
        report = {"status": delivery.PASS, "errors": [], "pins": [],
                  **dict.fromkeys(delivery.CLAIMS, False), "steps": [],
                  "memory_events_after": "high 0\nmax 0\noom 0\noom_kill 0\n",
                  "admission": {"admitted": True}}
        raw = {"raw/connected-execute.stdout.txt": "".join(
            line(count, generation) for count in analysis.COUNTS for generation in (0, 1)),
               "raw/connected-execute.stderr.txt": "".join(analysis.WARNING_PAIR * 417),
               "raw/connected-stale-metadata.stdout.txt": line(0, 0) + line(0, 1) + line(1, 0),
               "raw/connected-stale-metadata.stderr.txt": "integrated PMA state mismatch\n"}
        for phase in ("compile-0", "link", "execute", "negative-stale-metadata"):
            step = {"variant": "connected", "phase": phase, "stop_reason": "process_exit",
                    "exit_code": int(phase.startswith("negative")), "cleanup_snapshot_error": None}
            report["steps"].append(step)
            name = "stale-metadata" if phase.startswith("negative") else phase
            raw["raw/connected-" + name + ".resources.json"] = json.dumps(
                {key: value for key, value in step.items() if key not in ("variant", "phase")})
        report["functional"] = analysis.functional(raw["raw/connected-execute.stdout.txt"])
        report["diagnostics"] = analysis.diagnostics(raw["raw/connected-execute.stderr.txt"])
        report["stale_metadata_control"] = analysis.stale_rejection(
            report["steps"][-1], raw["raw/connected-stale-metadata.stdout.txt"],
            raw["raw/connected-stale-metadata.stderr.txt"])
        root.mkdir()
        for name, contents in {**raw, "results.json": json.dumps(report)}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        return report, raw

    def test_delivery_replays_raw_matrix_and_preserves_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report, raw = self.evidence(root / "attempt")
            delivery.replay(report, raw.__getitem__)
            for field, value in (("board_validated", True), ("memory_events_after", "oom 1\n"),
                                 ("functional", []), ("steps", report["steps"][:-1])):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    delivery.replay({**report, field: value}, raw.__getitem__)
            changed = dict(raw)
            changed["raw/connected-execute.resources.json"] = "{}"
            with self.assertRaises(ValueError):
                delivery.replay(report, changed.__getitem__)
            with patch.object(delivery, "recheck", return_value=report):
                index = delivery.package(root / "capsule", [root / "attempt"])
            self.assertEqual(index["attempts"][0]["rows"], 18)
            self.assertFalse(index["board_validated"])
            original = (root / "capsule/index.json").read_text()
            index["board_validated"] = True
            (root / "capsule/index.json").write_text(json.dumps(index))
            with self.assertRaises(ValueError):
                delivery.verify(root / "capsule")
            (root / "capsule/index.json").write_text(original)
            with (root / "capsule/connected_host.tar.gz").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaises(ValueError):
                delivery.verify(root / "capsule")

    def test_delivery_retains_failed_attempt_without_promoting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report, _ = self.evidence(root / "pass")
            failure = copy.deepcopy(report)
            failure.update(status="FAILED_RETAINED", errors=["rejected diagnostic"], steps=[])
            (root / "fail").mkdir()
            (root / "fail/results.json").write_text(json.dumps(failure))
            with patch.object(delivery, "recheck", side_effect=[failure, report]):
                index = delivery.package(root / "capsule", [root / "fail", root / "pass"])
            self.assertEqual(index["attempts"][0]["status"], "FAILED_RETAINED")
            self.assertEqual(index["attempts"][0]["errors"], ["rejected diagnostic"])
            with patch.object(delivery, "recheck", return_value=failure), self.assertRaises(ValueError):
                delivery.package(root / "no-pass", [root / "fail"])

    def test_only_exact_independent_cold_insert_warning_counts_are_admitted(self):
        self.assertEqual(analysis.expected_cold_insertions(), 417)
        messages = analysis.WARNING_PAIR
        # Real concurrent writers need not keep each message on its own line.
        stderr = "".join(messages * 417)
        self.assertEqual(analysis.diagnostics(stderr)["retained_vendor_width_warning_pairs"], 417)
        for changed in (stderr + "unknown warning", stderr + messages[0],
                        stderr.replace(messages[1], "", 1), ""):
            with self.assertRaises(ValueError):
                analysis.diagnostics(changed)

    def test_complete_ordered_matrix_and_backpressure_are_required(self):
        stdout = "".join(line(count, generation) for count in analysis.COUNTS for generation in (0, 1))
        self.assertEqual(len(analysis.functional(stdout)), 18)
        for changed in (stdout + stdout, stdout.split("\n", 1)[1], stdout + "FPGA PASS\n",
                        stdout.replace("capacity=131072", "capacity=1024"),
                        stdout.replace("same_addresses=1", "same_addresses=0"),
                        stdout.replace("blocked=4", "blocked=0"),
                        stdout.replace("completions=4", "completions=3")):
            with self.subTest(output=changed[:80]), self.assertRaises(ValueError):
                analysis.functional(changed)

    def test_expected_stale_metadata_rejection_is_not_any_failure(self):
        step = {"exit_code": 1, "stop_reason": "process_exit", "cleanup_snapshot_error": None}
        stdout = line(0, 0) + line(0, 1) + line(1, 0)
        stderr = "integrated PMA state mismatch\n"
        self.assertTrue(analysis.stale_rejection(step, stdout, stderr)["expected_rejection"])
        for changed in ({**step, "exit_code": 0}, {**step, "exit_code": -9},
                        {**step, "stop_reason": "timeout"}, {**step, "cleanup_snapshot_error": "unknown"}):
            with self.assertRaises(ValueError):
                analysis.stale_rejection(changed, stdout, stderr)
        for changed_stdout, changed_stderr in ((stdout + line(1, 1), stderr),
                                               (stdout, "segmentation fault\n"), ("", stderr)):
            with self.assertRaises(ValueError):
                analysis.stale_rejection(step, changed_stdout, changed_stderr)

    def test_single_translation_unit_uses_actual_cores_full_cache_and_dependencies(self):
        packet = preparation.packet(Path("/fresh/output"), Path("/usr/bin/g++"))
        self.assertEqual([phase for phase, _ in packet], ["compile-0", "link", "execute"])
        argv = packet[0][1]
        for flag in ("-MD", "-MF", "-DGRASU_MAX_CACHE_SEGMENT=131072", "-DCACHE_BANK_REGISTERED",
                     "-DGRASU_ENABLE_COMPLETION_TOKEN", "-DGRASU_SHARE_HBM_PORTS", "-pthread"):
            self.assertIn(flag, argv)
        self.assertNotIn("-D__SYNTHESIS__", argv)
        self.assertNotIn("--allow-multiple-definition", argv)
        fixture = Path(preparation.__file__).parent / "fixtures/bench.cpp"
        for core in ("search_binding/top.cpp", "process_cache.cpp", "kernel_dispatch.cpp", "kernel_process_ddr.cpp"):
            self.assertIn(core, fixture.read_text())

    def test_freeze_includes_connected_sources_fixture_and_main_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = [root / "upstream" / name for name in
                     ("kernel_config.h", "kernel_dispatch.cpp", "kernel_process_ddr.cpp")]
            files += [root / "fixture/search_pipeline" / name for name in ("finite_host.hpp", "control.hpp")]
            files += [root / "fixture/search_binding/rtl_control.cpp", root / "include/hls_stream.h",
                      root / "include/etc/ap_int_base.h"]
            for path in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// isolated mock input\n")
            output = root / "output"
            pins, sources = preparation.prepare(output, root / "fixture", root / "upstream", root / "include")
            unchanged(pins)
            members = {row["member"] for row in sources}
            self.assertTrue({"upstream/kernel_dispatch.cpp", "upstream/kernel_process_ddr.cpp",
                             "integration/bench.cpp", "integration/state.hpp", "integration/execution.hpp"} <= members)
            self.assertTrue((output / "runner/integration/study.py").is_file())
            files[1].write_text("// changed actual dispatch\n")
            with self.assertRaises(ValueError):
                unchanged(pins)


if __name__ == "__main__":
    unittest.main()
