import importlib.util
import copy
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "resident_logs", Path(__file__).resolve().parents[1] /
    "scripts/compare_resident_fpga_logs.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(algorithm):
    kind, prefix = MODULE.PROFILES[algorithm]
    shared = "vertices=8 logical_updates=1 physical_updates=1"
    gr = (f"GRASU_SHARDED_UPDATE_REPEAT_CONFIG repeats=1\n"
          f"{prefix}_RESULT status=PASS hardware_converged=1 oracle_converged=1 "
          f"resident_state=old_graph_converged conversion_cost=absent "
          f"k4_frontends=4 shared_regraph_downstream=1 {shared} ")
    if kind == 2:
        gr += ("rank_mismatches=0 degree_mismatches=0 rank_nonfinite=0 "
               "threshold_semantics=direct_per_vertex epsilon=0.000001 "
               "rank_error_l1=0.000001 rank_expected_l1=1.000000 "
               "rank_error_l1_limit=0.001100 propagation_rounds=3\n")
    else:
        gr += "mismatches=0 source_external=0 executed_supersteps=2\n"
    gr += f"{prefix}_TIMING event_e2e_ms=0.01 setup_inclusive_ms=30\n"
    spine = (f"SPINE_RESIDENT_BENCHMARK_PASS algorithm={kind} {shared} "
             f"source=0 iterations=3 boundary={MODULE.BOUNDARY} wall_ms=10 "
             f"final_validation=outside_wall full_state_readback=each_round "
             f"host_correction_included={int(kind == 2)}\n")
    return gr, spine


class ResidentLogComparisonTest(unittest.TestCase):
    def test_repeated_summary_uses_ratio_of_medians_not_best_pair(self):
        pair = MODULE.compare("weighted_sssp", *fixture("weighted_sssp"), source=0)
        samples = []
        for index, (gr, spine) in enumerate(((1, 1000), (20, 10), (30, 1), (100, 20))):
            row = dict(pair, gr_wall_ms=gr, spine_wall_ms=spine)
            samples.append(dict(sample_index=index, warmup=index == 0, pair=row))
        summary = MODULE.summarize(samples)
        self.assertEqual(summary["walls"]["gr"]["samples_ms"], [20, 30, 100])
        self.assertEqual(summary["speedup_ratio_of_median_walls"], 3)
        for mutation in ("too_few", "second_warmup", "out_of_order", "mixed", "nan"):
            invalid = copy.deepcopy(samples)
            if mutation == "too_few":
                invalid.pop()
            elif mutation == "second_warmup":
                invalid[1]["warmup"] = True
            elif mutation == "out_of_order":
                invalid[1]["sample_index"] = 2
            elif mutation == "mixed":
                invalid[1]["pair"]["vertices"] = 9
            else:
                invalid[1]["pair"]["spine_wall_ms"] = float("nan")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                MODULE.summarize(invalid)

    def test_three_algorithms_use_continuous_wall(self):
        for algorithm in MODULE.PROFILES:
            with self.subTest(algorithm=algorithm):
                result = MODULE.compare(algorithm, *fixture(algorithm), source=0)
                self.assertEqual(result["speedup_gr_over_spine"], 3.0)
                self.assertEqual(result["gr_wall_ms"], 30.0)

    def test_bad_or_ambiguous_integer_logs_rejected(self):
        gr, spine = fixture("weighted_sssp")
        mutations = (
            (gr.replace("hardware_converged=1", "hardware_converged=0"), spine),
            (gr.replace("oracle_converged=1", "oracle_converged=0"), spine),
            (gr.replace("old_graph_converged", "cold_fallback"), spine),
            (gr.replace("repeats=1", "repeats=10"), spine),
            (gr.replace("mismatches=0", "mismatches=1"), spine),
            (gr.replace("vertices=8", "vertices=9"), spine),
            (gr.replace("physical_updates=1", "physical_updates=0"), spine),
            (gr.replace("source_external=0", "source_external=11"), spine),
            (gr.replace("k4_frontends=4", "k4_frontends=1"), spine),
            (gr.replace("setup_inclusive_ms=30", "setup_inclusive_ms=nan"), spine),
            (gr.replace("setup_inclusive_ms=30", "setup_inclusive_ms=inf"), spine),
            (gr, spine.replace("wall_ms=10", "wall_ms=0")),
            (gr, spine.replace("algorithm=0", "algorithm=1")),
            (gr, spine.replace(MODULE.BOUNDARY, "device_only")),
            (gr, spine.replace("outside_wall", "inside_wall")),
            (gr, spine.replace("host_correction_included=0", "host_correction_included=1")),
            (gr, spine + spine),
            (gr, spine.replace("wall_ms=10", "wall_ms=10 wall_ms=20")),
        )
        for index, pair in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                MODULE.compare("weighted_sssp", *pair, source=0)

    def test_pr_threshold_and_aggregate_guard_rejected(self):
        gr, spine = fixture("residual_pagerank")
        for before, after in (
            ("epsilon=0.000001", "epsilon=0.000000125"),
            ("rank_error_l1=0.000001", "rank_error_l1=0.001200"),
            ("rank_expected_l1=1.000000", "rank_expected_l1=nan"),
            ("rank_error_l1_limit=0.001100", "rank_error_l1_limit=1.000000"),
            ("rank_nonfinite=0", "rank_nonfinite=1"),
            ("direct_per_vertex", "divide_by_vertices"),
        ):
            with self.subTest(before=before), self.assertRaises(ValueError):
                MODULE.compare("residual_pagerank", gr.replace(before, after), spine, 0)
        with self.assertRaises(ValueError):
            MODULE.compare("residual_pagerank", gr,
                           spine.replace("host_correction_included=1",
                                         "host_correction_included=0"), 0)


if __name__ == "__main__":
    unittest.main()
