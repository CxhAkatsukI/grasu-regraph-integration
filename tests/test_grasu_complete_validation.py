"""Fail-closed validation contracts, separate from executing the actual kernels."""

import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from validation.grasu_complete import analysis, commands, preparation, reference, runtime


def source_stdout(variant):
    if variant == "search":
        return "".join(f"SEARCH_PIPELINE_PASS updates={count} probes=9 stalled=0 channels=0 "
                       "output_blocked=0 host_vendor_keep_bits=12\n"
                       f"SEARCH_BINDING_RTL_ROW generation={generation} updates={count}\n"
                       for count in analysis.COUNTS for generation in (0, 1))
    token = int(variant == "cache-token")
    return "".join(f"PRODUCTION_CACHE_PASS updates={count} conflict={conflict} capacity=131072 token={token}\n"
                   for count, conflict in analysis.CACHE_ROWS)


class CompleteValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_compiler_temporaries_are_campaign_owned_not_global_tmp(self):
        environment = runtime.environment(self.root)
        self.assertEqual(environment["TMPDIR"], str(self.root / "temporary"))
        self.assertTrue(Path(environment["TMPDIR"]).is_dir())
        self.assertEqual(environment["PATH"], "/usr/bin:/bin")
        with self.assertRaises(FileExistsError):
            runtime.environment(self.root)

    def test_rows_are_ordered_complete_and_variant_specific(self):
        for variant in commands.VARIANTS:
            stdout = source_stdout(variant)
            self.assertEqual(len(analysis.functional(stdout, variant)), 18 if variant == "search" else 6)
            with self.assertRaises(ValueError):
                analysis.functional(stdout + stdout, variant)
            with self.assertRaises(ValueError):
                analysis.functional(stdout[:stdout.rfind("\n", 0, -1)], variant)
        with self.assertRaises(ValueError):
            analysis.functional(source_stdout("cache-token"), "cache-plain")
        with self.assertRaises(ValueError):
            analysis.functional(source_stdout("search").replace("output_blocked=0", "output_blocked=1"), "search")

    def test_single_host_translation_unit_has_dependencies_and_no_synthesis_shortcut(self):
        for variant in commands.VARIANTS:
            packet = commands.source_commands(self.root / "source", self.root / "include", "g++", self.root, variant)
            self.assertEqual([phase for phase, _ in packet], ["compile-0", "link", "execute"])
            for phase, argv in packet[:1]:
                self.assertIn("-MD", argv)
                self.assertIn("-MT", argv)
                self.assertIn("-include", argv)
                self.assertNotIn("--allow-multiple-definition", argv)
                self.assertNotIn("-D__SYNTHESIS__", argv)
                self.assertEqual("-DGRASU_ENABLE_COMPLETION_TOKEN" in argv, variant == "cache-token")
                self.assertIn("-DGRASU_MAX_CACHE_SEGMENT=131072", argv)
            script = commands.hls_script(self.root / "source", self.root / "include", variant)
            self.assertIn("csynth_design\nexport_design -format xo", script)
            self.assertNotIn("GRASU_SEARCH_HOST_HARNESS", script)
            self.assertNotIn("-I" + str(self.root / "include"), script)
            self.assertNotIn("-pthread", script)
            self.assertEqual("-DGRASU_ENABLE_COMPLETION_TOKEN" in script, variant == "cache-token")
        with self.assertRaises(ValueError):
            commands.hls_script(self.root / "with space", self.root, "search")

    def test_synthesis_headers_are_frozen_without_overriding_driver_selection(self):
        tool = self.root / "tool"
        for relative in ("common/technology/autopilot", "vcxx/data"):
            path = tool / relative / "hls_stream.h"
            path.parent.mkdir(parents=True)
            path.write_text("// synthesis model\n")
        pins = preparation.toolchain_headers(self.root / "snapshot", tool / "settings64.sh")
        self.assertEqual(len(pins), 4)
        preparation.unchanged(pins)
        (tool / "vcxx/data/hls_stream.h").write_text("// changed\n")
        with self.assertRaises(ValueError):
            preparation.unchanged(pins)

    def test_freeze_checks_reviewed_cores_and_pins_fixture_and_headers(self):
        fixture = self.root / "fixture"
        files = [fixture / "search_pipeline" / name for name in ("finite_host.hpp", "control.hpp")]
        files += [fixture / "search_binding/rtl_control.cpp", self.root / "config.h",
                  self.root / "include/hls_stream.h", self.root / "include/etc/ap_int_base.h"]
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// input fixture\n")
        pins, sources = preparation.prepare(self.root / "output", fixture, self.root / "config.h", self.root / "include")
        preparation.unchanged(pins)
        self.assertEqual(len(sources), 19)
        self.assertTrue(any(row["member"] == "vendor/include/hls_stream.h" for row in sources))
        files[0].write_text("// changed externally\n")
        with self.assertRaises(ValueError):
            preparation.unchanged(pins)
        owner = preparation.ROOT / "kernels/grasu_complete"
        manifest = json.loads((owner / "provenance.json").read_text())
        manifest["files"][0]["origin_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            preparation.reviewed(owner, manifest)

    def make_reference(self):
        folder = self.root / "reference"
        (folder / "raw").mkdir(parents=True)
        report = {"status": "SOURCE_FUNCTIONAL_PASS_NOT_RTL", "stage": "source", "pins": [],
                  "sources": [{"member": "core", "sha256": "abc"}], "steps": [], "functional": {}}
        for variant in commands.VARIANTS:
            stdout = source_stdout(variant)
            (folder / "raw" / (variant + "-execute.stdout.txt")).write_text(stdout)
            (folder / "raw" / (variant + "-execute.stderr.txt")).write_text("")
            report["functional"][variant] = analysis.functional(stdout, variant)
            report["steps"] += [{"variant": variant, "phase": phase, "exit_code": 0,
                                 "stop_reason": "process_exit", "cleanup_snapshot_error": None}
                                for phase in ("compile-0", "link", "execute")]
        (folder / "results.json").write_text(json.dumps(report))
        return folder, report

    def test_hls_reference_requires_same_inputs_complete_steps_and_oracle_logs(self):
        folder, report = self.make_reference()
        preparation.unchanged(reference.freeze(self.root / "accepted", folder, report["sources"]))
        with self.assertRaises(ValueError):
            reference.freeze(self.root / "bad-input", folder, [{"member": "core", "sha256": "changed"}])
        report["steps"][0]["exit_code"] = 1
        (folder / "results.json").write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            reference.freeze(self.root / "bad-step", folder, report["sources"])
        report["steps"][0]["exit_code"] = 0
        (folder / "results.json").write_text(json.dumps(report))
        (folder / "raw/search-execute.stdout.txt").write_text("")
        with self.assertRaises(ValueError):
            reference.freeze(self.root / "bad-log", folder, report["sources"])

    def make_export(self, arguments):
        directory = self.root / "hls"
        directory.mkdir(exist_ok=True)
        report = directory / "project/solution/syn/report/process_cache_csynth.xml"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("<profile><UserAssignments><TargetClockPeriod>6.667</TargetClockPeriod></UserAssignments>"
                          "<PerformanceEstimates><SummaryOfTimingAnalysis><EstimatedClockPeriod>7</EstimatedClockPeriod>"
                          "</SummaryOfTimingAnalysis></PerformanceEstimates></profile>")
        with ZipFile(directory / "candidate.xo", "w") as archive:
            archive.writestr("process_cache/kernel.xml", '<root><kernel name="process_cache"><args>' +
                             "".join(f'<arg name="{name}"/>' for name in arguments) + '</args></kernel></root>')
        return directory

    def test_hls_export_is_not_rtl_route_or_timing_closure(self):
        arguments = ["pma_cache", "update_stream", "completion_token"]
        observed = analysis.exported(self.make_export(arguments), "cache-token")
        self.assertFalse(observed["estimate_meets_target"])
        self.assertFalse(observed["full_abi_reviewed"])
        self.assertFalse(observed["rtl_validated"])
        self.assertFalse(observed["routed"])
        with self.assertRaises(ValueError):
            analysis.exported(self.root / "hls", "cache-plain")
        with self.assertRaises(ValueError):
            analysis.exported(self.make_export(list(reversed(arguments))), "cache-token")

    def test_report_clock_rounding_does_not_admit_a_different_target(self):
        for text in ("6.67", "6.667", "6.666666667"):
            self.assertEqual(analysis.target_period(text), float(text))
        for text in ("6.68", "6.7", "7", "0", "-6.67", "NaN", "Infinity", "missing"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                analysis.target_period(text)


if __name__ == "__main__":
    unittest.main()
