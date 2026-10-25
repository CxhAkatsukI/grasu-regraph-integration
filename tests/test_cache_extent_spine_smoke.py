"""The standalone Spine smoke cannot admit a different workload or failed log."""

import unittest

from validation.cache_extent import spine_smoke


class SpineSmokeTests(unittest.TestCase):
    workload = {"source": 0, "vertices": 515281, "updates": 8}
    text = ("SPINE_RESIDENT_BENCHMARK_PASS algorithm=2 source=0 vertices=515281 "
            "iterations=4 logical_updates=8 physical_updates=8 "
            "boundary=resident_update_to_final_readback_wall_including_host_relaunch "
            "wall_ms=10.25 final_validation=outside_wall full_state_readback=each_round "
            "host_correction_included=1\n")

    def test_exact_resident_result_is_accepted(self):
        result = spine_smoke.accepted_result(self.text, self.workload)
        self.assertEqual(result["wall_ms"], 10.25)

    def test_wrong_semantics_or_counts_are_rejected(self):
        mutations = {"algorithm=2": "algorithm=0", "source=0": "source=1",
            "vertices=515281": "vertices=500", "logical_updates=8": "logical_updates=1",
            "physical_updates=8": "physical_updates=16", "iterations=4": "iterations=-1",
            "final_validation=outside_wall": "final_validation=missing",
            "full_state_readback=each_round": "full_state_readback=absent",
            "host_correction_included=1": "host_correction_included=0"}
        for original, changed in mutations.items():
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                spine_smoke.accepted_result(self.text.replace(original, changed), self.workload)

    def test_missing_duplicate_and_invalid_wall_are_rejected(self):
        for text in ("", self.text * 2, *(self.text.replace("10.25", value)
                                        for value in ("0", "-1", "nan", "inf"))):
            with self.subTest(text=text), self.assertRaises(ValueError):
                spine_smoke.accepted_result(text, self.workload)


if __name__ == "__main__":
    unittest.main()
