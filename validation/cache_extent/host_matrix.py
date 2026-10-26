"""Run the host-only follow-up without rehashing unrelated graphs per sample."""

import argparse
import copy
import json
from pathlib import Path

from . import matrix, matrix_inputs as inputs
from .delivery import BOUNDARY


def case_plan(plan, row, extra_pins):
    graphs = {item["graph"] for item in plan["workloads"]}
    selected = row["workload"]["graph"]
    if selected not in graphs or not any(pin["path"] == selected for pin in plan["pins"]):
        raise ValueError("current graph must belong to the fully pinned parent plan")
    scoped = copy.deepcopy(plan)
    pins = {}
    for pin in plan["pins"] + extra_pins:
        path = pin["path"]
        if path in graphs and path != selected:
            continue
        if path in pins:
            previous = pins[path]
            if previous["sha256"] != pin["sha256"] or (
                    "size" in previous and "size" in pin and previous["size"] != pin["size"]):
                raise ValueError("conflicting evidence pins: " + path)
            pins[path] = {**previous, **pin}
        else:
            pins[path] = pin
    scoped["pins"] = list(pins.values())
    return scoped


def run(plan_path, output):
    plan = json.loads(plan_path.read_text())
    expected = {(logical, dataset) for logical in inputs.ALGORITHMS.values() for dataset in inputs.DATASETS}
    keys = [(row["algorithm"], row["dataset"]) for row in plan["workloads"]]
    if len(keys) != 24 or set(keys) != expected or plan["boundary"] != BOUNDARY or \
            plan["repeats"] != {"warmup_pairs": 1, "measured_pairs": 3}:
        raise ValueError("complete frozen matrix and unchanged timing contract required")
    inputs.unchanged(plan["pins"])
    extra = [inputs.pin(plan_path), inputs.pin(__file__)]
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "RUNNING_FPGA_MATRIX", "plan": str(plan_path), "cases": [],
        "pin_policy": "all parent pins before/after; all non-workload pins and current graph per sample"}
    for algorithm, logical in inputs.ALGORITHMS.items():
        report["cases"] += [{"algorithm": algorithm, "dataset": row["dataset"],
            "status": "PENDING_ARTIFACTS", "workload": row}
            for row in plan["workloads"] if row["algorithm"] == logical]
    matrix.summarize(output, report)
    try:
        for algorithm in inputs.ALGORITHMS:
            rows = [row for row in report["cases"] if row["algorithm"] == algorithm]
            state, bits, pins = matrix.artifacts(plan, algorithm)
            if state != "ready":
                raise ValueError("host-only follow-up requires existing ready hardware: " + algorithm)
            blocked = False
            for row in rows:
                if blocked:
                    row["status"] = "BLOCKED_BY_FAILED_AU_GATE"
                    continue
                row["status"] = "RUNNING"
                matrix.summarize(output, report)
                try:
                    scoped = case_plan(plan, row, extra)
                    matrix.measure(scoped, row, bits, pins, output)
                except Exception as error:
                    row.update(status="FAILED_RETAINED", error=repr(error))
                blocked = row["dataset"] == "AU" and row["status"] != "RESIDENT_PAIR_PASS"
                matrix.summarize(output, report)
        inputs.unchanged(plan["pins"] + extra)
        report["status"] = "FPGA_MATRIX_PASS" if all(row["status"] == "RESIDENT_PAIR_PASS"
            for row in report["cases"]) else "FPGA_MATRIX_INCOMPLETE_RETAINED"
    except BaseException as error:
        report.update(status="VALIDATION_FAILED_RETAINED", error=repr(error))
        raise
    finally:
        matrix.summarize(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.plan.resolve(), args.output.resolve())
    print(report["status"], flush=True)
    if report["status"] != "FPGA_MATRIX_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
