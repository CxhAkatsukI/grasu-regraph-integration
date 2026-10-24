"""Check the version-specific VIP repair without running vendor tools."""

from pathlib import Path
import subprocess
import tempfile
import unittest


REPAIR = Path(__file__).with_name("repair_cosim_axi_ids.tcl")


class CosimAxiIdsTests(unittest.TestCase):
    def fixture(self, root):
        folder = root / "unit_subsystem"
        folder.mkdir()
        (root / "svtb").mkdir()
        environment = folder / "unit_env.sv"
        environment.write_text("// Vitis HLS v2024.1\n" + "\n".join(
            f"axi_pkg::axi_env#(64,64,8,3,1) axi_master_{bundle};\n"
            f"unit_cfg.{bundle}_cfg.set_default();\n"
            f'axi_master_{bundle} = axi_pkg::axi_env#(64,64,8,3,1)::type_id::create("axi_master_{bundle}", this);'
            for bundle in ("even", "odd")))
        interfaces = root / "svtb/sv_module_top.sv"
        interfaces.write_text("\n".join(
            f"axi_if #(64,64,8,3,1) axi_{bundle}_if (.clk(clock));\n"
            f'uvm_config_db #( virtual axi_if#(64,64,8,3,1) )::set(null, "uvm_test_top.top_env.axi_master_{bundle}.*", "vif", axi_{bundle}_if);'
            for bundle in ("even", "odd")))
        dut = root / "unit.v"
        dut.write_text("parameter C_M_AXI_EVEN_ID_WIDTH = 2;\n"
                       "parameter C_M_AXI_ODD_ID_WIDTH = 1;\n")
        sequences = root / "svtb/unit_subsys_test_sequence_lib.sv"
        sequences.write_text("\n".join(
            f"axi_pkg::axi_slave_sequence#(64,64,8,3,1) axi_slave_{bundle}_seq;"
            for bundle in ("even", "odd")))
        return environment, interfaces, dut, sequences

    def repair(self, root):
        command = (f"source {{{REPAIR}}}\n"
                   f"if {{[catch {{repair_cosim_axi_ids {{{root}}} unit}} message]}} "
                   "{puts stderr $message; exit 1}\n")
        return subprocess.run(["tclsh"], input=command, text=True,
                              capture_output=True)

    def test_repairs_all_id_types_from_dut_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment, interfaces, dut, sequences = self.fixture(root)
            generated = (environment, interfaces, sequences)
            before = {path: path.read_text() for path in (*generated, dut)}
            result = self.repair(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for path in generated:
                self.assertEqual(Path(str(path) + ".before-id-fix").read_text(), before[path])
                expected_count = 1 if path == sequences else 2
                self.assertEqual(path.read_text().count("64,64,8,3,2"), expected_count)
                self.assertEqual(path.read_text().count("64,64,8,3,1"), expected_count)
            self.assertEqual(dut.read_text(), before[dut])
            self.assertIn("unit_cfg.even_cfg.id_num = 4;", environment.read_text())
            self.assertIn("unit_cfg.odd_cfg.id_num = 2;", environment.read_text())
            repaired = {path: path.read_text() for path in generated}
            result = self.repair(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refuse repeated", result.stderr)
            for path, content in repaired.items():
                self.assertEqual(path.read_text(), content)

    def test_unknown_templates_fail_without_mutation(self):
        mutations = (
            (0, "v2024.1", "v2025.1"),
            (2, "C_M_AXI_EVEN_ID_WIDTH", "UNKNOWN_WIDTH"),
            (2, "ID_WIDTH = 2", "ID_WIDTH = 5"),
            (1, "axi_even_if (.clk", "missing_if (.clk"),
            (0, "axi_master_even;", "unknown_master;"),
            (3, "axi_slave_even_seq;", "unknown_sequence;"),
        )
        for index, old, new in mutations:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                paths = self.fixture(root)
                paths[index].write_text(paths[index].read_text().replace(old, new))
                before = {path: path.read_text() for path in paths}
                result = self.repair(root)
                self.assertNotEqual(result.returncode, 0)
                for path, content in before.items():
                    self.assertEqual(path.read_text(), content)
                    self.assertFalse(Path(str(path) + ".before-id-fix").exists())


if __name__ == "__main__":
    unittest.main()
