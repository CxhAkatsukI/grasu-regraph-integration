"""Portable ABI, RTL matrix and immutable continuation contract tests."""

import copy
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from validation.grasu_complete import abi, analysis, commands, rtl_analysis, rtl_preparation


def cache_metadata(token=True):
    ports = '<port name="M_AXI_GMEM0" mode="master" dataWidth="512" portType="addressable"/>'
    ports += '<port name="S_AXI_CONTROL" mode="slave" dataWidth="32" portType="addressable"/>'
    args = '<arg id="0" name="pma_cache" port="M_AXI_GMEM0" addressQualifier="1" offset="0x10" size="8" hostSize="8"/>'
    buses, physical = [], []
    stimuli = [("update_stream", "slave", 96)] + ([("completion_token", "master", 32)] if token else [])
    for index, (name, mode, width) in enumerate(stimuli, 1):
        ports += f'<port name="{name.upper()}" mode="{"read_only" if mode == "slave" else "write_only"}" dataWidth="{width}" portType="stream"/>'
        args += f'<arg id="{index}" name="{name}" port="{name.upper()}" addressQualifier="4" offset="0" size="0" hostSize="8"/>'
        mappings = []
        for signal, bits in (("TDATA", width), ("TKEEP", width // 8), ("TSTRB", width // 8),
                             ("TLAST", 1), ("TVALID", 1), ("TREADY", 1)):
            direction = "out" if (mode == "master") != (signal == "TREADY") else "in"
            pname = name + "_" + signal
            physical.append(f'<s:port><s:name>{pname}</s:name><s:wire><s:direction>{direction}</s:direction>'
                            f'<s:vector><s:left>{bits-1}</s:left><s:right>0</s:right></s:vector></s:wire></s:port>')
            mappings.append(f'<s:portMap><s:logicalPort><s:name>{signal}</s:name></s:logicalPort>'
                            f'<s:physicalPort><s:name>{pname}</s:name></s:physicalPort></s:portMap>')
        buses.append(f'<s:busInterface><s:name>{name}</s:name><s:busType s:name="axis"/><s:{mode}/>'
                     f'<s:portMaps>{"".join(mappings)}</s:portMaps></s:busInterface>')
    kernel = f'<root><kernel name="process_cache" hwControlProtocol="ap_ctrl_chain"><ports>{ports}</ports><args>{args}</args></kernel></root>'
    component = (f'<s:component xmlns:s="{abi.search.NS["s"]}"><s:model><s:ports>{"".join(physical)}</s:ports></s:model>'
                 f'<s:busInterfaces>{"".join(buses)}</s:busInterfaces><s:memoryMaps><s:memoryMap><s:addressBlock>'
                 '<s:register><s:name>pma_cache_1</s:name><s:addressOffset>16</s:addressOffset><s:size>32</s:size></s:register>'
                 '</s:addressBlock></s:memoryMap></s:memoryMaps></s:component>')
    return {"kernel.xml": kernel.encode(), "component.xml": component.encode()}


class ProductionRtlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_plain_contract_removes_only_completion_port(self):
        token = cache_metadata()
        kernel, component = abi.cache.kernel(token["kernel.xml"]), abi.cache.component(token["component.xml"])
        plain = cache_metadata(False)
        result = abi.plain(plain, kernel, component)
        self.assertTrue(result["derived_plain_contract_pass"])
        self.assertFalse(result["matches_routed_cache_abi"])
        self.assertFalse(result["board_execution_admitted"])
        for member, before, after in (("kernel.xml", b'offset="0x10"', b'offset="0x20"'),
                                      ("kernel.xml", b'dataWidth="512"', b'dataWidth="256"'),
                                      ("kernel.xml", b'ap_ctrl_chain', b'ap_ctrl_hs'),
                                      ("component.xml", b'<s:left>95</s:left>', b'<s:left>63</s:left>'),
                                      ("component.xml", b'<s:addressOffset>16', b'<s:addressOffset>32'),
                                      ("component.xml", b'<s:slave/>', b'<s:master/>')):
            changed = copy.deepcopy(plain)
            changed[member] = changed[member].replace(before, after)
            with self.subTest(before=before), self.assertRaises(ValueError):
                abi.plain(changed, kernel, component)
        with self.assertRaises(ValueError):
            abi.plain(token, kernel, component)

    def test_xo_review_uses_canonical_members_and_exact_reference(self):
        reference = self.root / "reference"
        reference.mkdir()
        token = cache_metadata()
        for name, contents in token.items():
            (reference / name).write_bytes(contents)
        archive_path = self.root / "cache.xo"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr("process_cache/kernel.xml", token["kernel.xml"])
            archive.writestr("ip_repo/cache/component.xml", token["component.xml"])
            archive.writestr(".Xil/kernel.xml", "scratch")
        result = abi.review(archive_path, "cache-token", reference)
        self.assertTrue(result["matches_routed_cache_abi"])
        (reference / "kernel.xml").write_bytes(token["kernel.xml"].replace(b'offset="0x10"', b'offset="0x20"'))
        with self.assertRaises(ValueError):
            abi.review(archive_path, "cache-token", reference)

    def test_rtl_script_keeps_real_core_capacity_and_driver_header_selection(self):
        for variant in commands.VARIANTS:
            script = rtl_preparation.script(self.root / "source", variant)
            self.assertIn("create_clock -period 6.666666667", script)
            self.assertIn("config_rtl -deadlock_detection sim", script)
            self.assertIn("csim_design -ldflags {-pthread}", script)
            self.assertIn("cosim_design -rtl verilog -tool xsim", script)
            self.assertIn("-DGRASU_MAX_CACHE_SEGMENT=131072", script)
            self.assertNotIn("-I" + str(self.root / "source/vendor/include") + " ", script)
            self.assertNotIn("-D__SYNTHESIS__", script)
            self.assertNotIn("--allow-multiple-definition", script)
            self.assertEqual("-DGRASU_ENABLE_COMPLETION_TOKEN" in script, variant == "cache-token")
            self.assertNotIn("-DGRASU_SEARCH_HOST_HARNESS", script)
            self.assertEqual("-include " + str(self.root / "runner/search_host_config.hpp") in script,
                             variant == "search")
        with self.assertRaises(ValueError):
            rtl_preparation.script(self.root / "with space", "search")
        with self.assertRaises(ValueError):
            rtl_preparation.script(self.root, "bad")

    def test_host_preinclude_selects_harness_only_outside_synthesis(self):
        config = Path(rtl_preparation.__file__).parent / "fixtures/search_host_config.hpp"
        for synthesis in (False, True):
            argv = ["/usr/bin/c++", "-E", "-dM", "-x", "c++", "-include", str(config), "-"]
            if synthesis:
                argv.insert(1, "-D__SYNTHESIS__")
            result = subprocess.run(argv, input="", capture_output=True, text=True, check=True, timeout=10)
            definition = '#define GRASU_SEARCH_HOST_HARNESS "finite_host.hpp"'
            self.assertEqual(definition in result.stdout, not synthesis)

    def test_analysis_requires_full_oracle_and_rtl_transactions(self):
        directory = self.root / "candidate"
        solution = directory / "project/solution"
        for folder in ("csim/report", "sim/report/verilog"):
            (solution / folder).mkdir(parents=True)
        csim = solution / "csim/report/process_cache_csim.log"
        csim.write_text("".join(f"PRODUCTION_CACHE_PASS updates={count} conflict={conflict} capacity=131072 token=1\n"
                                for count, conflict in analysis.CACHE_ROWS))
        cosim = solution / "sim/report/process_cache_cosim.rpt"
        cosim.write_text("| Verilog | Pass |\n")
        transaction = solution / "sim/report/verilog/result.transaction.rpt"
        transaction.write_text("latency interval\n" + "".join(f"transaction {i}: {100+i} {99+i if i<5 else 'x'}\n" for i in range(6)))
        with patch.object(rtl_analysis.analysis, "exported", return_value={}), \
                patch.object(rtl_analysis.abi, "review", return_value={}), \
                patch.object(rtl_analysis.preparation, "pin", side_effect=lambda p: {"path": str(p)}):
            result = rtl_analysis.inspect(directory, "cache-token", self.root)
            self.assertTrue(result["rtl_validated"])
            self.assertEqual(len(result["transactions"]), 6)
            for key in ("external_RTL_backpressure_tested", "integrated_g_admitted", "routed",
                        "board_validated", "performance_matched"):
                self.assertFalse(result[key])
            cosim.write_text("| Verilog | Fail |\n")
            with self.assertRaises(ValueError):
                rtl_analysis.inspect(directory, "cache-token", self.root)
            cosim.write_text("| Verilog | Pass |\n")
            transaction.write_text("latency interval\ntransaction 0: 100 x\n")
            with self.assertRaises(ValueError):
                rtl_analysis.inspect(directory, "cache-token", self.root)


if __name__ == "__main__":
    unittest.main()
