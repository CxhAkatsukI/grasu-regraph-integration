"""Host optimization cannot silently change the workload or FPGA comparison."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from validation.cache_extent import host_followup as followup


class HostFollowupTest(unittest.TestCase):
    def fixture(self, root):
        old, new = root / "old.host", root / "new.host"
        old.write_text("old host")
        new.write_text("optimized host")
        prior = {"boundary": followup.BOUNDARY,
            "repeats": {"warmup_pairs": 1, "measured_pairs": 3},
            "pins": [followup.inputs.pin(old)],
            "spine_hosts": {key: str(old) for key in followup.inputs.ALGORITHMS},
            "gr_hosts": {key: str(old) for key in followup.inputs.ALGORITHMS},
            "spine_bits": {"sssp": "unchanged", "cc": "unchanged"},
            "memory_gib": {"AU": 16},
            "workloads": [{"algorithm": algorithm, "dataset": dataset, "batch_size": 8}
                for algorithm in followup.inputs.ALGORITHMS.values() for dataset in followup.inputs.DATASETS]}
        receipt = {"status": "DEFAULT_HOSTS_BUILT", "kernel_rebuilt": False,
                   "hosts": {key: str(new) for key in followup.SPECIALIZATIONS},
                   "pins": [followup.inputs.pin(new)]}
        paths = root / "prior.json", root / "build.json"
        for path, value in zip(paths, (prior, receipt)):
            path.write_text(json.dumps(value))
        return paths, prior, receipt

    def test_only_cc_pr_hosts_change_and_all_inputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, prior, _ = self.fixture(Path(directory))
            original = copy.deepcopy(prior)
            full = followup.derive(*paths, "full")
            for key in ("workloads", "gr_hosts", "spine_bits", "boundary", "repeats", "memory_gib"):
                self.assertEqual(full[key], prior[key])
            self.assertEqual(full["spine_hosts"]["sssp"], prior["spine_hosts"]["sssp"])
            self.assertNotEqual(full["spine_hosts"]["cc"], prior["spine_hosts"]["cc"])
            self.assertEqual(json.loads(paths[0].read_text()), original)
            gate = followup.derive(*paths, "au-gate")
            self.assertEqual([(row["algorithm"], row["dataset"]) for row in gate["workloads"]],
                             [("connected_components", "AU"), ("residual_pagerank", "AU")])

    def test_invalid_contract_or_changed_evidence_is_rejected(self):
        for mutation in ("boundary", "repeats", "duplicate", "build", "kernel", "hosts", "pin", "scope"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                paths, prior, receipt = self.fixture(Path(directory))
                scope = "full"
                if mutation == "boundary":
                    prior["boundary"] = "device_only"
                elif mutation == "repeats":
                    prior["repeats"]["measured_pairs"] = 1
                elif mutation == "duplicate":
                    prior["workloads"][-1] = prior["workloads"][0]
                elif mutation == "build":
                    receipt["status"] = "FAILED_RETAINED"
                elif mutation == "kernel":
                    receipt["kernel_rebuilt"] = True
                elif mutation == "hosts":
                    receipt["hosts"]["sssp"] = receipt["hosts"]["cc"]
                elif mutation == "pin":
                    Path(receipt["hosts"]["cc"]).write_text("changed")
                else:
                    scope = "fastest"
                for path, value in zip(paths, (prior, receipt)):
                    path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    followup.derive(*paths, scope)


if __name__ == "__main__":
    unittest.main()
