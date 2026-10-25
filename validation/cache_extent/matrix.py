"""Schedule the fixed 24-case FPGA matrix after its exact new artifacts route."""

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import time

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import matrix_inputs as inputs


def gate(path):
    report = json.loads(path.read_text()) if path.exists() else {}
    if report.get("status") == "FAILED_RETAINED":
        return "failed", report
    if report.get("status") != "ROUTED_NOT_BOARD_TESTED":
        return "waiting", report
    return "ready", report


def artifacts(plan, algorithm):
    root = Path(plan["build_root"])
    route_root = root / plan.get("route_directory", "route-v1")
    paths = [route_root / algorithm / "results.json"]
    if algorithm == "respr":
        paths.append(root / plan.get("spine_directory", "spine-respr-v1") / "results.json")
    states = [gate(path) for path in paths]
    if any(state == "failed" for state, _ in states):
        return "failed", {}, []
    if any(state != "ready" for state, _ in states):
        return "waiting", {}, []
    gr = states[0][1]
    gr_manifest = route_root / algorithm / "manifest.json"
    manifest = json.loads(gr_manifest.read_text())
    if manifest.get("abi", {}).get("status") != "CACHE_EXTENT_ABI_PASS":
        raise ValueError("only the new bounded-cache hardware is admitted")
    pins = list(manifest["pins"]) + [gr["xclbin"], inputs.pin(gr_manifest)]
    if algorithm == "respr":
        spine = states[1][1]
        pins += [spine["xclbin"], spine["provenance"]]
        spine_bit = spine["xclbin"]["path"]
    else:
        spine_bit = plan["spine_bits"][algorithm]["path"]
    pins += [inputs.pin(path) for path in paths]
    inputs.unchanged(pins)
    return "ready", {"gr_binary": gr["xclbin"]["path"], "spine_binary": spine_bit}, pins


def summarize(output, report):
    buffer = io.StringIO()
    columns = ("algorithm", "dataset", "status", "gr_ms", "spine_ms", "speedup", "results")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in report["cases"]:
        summary = row.get("summary", {})
        walls = summary.get("walls", {})
        writer.writerow({"algorithm": row["algorithm"], "dataset": row["dataset"],
            "status": row["status"], "results": row.get("results", ""),
            "gr_ms": walls.get("gr", {}).get("median_ms", ""),
            "spine_ms": walls.get("spine", {}).get("median_ms", ""),
            "speedup": summary.get("speedup_ratio_of_median_walls", "")})
    (output / "summary.csv").write_text(buffer.getvalue())
    report["passed_cases"] = sum(row["status"] == "RESIDENT_PAIR_PASS" for row in report["cases"])
    atomic_write_json(output / "results.json", report)


def measure(plan, row, bits, artifact_pins, output):
    key = row["algorithm"] + "-" + row["dataset"].lower()
    config_path, destination = output / (key + ".json"), output / key
    config = {**bits, "logical": inputs.ALGORITHMS[row["algorithm"]], "dataset": row["dataset"],
        "source": row["workload"]["source"], "graph": row["workload"]["graph"],
        "gr_host": plan["gr_hosts"][row["algorithm"]],
        "spine_host": plan["spine_hosts"][row["algorithm"]],
        "board_lock": plan["board_lock"], "memory_gib": plan["memory_gib"][row["dataset"]],
        "scope": "new_bounded_cache_G_plus_R_vs_current_Spine_resident_FPGA",
        "kernel_variant": "complete-search-cache-bounded",
        "expected_pins": plan["pins"] + artifact_pins}
    atomic_write_json(config_path, config)
    budget = config["memory_gib"]
    argv = ["systemd-run", "--user", "--wait", "--pipe", "--collect",
        "--unit", "gr-cache-matrix-" + output.name + "-" + key,
        "--property=MemoryMax=" + str(budget) + "G",
        "--property=MemoryHigh=" + str(budget - 2) + "G",
        "--property=MemorySwapMax=0", "--property=OOMPolicy=kill", "--property=KillMode=control-group",
        "/usr/bin/env", "PYTHONPATH=" + plan["runtime_pythonpath"], "/usr/bin/python3",
        "-m", "validation.cache_extent.board", "--config", str(config_path), "--output", str(destination)]
    with (output / (key + ".driver.log")).open("x") as log:
        result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=43200)
    path = destination / "results.json"
    captured = json.loads(path.read_text()) if path.exists() else {}
    row.update(results=str(path), driver_exit_code=result.returncode,
               status=captured.get("status", "FAILED_RETAINED"))
    if result.returncode or not captured.get("board_tested"):
        row["status"] = "FAILED_RETAINED"
    if row["status"] == "RESIDENT_PAIR_PASS":
        row["summary"] = captured["summary"]


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(args.plan.read_text())
    inputs.unchanged(plan["pins"])
    plan["pins"] += [inputs.pin(args.plan)]
    report = {"status": "WAITING_FOR_NEW_HARDWARE", "plan": str(args.plan), "cases": []}
    for algorithm, logical in inputs.ALGORITHMS.items():
        for row in plan["workloads"]:
            if row["algorithm"] == logical:
                report["cases"].append({"algorithm": algorithm, "dataset": row["dataset"],
                                         "status": "PENDING_ARTIFACTS", "workload": row})
    deadline = time.monotonic() + args.wait_seconds
    while any(row["status"] == "PENDING_ARTIFACTS" for row in report["cases"]):
        for algorithm in inputs.ALGORITHMS:
            remaining = [row for row in report["cases"] if row["algorithm"] == algorithm
                         and row["status"] == "PENDING_ARTIFACTS"]
            if not remaining:
                continue
            try:
                state, bits, pins = artifacts(plan, algorithm)
            except Exception as error:
                for row in remaining:
                    row.update(status="BLOCKED_BY_INVALID_ARTIFACT", error=repr(error))
                summarize(args.output, report)
                continue
            if state == "failed":
                for row in remaining:
                    row["status"] = "BLOCKED_BY_FAILED_BUILD"
            elif state == "ready":
                for row in remaining:
                    row["status"] = "RUNNING"
                    report["status"] = "RUNNING_FPGA_MATRIX"
                    summarize(args.output, report)
                    try:
                        measure(plan, row, bits, pins, args.output)
                    except Exception as error:
                        row.update(status="FAILED_RETAINED", error=repr(error))
                    summarize(args.output, report)
                    if row["dataset"] == "AU" and row["status"] != "RESIDENT_PAIR_PASS":
                        for other in remaining[1:]:
                            other["status"] = "BLOCKED_BY_FAILED_AU_GATE"
                        break
            summarize(args.output, report)
        if time.monotonic() >= deadline:
            for row in report["cases"]:
                if row["status"] == "PENDING_ARTIFACTS":
                    row["status"] = "TIMED_OUT_WAITING_FOR_BUILD"
            break
        if any(row["status"] == "PENDING_ARTIFACTS" for row in report["cases"]):
            report["status"] = "WAITING_FOR_REMAINING_HARDWARE"
            summarize(args.output, report)
            time.sleep(30)
    report["status"] = "FPGA_MATRIX_PASS" if all(row["status"] == "RESIDENT_PAIR_PASS"
        for row in report["cases"]) else "FPGA_MATRIX_INCOMPLETE_RETAINED"
    summarize(args.output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("prepare")
    for name in ("workloads", "sssp-reference", "spine-repository", "prior-root", "build-root", "output"):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--runtime-pythonpath", required=True)
    prepare.add_argument("--route-directory", default="route-v1")
    prepare.add_argument("--spine-directory", default="spine-respr-v1")
    execute = modes.add_parser("run")
    execute.add_argument("--plan", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--wait-seconds", type=int, default=259200)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    result = inputs.prepare(args) if args.mode == "prepare" else run(args)
    print(result.get("status", "MATRIX_FROZEN_NOT_BOARD_TESTED"), flush=True)


if __name__ == "__main__":
    main()
