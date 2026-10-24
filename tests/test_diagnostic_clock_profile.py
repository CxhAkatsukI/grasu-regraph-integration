"""A diagnostic run must neither hide clock changes nor claim timing signoff."""
import copy
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "scripts/check_diagnostic_clock_profile.py"
SPEC = importlib.util.spec_from_file_location("diagnostic_clock", PATH)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
ROWS = ("kernel:0:ulp_ucs/aclk_kernel_00:150.0\n"
        "kernel:1:ulp_ucs/aclk_kernel_01:500.0\n"
        "system::hbm_aclk:440.1\n")
TOPOLOGY = {"clock_freq_topology": {"m_count": "3", "m_clock_freq": [
    {"m_type": "SYSTEM", "m_name": "hbm_aclk", "m_freq_Mhz": "440"},
    {"m_type": "KERNEL", "m_name": "KERNEL_CLK", "m_freq_Mhz": "500"},
    {"m_type": "DATA", "m_name": "DATA_CLK", "m_freq_Mhz": "150"}]}}


class DiagnosticClockTests(unittest.TestCase):
    def test_explicit_profile_is_not_timing_signoff(self):
        result = CHECK.check(ROWS, TOPOLOGY, hbm_mhz=440.1)
        self.assertFalse(result["fixed_450mhz_signoff"])
        self.assertIn("NOT_TIMING_SIGNOFF", result["status"])
        self.assertEqual(result["compute_mhz"], 150)

    def test_changed_build_clock_missing_duplicate_and_nonfinite_reject(self):
        for text in (ROWS.replace("150.0", "149.0"), ROWS.replace("440.1", "450.0"),
                     ROWS.replace("440.1", "nan"), ROWS.splitlines()[0],
                     ROWS + ROWS.splitlines()[0] + "\n", ROWS + "\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CHECK.check(text, TOPOLOGY, hbm_mhz=440.1)

    def test_changed_packaged_clock_duplicate_and_count_reject(self):
        for change in ("frequency", "duplicate", "count"):
            topology = copy.deepcopy(TOPOLOGY)
            clock = topology["clock_freq_topology"]
            if change == "frequency":
                clock["m_clock_freq"][0]["m_freq_Mhz"] = "450"
            elif change == "duplicate":
                clock["m_clock_freq"][0] = clock["m_clock_freq"][1]
            else:
                clock["m_count"] = "2"
            with self.subTest(change=change), self.assertRaises(ValueError):
                CHECK.check(ROWS, topology, hbm_mhz=440.1)


if __name__ == "__main__":
    unittest.main()
