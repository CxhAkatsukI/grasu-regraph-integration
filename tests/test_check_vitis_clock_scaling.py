"""Clock metadata cannot silently turn a lower-frequency build into signoff."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_vitis_clock_scaling.py"
SPEC = importlib.util.spec_from_file_location("clock_check", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
ROWS = ("kernel:0:ulp_ucs/aclk_kernel_00:150.0\n"
        "kernel:1:ulp_ucs/aclk_kernel_01:500\n"
        "system::hbm_aclk:450.0\n")


class ClockScalingTests(unittest.TestCase):
    def check(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "_new_clk_freq"
            path.write_text(text, encoding="ascii")
            return CHECK.check(path)

    def test_all_original_clocks_required(self):
        result = self.check(ROWS)
        self.assertEqual(result["status"], "FIXED_CLOCK_METADATA_PASS_NOT_TIMING_OR_BOARD_TESTED")
        self.assertEqual(len(result["clocks"]), 3)
        self.assertEqual(len(result["source"]["sha256"]), 64)

    def test_reduction_or_increase_is_not_original_configuration(self):
        for old, new in (("450.0", "437.5"), ("150.0", "149.0"), ("450.0", "451.0")):
            with self.subTest(new=new):
                self.assertEqual(self.check(ROWS.replace(old, new))["status"],
                                 "CLOCK_CONFIGURATION_MISMATCH")

    def test_missing_duplicate_unknown_nonfinite_and_malformed_fail_closed(self):
        invalid = (ROWS.splitlines()[0], ROWS + ROWS.splitlines()[0] + "\n",
                   ROWS.replace("hbm_aclk", "other"), ROWS.replace("450.0", "nan"),
                   ROWS.replace("450.0", "inf"), ROWS.replace("450.0", "0"),
                   ROWS.replace("system::", "system:"), ROWS + "\n")
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.check(text)


if __name__ == "__main__":
    unittest.main()
