"""Generate-only source/ABI regression; does not invoke FPGA tools."""

import csv
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPLETE = ROOT / "kernels/grasu_complete"
PURE = "prepare_pure_hw_pipeline_build.sh"
PR = "prepare_pagerank_pipeline_build.sh"
LEGACY_COMMIT = "6f5ebf2b0679f04f4f6e035e850fce7b6043a660"


def write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="ascii")


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.grasu = self.root / "GraSU"
        kernels = self.grasu / "GraSU/GraSU_kernels/src"
        for name in ("kernel_bin_search.cpp", "kernel_process_cache.cpp",
                     "kernel_process_ddr.cpp", "kernel_dispatch.cpp", "kernel_config.h"):
            write(kernels / name, "// generator input fixture\n")
        write(self.grasu / "u55c_hbm/config/GraSU-link.cfg", "[connectivity]\n")
        write(self.grasu / "u55c_hbm/config/stream_connect.ini", "[connectivity]\n")
        subprocess.run(["git", "init", "-q", str(self.grasu)], check=True)
        subprocess.run(["git", "-C", str(self.grasu), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q",
                        "--allow-empty", "-m", "fixture"], check=True)
        regraph = self.root / "ReGraph"
        for name in ("connectivity.cfg",
                     "kernel_little_gs_merger/kernel_little_gs_merger.cpp",
                     "kernel_hbm_wrapper/kernel_hbm_wrapper.cpp"):
            write(regraph / "acc_template" / name, "[connectivity]\n")
        (self.root / "hls/etc").mkdir(parents=True)
        self.environment = {**os.environ, "GRI_ROOT": str(ROOT),
                            "GRASU_ROOT": str(self.grasu), "REGRAPH_ROOT": str(regraph)}
        self.output = self.root / "output"

    def generate(self, script, algorithm, *options, directory=SCRIPTS, check=True):
        return subprocess.run(
            ["bash", str(directory / script), "--target", "hw",
             "--pipeline-mode", "sharded-k4", "--algorithm", algorithm,
             "--hls-include", str(self.root / "hls"),
             "--hls-include-etc", str(self.root / "hls/etc"),
             "--build-root", str(self.output), *options],
            cwd=ROOT, env=self.environment, capture_output=True, text=True, check=check)

    def test_complete_four_algorithms_and_both_hardware_targets(self):
        for script, algorithm in ((PURE, "weighted_sssp"), (PURE, "connected_components"),
                                  (PR, "full_pagerank"), (PR, "residual_pagerank")):
            for target in ("hw", "hw_emu"):
                with self.subTest(algorithm=algorithm, target=target):
                    self.generate(script, algorithm, "--grasu-implementation",
                                  "complete-search-cache", "--target", target)
                    commands = (self.output / "compile_commands.sh").read_text()
                    search = next(line for line in commands.splitlines()
                                  if str(COMPLETE / "search_binding/top.cpp") in line)
                    cache = next(line for line in commands.splitlines()
                                 if str(COMPLETE / "process_cache.cpp") in line)
                    self.assertIn(f"--target {target}", search)
                    self.assertIn("-DCACHE_BANK_REGISTERED", cache)
                    self.assertNotIn("GRASU_PURE_PIPELINE_DIRECT_CACHE", commands)
                    self.assertEqual("-DGRASU_ENABLE_COMPLETION_TOKEN" in cache, script == PURE)
                    self.assertIn("-DGRASU_MAX_CACHE_SEGMENT=131072", cache)
                    manifest = dict(line.split("=", 1) for line in
                                    (self.output / "manifest.env").read_text().splitlines())
                    self.assertEqual(manifest["GRASU_IMPLEMENTATION"], "complete-search-cache")
                    self.assertEqual(manifest["GRASU_CACHE_COMPLETION_TOKEN"], str(int(script == PURE)))
                    self.assertEqual(manifest["GRASU_SOURCE_SELECTION_IS_HARDWARE_EVIDENCE"], "0")
                    with (self.output / "inputs.tsv").open() as stream:
                        records = {Path(row["path"]): row for row in csv.DictReader(stream, delimiter="\t")}
                    sources = [*COMPLETE.rglob("*.cpp"), *COMPLETE.rglob("*.hpp"),
                               SCRIPTS / "lib/grasu_kernel_selection.sh",
                               self.grasu / "GraSU/GraSU_kernels/src/kernel_config.h"]
                    for source in sources:
                        self.assertEqual(records[source]["status"], "present")
                        self.assertEqual(records[source]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
                    for command_file in ("compile_commands.sh", "link_command.sh"):
                        subprocess.run(["bash", "-n", str(self.output / command_file)], check=True)

    def test_invalid_requests_fail_before_output_creation(self):
        cases = (("--target", "sw_emu"), ("--pipeline-mode", "weighted-axis"),
                 ("--max-cache-segment", "65536"), ("--grasu-implementation", "typo"))
        for script, algorithm in ((PURE, "weighted_sssp"), (PR, "residual_pagerank")):
            for options in cases:
                with self.subTest(script=script, options=options):
                    result = self.generate(script, algorithm, "--grasu-implementation",
                                           "complete-search-cache", *options, check=False)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(self.output.exists())

    def test_legacy_compile_and_connectivity_are_unchanged(self):
        original_scripts = self.root / "original_scripts"
        for name in (PURE, PR, "env.sh"):
            result = subprocess.run(["git", "show", f"{LEGACY_COMMIT}:scripts/{name}"],
                                    cwd=ROOT, check=True, capture_output=True, text=True)
            write(original_scripts / name, result.stdout)
        for script, algorithm in ((PURE, "weighted_sssp"), (PURE, "connected_components"),
                                  (PR, "full_pagerank"), (PR, "residual_pagerank")):
            with self.subTest(algorithm=algorithm):
                self.generate(script, algorithm, directory=original_scripts)
                names = ["compile_commands.sh", "link_command.sh"]
                if script == PR:
                    names.append("run_build.sh")
                files = [self.output / name for name in names]
                files += sorted((self.output / "config").glob("*.cfg"))
                before = {path: path.read_bytes() for path in files}
                self.generate(script, algorithm)
                self.assertEqual(before, {path: path.read_bytes() for path in files})


if __name__ == "__main__":
    unittest.main()
