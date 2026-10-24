"""Generate-only checks for the explicit physical AXI sharing profile."""

import csv
import hashlib
import unittest

from test_grasu_kernel_selection import SourceSelectionTests, PURE, PR, SCRIPTS


class PhysicalPortTests(unittest.TestCase):
    setUp = SourceSelectionTests.setUp
    generate = SourceSelectionTests.generate

    def test_all_four_algorithms_emit_consistent_shared_port_inputs(self):
        for script, algorithm in ((PURE, "weighted_sssp"),
                                  (PURE, "connected_components"),
                                  (PR, "full_pagerank"), (PR, "residual_pagerank")):
            with self.subTest(algorithm=algorithm):
                self.generate(script, algorithm, "--grasu-implementation",
                              "complete-search-cache", "--adapter-policy", "prefetch-compact",
                              "--physical-port-policy", "shared-ingress")
                commands = (self.output / "compile_commands.sh").read_text()
                selected = [line for line in commands.splitlines() if line.startswith("v++ ")
                            and ("search_binding/top.cpp" in line or
                                 "pma_prefetch_compact/top.cpp" in line)]
                self.assertEqual(len(selected), 2)
                for line in selected:
                    self.assertIn("-DGRI_HMSS_SHARED_INGRESS=1", line)
                cfg = (self.output / "config" / (f"{algorithm}_hw.cfg" if script == PR
                       else "weighted_pma_native_sharded_k4_hw.cfg")).read_text()
                for cu in range(1, 5):
                    self.assertIn(f"sp=bin_search_{cu}.edges:HBM[0:22]", cfg)
                    self.assertIn(f"sp=bin_search_{cu}.binary_0:HBM[0:22]", cfg)
                    self.assertIn(f"sp=bin_search_{cu}.row_offset_0:HBM[0:22]", cfg)
                manifest = dict(line.split("=", 1) for line in
                                (self.output / "manifest.env").read_text().splitlines())
                self.assertEqual(manifest["PHYSICAL_PORT_POLICY"], "shared-ingress")
                self.assertEqual(manifest["PHYSICAL_PORT_POLICY_IS_HARDWARE_EVIDENCE"], "0")
                self.assertEqual(manifest["PMA_ADAPTER_AXI_BUNDLES_PER_CU"], "2")
                with (self.output / "inputs.tsv").open() as stream:
                    records = {row["path"]: row for row in csv.DictReader(stream, delimiter="\t")}
                helper = SCRIPTS / "lib/physical_port_policy.sh"
                self.assertEqual(records[str(helper)]["sha256"],
                                 hashlib.sha256(helper.read_bytes()).hexdigest())

    def test_invalid_sharing_requests_fail_before_creating_output(self):
        for options in (("--physical-port-policy", "typo"),
                        ("--grasu-implementation", "legacy-direct-cache"),
                        ("--adapter-policy", "legacy"), ("--target", "sw_emu")):
            with self.subTest(options=options):
                result = self.generate(PURE, "weighted_sssp", "--grasu-implementation",
                                       "complete-search-cache", "--adapter-policy",
                                       "prefetch-compact", "--physical-port-policy",
                                       "shared-ingress", *options, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
