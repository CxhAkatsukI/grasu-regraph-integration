"""Portable delivery must not turn controls, pending rows or altered logs into wins."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from validation.cache_extent import delivery
from test_compare_resident_fpga_logs import fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def study(root):
    path = root / "matrix/results.json"
    rows = [{"algorithm": algorithm, "dataset": dataset, "status": "BLOCKED_BY_FAILED_BUILD",
             "workload": {"algorithm": logical, "dataset": dataset, "source": 0,
                          "graph": str(root / "graph"), "batch_size": 8,
                          "updates": 16 if algorithm == "cc" else 8}}
            for algorithm, logical in delivery.ALGORITHMS.items() for dataset in delivery.DATASETS]
    report = {"status": "FPGA_MATRIX_INCOMPLETE_RETAINED", "passed_cases": 0,
              "cases": rows, "plan": str(root / "plan.json")}
    plan = {"boundary": delivery.BOUNDARY, "repeats": {"warmup_pairs": 1, "measured_pairs": 3},
            "pins": [], "workloads": [row["workload"] for row in rows]}
    write(path, report)
    write(root / "plan.json", plan)
    return path, report, plan


def passing(root, report, plan, algorithm="sssp", records=None):
    path = root / ("matrix/" + algorithm + "-au/results.json")
    row = next(row for row in report["cases"] if row["algorithm"] == algorithm and row["dataset"] == "AU")
    logical = row["workload"]["algorithm"]
    records = row["workload"]["updates"] if records is None else records
    config = {"logical": logical, "dataset": "AU", "source": 0,
              "kernel_variant": "complete-search-cache-bounded"}
    pins = []
    for key in ("gr_host", "spine_host", "gr_binary", "spine_binary", "graph"):
        pinned = root / key
        pinned.write_text("test artifact " + key)
        config[key] = str(pinned)
        pins.append({"path": str(pinned), "sha256": hashlib.sha256(pinned.read_bytes()).hexdigest()})
    parser, samples = delivery.log_parser(), []
    for index in range(4):
        gr, spine = [text.replace("logical_updates=1", f"logical_updates={records}")
                     .replace("physical_updates=1", f"physical_updates={records}") for text in fixture(logical)]
        directory = path.parent / ("sample-" + str(index))
        (directory / "gr").mkdir(parents=True)
        (directory / "gr/run.log").write_text(gr)
        (directory / "spine.stdout.txt").write_text(spine)
        samples.append({"sample_index": index, "warmup": index == 0,
            "order": ["gr", "spine"] if index % 2 == 0 else ["spine", "gr"],
            "pair": parser.compare(logical, gr, spine, 0),
            "resources": {name: {"exit_code": 0, "stop_reason": "process_exit",
                                 "cleanup_snapshot_error": None} for name in ("gr", "spine")}})
    clocks = {name: [{"m_type": "DATA", "m_freq_Mhz": "140" if name == "gr" else "150"}]
              for name in ("gr", "spine")}
    captured = {"status": "RESIDENT_PAIR_PASS", "board_tested": True, "config": config,
        "boundary": delivery.BOUNDARY, "clocks": clocks, "samples": samples,
        "summary": parser.summarize(samples)}
    write(path, captured)
    write(path.with_name("manifest.json"), {"config": config, "boundary": delivery.BOUNDARY,
                                            "clocks": clocks, "pins": pins})
    for name in clocks:
        write(path.with_name(name + "-clocks.json"), {"clock_freq_topology": {"m_clock_freq": clocks[name]}})
    row.update(status="RESIDENT_PAIR_PASS", results=str(path), summary=captured["summary"])
    report["passed_cases"] = 1
    write(root / "matrix/results.json", report)
    return path, captured


class DeliveryTest(unittest.TestCase):
    def test_failures_are_retained_without_fabricated_ratios(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _ = study(root)
            output = root / "delivery"
            result = delivery.package(path, output)
            with (output / "summary.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(result["passed_cases"], 0)
            self.assertEqual(len(rows), 24)
            self.assertTrue(all(row["speedup_gr_over_spine"] == "" for row in rows))
            self.assertIn("0/24", (output / "README.md").read_text())
            with self.assertRaises(ValueError):
                delivery.package(path, output)

    def test_unfinished_duplicate_or_miscounted_matrix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, report, _ = study(root)
            for mutation in ("running", "duplicate", "pending", "count", "false_pass"):
                changed = copy.deepcopy(report)
                if mutation == "running":
                    changed["status"] = "WAITING_FOR_REMAINING_HARDWARE"
                elif mutation == "duplicate":
                    changed["cases"][-1] = changed["cases"][0]
                elif mutation == "pending":
                    changed["cases"][0]["status"] = "PENDING_ARTIFACTS"
                elif mutation == "count":
                    changed["passed_cases"] = 24
                else:
                    changed["status"] = "FPGA_MATRIX_PASS"
                write(path, changed)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    delivery.inspect(path)

    def test_raw_logs_are_reparsed_and_actual_frequencies_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, report, plan = study(root)
            passing(root, report, plan)
            output = root / "delivery"
            delivery.package(path, output)
            with (output / "summary.csv").open() as stream:
                first = next(csv.DictReader(stream))
            self.assertEqual(first["speedup_gr_over_spine"], "3.0")
            self.assertEqual((first["gr_data_mhz"], first["spine_data_mhz"]), ("140", "150"))
            raw = output / "cases/sssp-au/sample-1/gr/run.log"
            self.assertTrue(raw.is_file())
            self.assertTrue(any(item["path"].endswith("sample-1/gr/run.log")
                                for item in delivery.read(output / "files.json")))

    def test_batch_size_and_raw_record_counts_are_distinct_for_cc(self):
        for algorithm, records in (("sssp", 8), ("cc", 16), ("respr", 8)):
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, report, plan = study(root)
                passing(root, report, plan, algorithm)
                output = root / "delivery"
                delivery.package(path, output)
                with (output / "summary.csv").open() as stream:
                    measured = next(row for row in csv.DictReader(stream) if row["status"] == "RESIDENT_PAIR_PASS")
                self.assertEqual(measured["batch_size"], "8")
                self.assertEqual(measured["input_update_records"], str(records))
                self.assertEqual(measured["logical_updates"], str(records))
                self.assertEqual(measured["physical_updates"], str(records))
                self.assertIn("sixteen reciprocal", (output / "README.md").read_text())

    def test_matching_raw_logs_cannot_override_the_frozen_record_count(self):
        for algorithm, records in (("sssp", 16), ("cc", 8), ("respr", 16)):
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, report, plan = study(root)
                passing(root, report, plan, algorithm, records)
                with self.assertRaisesRegex(ValueError, "input-record count"):
                    delivery.package(path, root / "delivery")
                self.assertFalse((root / "delivery").exists())

    def test_frozen_contract_does_not_allow_arbitrary_batch_or_record_counts(self):
        for field, value in (("batch_size", 4), ("updates", 15)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, report, plan = study(root)
                row = next(row for row in report["cases"] if row["algorithm"] == "cc" and row["dataset"] == "AU")
                row["workload"][field] = value
                write(root / "plan.json", plan)
                passing(root, report, plan, "cc")
                with self.assertRaisesRegex(ValueError, "eight batch edits"):
                    delivery.package(path, root / "delivery")

    def test_bad_pair_evidence_is_not_exported_as_hardware_success(self):
        for mutation in ("control", "sample", "summary", "log", "pin", "clock", "resources"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                matrix_path, report, plan = study(root)
                path, captured = passing(root, report, plan)
                if mutation == "control":
                    captured["config"]["kernel_variant"] = "legacy_full_cache"
                elif mutation == "sample":
                    captured["samples"][1]["warmup"] = True
                elif mutation == "summary":
                    captured["summary"]["speedup_ratio_of_median_walls"] = 3000
                elif mutation == "log":
                    raw = path.parent / "sample-1/gr/run.log"
                    raw.write_text(raw.read_text().replace("mismatches=0", "mismatches=1"))
                elif mutation == "pin":
                    Path(captured["config"]["gr_binary"]).write_text("different bitstream")
                elif mutation == "clock":
                    write(path.with_name("gr-clocks.json"), {"clock_freq_topology": {"m_clock_freq": []}})
                else:
                    captured["samples"][0]["resources"] = {}
                write(path, captured)
                with self.assertRaises(ValueError):
                    delivery.package(matrix_path, root / "delivery")
                self.assertFalse((root / "delivery").exists())


if __name__ == "__main__":
    unittest.main()
