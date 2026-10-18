"""Source/command tests, not timing or board qualification."""

import hashlib
import shlex
import shutil
import unittest

from test_grasu_kernel_selection import SourceSelectionTests, PURE, PR, SCRIPTS


class AdapterSelectionTests(SourceSelectionTests):
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
