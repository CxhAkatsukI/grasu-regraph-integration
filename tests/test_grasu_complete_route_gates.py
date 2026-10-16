"""Production route preparation rejects mixed versions and missing evidence."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.grasu_complete import preparation as common
from validation.grasu_complete.routing import gates, preparation
from validation.grasu_complete.integration import delivery


class ProductionRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rtl, self.connected, self.fit = [self.root / name for name in ("rtl", "connected", "fit")]
        for path in (self.rtl, self.connected, self.fit):
            path.mkdir()
        self.source = self.root / "source.hpp"
        self.source.write_text("// unchanged production source\n")
        provenance = json.loads((common.ROOT / "kernels/grasu_complete/provenance.json").read_text())
        names = ["grasu_complete/" + row["path"] for row in provenance["files"]]
        names += ["grasu_complete/provenance.json", "upstream/kernel_config.h"]
        self.sources = [{"member": name, **common.pin(self.source)} for name in names]
        self.complete = {"status": delivery.PASS, "sources": copy.deepcopy(self.sources), "pins": []}
        self.ledger = {"source": [], "single_cu_relocation_screen": {
            "uram_oversubscribed_slrs": [], "total_uram_capacity_exceeded": False,
            "platform_storage_screen": {"uram_oversubscribed_slrs": [], "total_uram_capacity_exceeded": False}}}
        self.exports = {variant: {"report": str(self.root / (variant + ".xml")),
                                   "xo": str(self.root / (variant + ".xo"))}
                        for variant in ("search", "cache-token")}
        self.checked = {"pins": [], "exports": self.exports}
        self.reused = {"pins": [], "kernels": {"dispatch": {}, "process_ddr": {}}}
        self.write()
        self.addCleanup(patch.stopall)
        patch.object(gates.admission, "review", return_value=self.checked).start()
        patch.object(gates.delivery, "recheck", side_effect=lambda _: copy.deepcopy(self.complete)).start()
        self.fit_check = patch.object(gates, "validate_fit").start()
        self.resources = patch.object(gates, "resources", return_value={"URAM": 128}).start()
        self.upstream = patch.object(gates.upstream, "review", return_value=self.reused).start()

    def write(self):
        (self.rtl / "results.json").write_text(json.dumps({"sources": self.sources}))
        (self.connected / "results.json").write_text(json.dumps(self.complete))
        (self.fit / "results.json").write_text(json.dumps(self.ledger))

    def review(self):
        return gates.candidates(self.root, self.root, self.rtl, self.connected, self.fit, self.source)

    def test_matching_production_evidence_only_replaces_two_xos(self):
        report = self.review()
        self.assertEqual(report["replacements"], {"bin_search": Path(self.exports["search"]["xo"]),
                                                  "process_cache": Path(self.exports["cache-token"]["xo"])})
        self.fit_check.assert_called_once()
        self.upstream.assert_called_once()
        for claim in ("integrated_rtl_admitted", "device_metadata_refresh_admitted",
                      "production_baseline_admitted", "publication_match_admitted"):
            self.assertFalse(report["identity"][claim])

    def test_different_frozen_host_benches_do_not_hide_an_owned_source_difference(self):
        member = "grasu_complete/search_pipeline/finite_host.hpp"
        self.sources.append({"member": member, "sha256": "0" * 64})
        self.complete["sources"].append({"member": member, "sha256": "1" * 64})
        self.write()
        result = self.review()
        self.assertEqual(len(result["identity"]["production_source_members"]), 13)
        self.assertNotIn(member, {row["member"] for row in result["identity"]["production_source_members"]})
        self.complete["sources"][0]["sha256"] = "2" * 64
        with self.assertRaises(ValueError):
            self.review()

    def test_retained_failed_connected_attempt_is_not_route_admission(self):
        self.complete["status"] = "FAILED_RETAINED"
        with self.assertRaisesRegex(ValueError, "passing connected"):
            self.review()
        self.upstream.assert_not_called()

    def test_mixed_missing_or_duplicate_connected_sources_rejected(self):
        baseline = copy.deepcopy(self.complete)
        for sources in (self.sources[1:], [*self.sources, self.sources[0]],
                        [{**self.sources[0], "sha256": "0" * 64}, *self.sources[1:]]):
            self.complete = {**baseline, "sources": sources}
            with self.assertRaises(ValueError):
                self.review()

    def test_infeasible_or_missing_platform_storage_screen_rejected(self):
        baseline = copy.deepcopy(self.ledger)
        for mutation in (lambda row: row.pop("platform_storage_screen"),
                         lambda row: row.update(uram_oversubscribed_slrs=["SLR0"]),
                         lambda row: row["platform_storage_screen"].update(total_uram_capacity_exceeded=True)):
            self.ledger = copy.deepcopy(baseline)
            mutation(self.ledger["single_cu_relocation_screen"])
            self.write()
            with self.assertRaises(ValueError):
                self.review()

    def test_storage_screen_must_describe_same_component(self):
        self.resources.side_effect = [{"URAM": 128}, {"URAM": 64}]
        with self.assertRaisesRegex(ValueError, "resource screen differs"):
            self.review()

    def test_prepare_checks_fresh_path_and_timeout_before_gates(self):
        with patch.object(preparation.gates, "candidates") as review:
            args = [self.root] * 6
            with self.assertRaises(FileExistsError):
                preparation.prepare(*args, self.root)
            for value in (True, 43200.0, 36000, 0):
                with self.assertRaises(ValueError):
                    preparation.prepare(*args, self.root / "new", link_timeout_seconds=value)
            review.assert_not_called()

    def test_prepared_packet_retains_gates_and_pins_each_runner_copy(self):
        output = self.root / "route"
        checked = {"replacements": {}, "reports": [], "pins": [common.pin(self.source)],
                   "identity": {"production_baseline_admitted": False}}
        def freeze(*args, **kwargs):
            self.assertEqual(args[-1], output)
            self.assertEqual(kwargs, {"link_timeout_seconds": 43200})
            output.mkdir()
            return {"status": "PREPARED_DIAGNOSTIC_LINK_NOT_BASELINE_ADMISSION",
                    "pins": [], "FPGA_timing_admitted": False}
        with patch.object(preparation.gates, "candidates", return_value=checked), \
                patch.object(preparation, "freeze", side_effect=freeze):
            manifest = preparation.prepare(*([self.root] * 6), output)
        self.assertEqual(manifest, json.loads((output / "manifest.json").read_text()))
        self.assertEqual(manifest["candidate_owner"], "production-source-grasu-complete")
        self.assertEqual(manifest["production_source_evidence"], checked["identity"])
        self.assertFalse(manifest["FPGA_timing_admitted"])
        common.unchanged(manifest["pins"])
        pins = {row["path"]: row for row in manifest["pins"]}
        originals = list(Path(preparation.__file__).parent.glob("*.py"))
        copies = list((output / "runner").glob("*.py"))
        for original in originals:
            self.assertIn(str(original), pins)
            self.assertTrue(any(common.pin(copy)["sha256"] == common.pin(original)["sha256"]
                                for copy in copies))
        copies[0].write_text("# changed frozen runner\n")
        with self.assertRaises(ValueError):
            common.unchanged(manifest["pins"])


if __name__ == "__main__":
    unittest.main()
