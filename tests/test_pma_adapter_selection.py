"""Source/command tests, not timing or board qualification."""

import hashlib
import json
import shlex
import shutil
import subprocess
import unittest

from test_grasu_kernel_selection import SourceSelectionTests, PURE, PR, SCRIPTS
from test_check_pipeline_master_budget import MASTER_COUNTS, write_xo


class AdapterSelectionTests(SourceSelectionTests):
    def test_over_budget_link_stops_before_tool_setup(self):
        for script, algorithm, expected in ((PURE, "weighted_sssp", 34),
                                             (PURE, "connected_components", 34),
                                             (PR, "full_pagerank", 39),
                                             (PR, "residual_pagerank", 40)):
            with self.subTest(algorithm=algorithm):
                self.generate(script, algorithm, "--grasu-implementation",
                              "complete-search-cache", "--adapter-policy",
                              "prefetch-compact")
                build = self.output / "build"
                counts = dict(MASTER_COUNTS, process_ddr=4,
                              pma_to_regraph_adapter=3,
                              regraph_pagerank_apply=3 if script == PR and
                              algorithm == "residual_pagerank" else 2,
                              dispatch=0, pma_completion_barrier=0, kernelApply=2)
                for kernel, count in counts.items():
                    write_xo(build / f"{kernel}.hw.xo", count)
                environment = {**self.environment,
                               "GRI_VITIS_SETTINGS": "/nonexistent/forbidden-tool-setup.sh"}
                result = subprocess.run(["bash", str(self.output / "link_command.sh")],
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("exceeding platform budget 32", result.stderr)
                self.assertNotIn("forbidden-tool-setup", result.stderr)
                report = json.loads((self.output / "pipeline_master_budget.json").read_text())
                self.assertFalse(report["passed"])
                self.assertEqual(report["projected_axi_master_instances"], expected)

    def test_prefetch_compact_four_algorithms_both_targets(self):
        for script, algorithm, audit in ((PURE, "weighted_sssp", "sssp"),
                                        (PURE, "connected_components", "cc"),
                                        (PR, "full_pagerank", "fullpr"),
                                        (PR, "residual_pagerank", "respr")):
            for target in ("hw", "hw_emu"):
                with self.subTest(algorithm=algorithm, target=target):
                    self.generate(script, algorithm, "--grasu-implementation",
                                  "complete-search-cache", "--adapter-policy",
                                  "prefetch-compact", "--target", target)
                    commands = (self.output / "compile_commands.sh").read_text()
                    self.assertIn("kernels/pma_prefetch_compact/top.cpp", commands)
                    scatter = next(line for line in commands.splitlines()
                                   if line.endswith("/little_gs_stream.cpp"))
                    self.assertIn("-DGRASU_REGRAPH_PREFETCH_COMPACT=1", scatter)
                    self.assertIn('source "${GRI_VITIS_SETTINGS:-', commands)
                    inputs = (self.output / "inputs.tsv").read_text()
                    self.assertIn("/pma_prefetch_compact/compactor.hpp", inputs)
                    self.assertIn("/regraph_stream_little_gs/framed/scatter.hpp", inputs)
                    config = "\n".join(path.read_text() for path in
                                       (self.output / "config").glob("*.cfg"))
                    self.assertIn("pma_to_regraph_adapter_4.row_offset:HBM[0:22]", config)
                    if script == PURE:
                        self.assertIn("kernelApply_1.vertex_prop_write:HBM[30]", config)
                        self.assertIn("/regraph_sssp_apply_status/prefetch.hpp", inputs)
                    link = (self.output / "link_command.sh").read_text()
                    self.assertEqual("--algorithm " + audit in link, target == "hw")
                    if target == "hw":
                        self.assertLess(link.index("check_pipeline_master_budget.py"),
                                        link.index("source "))
                    for name in ("compile_commands.sh", "link_command.sh"):
                        subprocess.run(["bash", "-n", str(self.output / name)], check=True)

    def test_explicit_policy_four_algorithms(self):
        expected = {
            "ROW_PREFETCH": "1", "STOP_AFTER_LAST": "1", "SKIP_EMPTY_SEGMENT": "1",
            "ROW_LINE_READ": "1", "CROSS_ROW_PIPELINE": "1", "DIRECTORY_TILE_ROWS": "1024",
            "PACKET_PIPELINE": "1", "BANK_STREAM": "1", "BANK_FIFO_LINES": "256",
        }
        for script, algorithm in ((PURE, "weighted_sssp"), (PURE, "connected_components"),
                                  (PR, "residual_pagerank"), (PR, "full_pagerank")):
            with self.subTest(algorithm=algorithm):
                self.generate(script, algorithm, "--grasu-implementation", "complete-search-cache",
                              "--adapter-policy", "bank-stream")
                lines = (self.output / "compile_commands.sh").read_text().splitlines()
                adapter = next(line for line in lines if line.endswith("pma_to_regraph_adapter.cpp"))
                flags = shlex.split(adapter)
                for key, value in expected.items():
                    self.assertIn(f"-DGRASU_REGRAPH_{key}={value}", flags)
                mode = "WEIGHTED_PMA" if algorithm == "weighted_sssp" else "DESTINATION_ONLY"
                self.assertIn(f"-DGRASU_REGRAPH_{mode}=1", flags)
                for line in lines:
                    if line.startswith("v++ ") and line != adapter:
                        self.assertNotIn("-DGRASU_REGRAPH_BANK_STREAM=1", line)
                manifest = (self.output / "manifest.env").read_text()
                self.assertIn("ADAPTER_ROW_LINE_READ=1\n", manifest)
                self.assertIn("ADAPTER_POLICY_IS_HARDWARE_EVIDENCE=0\n", manifest)
                helper = SCRIPTS / "lib/pma_adapter_selection.sh"
                self.assertIn(hashlib.sha256(helper.read_bytes()).hexdigest(),
                              (self.output / "inputs.tsv").read_text())

    def test_invalid_adapter_policy_before_output(self):
        for script, algorithm in ((PURE, "connected_components"), (PR, "residual_pagerank")):
            for options in (("--adapter-policy", "typo"),
                            ("--adapter-policy", "bank-stream", "--pipeline-mode", "weighted-axis")):
                with self.subTest(script=script, options=options):
                    result = self.generate(script, algorithm, *options, check=False)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(self.output.exists())

    def test_pagerank_source_archive_records_unavailable_git_identity(self):
        archive = self.root / "source-archive"
        for member in ("scripts", "include", "kernels"):
            shutil.copytree(SCRIPTS.parent / member, archive / member,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.rmtree(self.grasu / ".git")
        self.environment["GRI_ROOT"] = str(archive)
        self.generate(PR, "residual_pagerank", "--grasu-implementation", "complete-search-cache",
                      "--adapter-policy", "bank-stream", directory=archive / "scripts")
        manifest = (self.output / "manifest.env").read_text()
        self.assertIn("GRI_GIT_HEAD=not_available\n", manifest)
        self.assertIn("GRI_GIT_TRACKED_DIRTY=not_available\n", manifest)
        self.assertIn("GRASU_GIT_HEAD=not_available\n", manifest)


if __name__ == "__main__":
    unittest.main()
