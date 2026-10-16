"""Read-only component admission must reject stale or incomplete evidence."""

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from validation.grasu_complete import admission, commands, preparation


class ProductionAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.owner = self.root / "kernels/grasu_complete"
        shutil.copytree(preparation.ROOT / "kernels/grasu_complete", self.owner)
        self.attempt = self.root / "attempt"
        (self.attempt / "raw").mkdir(parents=True)
        self.config = self.root / "kernel_config.h"
        self.config.write_text("// integration config\n")
        provenance = json.loads((self.owner / "provenance.json").read_text())
        inputs = [(self.owner / row["path"], "grasu_complete/" + row["path"])
                  for row in provenance["files"]]
        inputs += [(self.owner / "provenance.json", "grasu_complete/provenance.json"),
                   (self.config, "upstream/kernel_config.h")]
        sources = []
        for original, member in inputs:
            frozen = self.attempt / "source" / member
            frozen.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, frozen)
            sources.append({"member": member, **preparation.pin(frozen)})
        self.report = {"stage": "rtl", "status": admission.RTL_PASS, "errors": [],
                       "rtl_validated": True, **dict.fromkeys(admission.CLAIMS, False),
                       "pins": [preparation.pin(Path(row["path"])) for row in sources],
                       "sources": sources, "steps": [], "components": {}}
        for variant in commands.VARIANTS:
            raw = {"exit_code": 0, "stop_reason": "process_exit", "cleanup_snapshot_error": None}
            path = self.attempt / "raw" / (variant + "-rtl-cosimulation.resources.json")
            path.write_text(json.dumps(raw))
            self.report["steps"].append({"variant": variant, "phase": "rtl-cosimulation", **raw})
            self.report["components"][variant] = {
                "export": {"estimate_meets_target": True, "xo": variant}, "artifacts": []}
        self.observations = copy.deepcopy(self.report["components"])
        self.addCleanup(patch.stopall)
        patch.object(preparation, "ROOT", self.root).start()
        self.inspector = patch.object(admission.rtl_analysis, "inspect", side_effect=
            lambda directory, variant, reference: copy.deepcopy(self.observations[variant])).start()
        self.write()

    def write(self):
        (self.attempt / "results.json").write_text(json.dumps(self.report))

    def review(self):
        return admission.review(self.attempt, self.config)

    def test_complete_review_preserves_original_and_does_not_promote_integration(self):
        original = preparation.pin(self.attempt / "results.json")
        result = admission.run(self.attempt, self.config, self.root / "review")
        self.assertEqual(result["status"], admission.PASS)
        self.assertEqual(result["original_result"], original)
        self.assertEqual(preparation.pin(self.attempt / "results.json"), original)
        self.assertFalse(result["original_result_modified"])
        self.assertFalse(result["integrated_g_admitted"])
        self.assertFalse(result["external_RTL_backpressure_tested"])
        for key in admission.CLAIMS:
            self.assertFalse(result[key])
        self.assertEqual(self.inspector.call_count, 3)
        preparation.unchanged(result["pins"])
        with self.assertRaises(FileExistsError):
            admission.run(self.attempt, self.config, self.root / "review")

    def test_incomplete_failed_or_promoted_matrix_is_rejected(self):
        baseline = copy.deepcopy(self.report)
        mutations = [lambda row: row.update(status="FAILED_RETAINED"),
                     lambda row: row.update(errors=["error"]),
                     lambda row: row.update(rtl_validated=False),
                     lambda row: row.update(routed=True),
                     lambda row: row["steps"].reverse(),
                     lambda row: row["steps"].pop(),
                     lambda row: row["components"].pop("search"),
                     lambda row: row["steps"][0].update(exit_code=1),
                     lambda row: row["steps"][0].update(stop_reason="timeout"),
                     lambda row: row["steps"][0].update(cleanup_snapshot_error="error"),
                     lambda row: row["sources"].append(row["sources"][0])]
        for mutation in mutations:
            self.report = copy.deepcopy(baseline)
            mutation(self.report)
            self.write()
            with self.assertRaises(ValueError):
                self.review()

    def test_changed_raw_execution_or_component_observation_is_rejected(self):
        path = self.attempt / "raw/search-rtl-cosimulation.resources.json"
        original = path.read_text()
        path.write_text("{}")
        with self.assertRaises(ValueError):
            self.review()
        path.write_text(original)
        self.observations["search"]["export"]["xo"] = "different"
        with self.assertRaises(ValueError):
            self.review()

    def test_unmet_clock_estimate_is_not_accepted_as_route_ready(self):
        self.observations["search"]["export"]["estimate_meets_target"] = False
        self.report["components"] = copy.deepcopy(self.observations)
        self.write()
        with self.assertRaises(ValueError):
            self.review()

    def test_current_config_and_frozen_source_must_both_match(self):
        self.config.write_text("// different integration config\n")
        with self.assertRaises(ValueError):
            self.review()
        self.config.write_text("// integration config\n")
        frozen = self.attempt / "source/grasu_complete/search_binding/top.cpp"
        frozen.write_text("// stale source\n")
        with self.assertRaises(ValueError):
            self.review()

    def test_current_owned_core_cannot_drift_from_reviewed_provenance(self):
        core = self.owner / "search_binding/top.cpp"
        core.write_text(core.read_text() + "\n// changed\n")
        with self.assertRaises(ValueError):
            self.review()


if __name__ == "__main__":
    unittest.main()
