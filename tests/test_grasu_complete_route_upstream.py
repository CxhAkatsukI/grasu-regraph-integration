"""Reusing upstream XOs requires source, compile flags and output identity."""

import copy
import csv
from pathlib import Path
import shlex
import tempfile
import unittest
import zipfile

from validation.grasu_complete.preparation import pin
from validation.grasu_complete.routing import upstream


class ReusedUpstreamTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.build, self.basis = self.root / "build", self.root / "basis"
        self.build.mkdir()
        (self.basis / "inputs").mkdir(parents=True)
        self.connected = {"sources": []}
        self.inputs, self.commands = [], []
        for name in ("kernel_config.h", *upstream.SOURCES.values()):
            source = self.build / name
            source.write_text("// " + name + "\n")
            self.inputs.append({"role": "kernel_source", "status": "present", **pin(source),
                                "bytes": source.stat().st_size})
            self.connected["sources"].append({"member": "upstream/" + name, **pin(source)})
        for kernel, name in upstream.SOURCES.items():
            xo = self.build / (kernel + ".hw.xo")
            with zipfile.ZipFile(xo, "w") as archive:
                archive.writestr(kernel + "/cpu_sources/" + name, (self.build / name).read_bytes())
            (self.basis / "inputs" / xo.name).write_bytes(xo.read_bytes())
            config = self.build / (kernel + "_compile.cfg")
            config.write_text("[hls]\n")
            defines = sorted(upstream.BASE_DEFINES)
            if kernel == "process_ddr":
                defines += ["-DGRASU_ENABLE_COMPLETION_TOKEN"]
            self.commands.append(["v++", "--compile", "--target", "hw", "--kernel_frequency", "150",
                                  *defines, "--config", str(config), "-o", str(xo), str(self.build / name)])
        self.write()

    def write(self):
        with (self.build / "inputs.tsv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=["role", "status", "sha256", "bytes", "path"],
                                    delimiter="\t")
            writer.writeheader()
            writer.writerows(self.inputs)
        (self.build / "compile_commands.sh").write_text("#!/bin/bash\n" + "\n".join(
            shlex.join(command) for command in self.commands) + "\n")

    def review(self):
        return upstream.review(self.build, self.basis, self.connected)

    def test_reused_xos_match_and_cpu_physical_limit_remains_explicit(self):
        report = self.review()
        self.assertEqual(set(report["kernels"]), {"dispatch", "process_ddr"})
        self.assertEqual(report["cold_axi_masters"], 4)
        self.assertEqual(report["connected_host_cold_axi_masters"], "not_modeled")
        self.assertNotIn("-DGRASU_SHARE_HBM_PORTS", report["kernels"]["process_ddr"]["defines"])

    def test_changed_or_duplicate_compile_flags_rejected(self):
        original = copy.deepcopy(self.commands)
        for flag in ("-DGRASU_SHARE_HBM_PORTS", "-DGRASU_PURE_PIPELINE_DIRECT_CACHE",
                     "-DGRASU_MAX_CACHE_SEGMENT=131072"):
            self.commands = copy.deepcopy(original)
            self.commands[1].insert(-1, flag)
            self.write()
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.review()

    def test_changed_target_clock_or_duplicate_compile_rejected(self):
        original = copy.deepcopy(self.commands)
        for flag, value in (("--target", "hw_emu"), ("--kernel_frequency", "200")):
            self.commands = copy.deepcopy(original)
            self.commands[0][self.commands[0].index(flag) + 1] = value
            self.write()
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.review()
        self.commands = [*original, original[0]]
        self.write()
        with self.assertRaises(ValueError):
            self.review()

    def test_missing_changed_or_duplicate_source_rejected(self):
        baseline = copy.deepcopy(self.inputs)
        for rows in (baseline[1:], [baseline[0], *baseline],
                     [{**baseline[0], "sha256": "0" * 64}, *baseline[1:]]):
            self.inputs = rows
            self.write()
            with self.assertRaises(ValueError):
                self.review()

    def test_changed_original_xo_and_embedded_source_rejected(self):
        xo = self.build / "dispatch.hw.xo"
        with zipfile.ZipFile(xo, "w") as archive:
            archive.writestr("dispatch/cpu_sources/kernel_dispatch.cpp", "changed\n")
        with self.assertRaisesRegex(ValueError, "original compilation"):
            self.review()
        (self.basis / "inputs" / xo.name).write_bytes(xo.read_bytes())
        with self.assertRaisesRegex(ValueError, "embedded source"):
            self.review()

    def test_live_source_and_declared_size_must_match(self):
        path = self.build / "kernel_config.h"
        original = path.read_text()
        path.write_text(original.replace("config", "CONFIG"))
        with self.assertRaisesRegex(ValueError, "historical upstream input"):
            self.review()
        path.write_text(original)
        self.inputs[0]["bytes"] += 1
        self.write()
        with self.assertRaisesRegex(ValueError, "historical upstream input"):
            self.review()


if __name__ == "__main__":
    unittest.main()
