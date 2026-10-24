"""Check repair sequencing and fail-closed guards without claiming FPGA evidence."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/optimize_routed_checkpoint.tcl"


@unittest.skipUnless(shutil.which("tclsh"), "tclsh required")
class RoutedRepairTests(unittest.TestCase):
    def invoke(self, root, *, version="2024.1", routed=1, collision=False,
               hbm_period="2.222222222222222", missing_clock=False):
        checkpoint = root / "input.dcp"
        checkpoint.touch()
        output = root / "candidate"
        output.mkdir()
        if collision:
            (output / "optimized_routed.dcp").touch()
        stub = root / "stub.tcl"
        stub.write_text(
            f"proc version {{args}} {{return {version}}}\n"
            f"proc report_route_status {{args}} {{puts [list ROUTE {{*}}$args]; return {routed}}}\n"
            "proc get_clocks {args} {\n"
            + ("  return {}\n" if missing_clock else "  return [lindex $args end]\n")
            + "}\n"
            "proc get_property {property clock} {\n"
            "  puts [list CLOCK $property $clock]\n"
            f"  if {{$clock eq \"hbm_aclk\"}} {{return {hbm_period}}}\n"
            "  if {$clock eq \"clk_kernel_00_unbuffered_net\"} {return 6.666666666666667}\n"
            "  return 2.0\n"
            "}\n"
            "foreach name {set_param open_checkpoint report_clocks report_timing_summary "
            "phys_opt_design report_bus_skew write_checkpoint close_design} {\n"
            "  proc $name {args} {puts [list CALL [lindex [info level 0] 0] {*}$args]}\n"
            "}\n"
            "set argv [lrange $argv 1 end]\n"
            "set argc [llength $argv]\n"
            f"source {{{SCRIPT}}}\n",
            encoding="ascii",
        )
        return subprocess.run(
            ["tclsh", str(stub), "stub", str(checkpoint), str(output)],
            text=True, capture_output=True, timeout=10, check=False,
        )

    def test_candidate_is_not_signoff(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.invoke(Path(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CALL phys_opt_design -directive ExploreWithHoldFix", result.stdout)
        self.assertIn("POST_ROUTE_CANDIDATE_WRITTEN_NOT_SIGNED_OFF", result.stdout)
        self.assertEqual(result.stdout.count("ROUTE -boolean_check ROUTED_FULLY"), 2)
        self.assertEqual(result.stdout.count("CLOCK PERIOD hbm_aclk"), 2)
        self.assertLess(result.stdout.index("timing_before.rpt"), result.stdout.index("CALL phys_opt_design"))
        self.assertLess(result.stdout.index("bus_skew_after.rpt"), result.stdout.index("CALL write_checkpoint"))
        self.assertNotIn("-force", result.stdout)

    def test_wrong_version_unrouted_and_overwrite_are_rejected(self):
        for options in ({"version": "2024.2"}, {"routed": 0}, {"collision": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.invoke(Path(directory), **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("CALL phys_opt_design", result.stdout)
                self.assertNotIn("CALL write_checkpoint", result.stdout)

    def test_changed_or_missing_clocks_are_rejected(self):
        for options in ({"hbm_period": "2.3"}, {"hbm_period": "nan"},
                        {"missing_clock": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.invoke(Path(directory), **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("CALL phys_opt_design", result.stdout)
                self.assertNotIn("CALL write_checkpoint", result.stdout)


if __name__ == "__main__":
    unittest.main()
