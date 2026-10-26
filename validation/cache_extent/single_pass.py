"""One resident FPGA pair per frozen workload, with no warmups or averaging."""

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import matrix_inputs as inputs
from .board import REPOSITORY


HOST_NAMES = {"sssp": "sharded_k4_sssp_native_host", "cc": "sharded_k4_cc_native_host",
              "respr": "sharded_k4_residual_pagerank_native_host"}


def save(output, report):
    buffer = io.StringIO()
    columns = ("algorithm", "dataset", "status", "gr_wall_ms", "spine_wall_ms",
               "speedup_gr_over_spine", "gr_rounds", "spine_rounds")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in report["cases"]:
        writer.writerow({key: row.get("summary", {}).get(key, row.get(key, "")) for key in columns})
    (output / "summary.csv").write_text(buffer.getvalue())
    report["passed_cases"] = sum(row["status"] == "RESIDENT_PAIR_PASS" for row in report["cases"])
    atomic_write_json(output / "results.json", report)


def inherited_pins(previous, key, config):
    manifest = json.loads((previous / key / "manifest.json").read_text())
    paths = {config[name] for name in ("graph", "gr_binary", "spine_binary", "spine_host")}
    selected = {}
    for pin in config["expected_pins"] + manifest["pins"]:
        if pin["path"] not in paths:
            continue
        old = selected.setdefault(pin["path"], pin)
        if old["sha256"] != pin["sha256"]:
            raise ValueError("conflicting prior artifact hashes: " + pin["path"])
    if set(selected) != paths:
        raise ValueError("previous execution lacks immutable artifact/input pins: " + key)
    return list(selected.values())


def recover_unstarted(output, report):
    for row in list(report["cases"]):
        if row["status"] != "RUNNING":
            continue
        key = row["algorithm"] + "-" + row["dataset"].lower()
        destination = output / key
        captured = json.loads((destination / "results.json").read_text())
        state = subprocess.run(["systemctl", "--user", "is-active", "--quiet",
                                output.name + "-" + key], check=False).returncode
        if state not in (3, 4) or captured.get("status") != "WAITING_FOR_FREE_BOARD_AND_MEMORY" or \
                captured.get("samples") != [] or captured.get("board_tested") is not False or \
                captured.get("current_sample") is not None or any(destination.glob("sample-*")):
            raise ValueError("refusing to repeat a possibly executed partial case: " + key)
        archive = output / "admission-interruptions" / key
        archive.mkdir(parents=True, exist_ok=False)
        destination.rename(archive / key)
        for suffix in (".json", ".driver.log"):
            (output / (key + suffix)).rename(archive / (key + suffix))
        report.setdefault("admission_interruptions", []).append(
            dict(row, archive=str(archive), reason="stopped_before_any_board_sample"))
        report["cases"].remove(row)
        save(output, report)


def run(previous, hosts, output, pythonpath, resume=False):
    if resume:
        report = json.loads((output / "results.json").read_text())
        if report["previous_matrix"] != str(previous) or report["measured_pairs"] != 1:
            raise ValueError("resume contract differs from existing campaign")
        recover_unstarted(output, report)
        completed = {row["algorithm"] + "-" + row["dataset"].lower() for row in report["cases"]}
    else:
        output.mkdir(parents=True, exist_ok=False)
        report = {"previous_matrix": str(previous), "warmup_pairs": 0,
                  "measured_pairs": 1, "aggregation": "none", "cases": []}
        completed = set()
    report["status"] = "RUNNING"
    source_paths = [REPOSITORY / relative for relative in (
        "tools/sharded_k4_native_host.cpp", "tools/sharded_k4_pagerank_native_host.cpp",
        "tools/sharded_cache_runtime.hpp", "include/weighted_pma_metadata_plan.hpp",
        "include/weighted_pma_runtime_plan.hpp", "validation/cache_extent/board.py",
        "validation/cache_extent/board_memory.py",
        "validation/cache_extent/single_pass.py")]
    sources = [inputs.pin(path) for path in source_paths]
    for algorithm in HOST_NAMES:
        for dataset in inputs.DATASETS:
            key = algorithm + "-" + dataset.lower()
            if key in completed:
                continue
            config = json.loads((previous / (key + ".json")).read_text())
            # Preserve exact graph and bitstream hashes, not obsolete host-source pins.
            pins = inherited_pins(previous, key, config)
            config.update(gr_host=str(hosts / algorithm / HOST_NAMES[algorithm]), single_pass=True,
                          expected_pins=pins + sources)
            config["expected_pins"].append(inputs.pin(Path(config["gr_host"])))
            config_path, destination = output / (key + ".json"), output / key
            atomic_write_json(config_path, config)
            row = {"algorithm": algorithm, "dataset": dataset, "status": "RUNNING",
                   "results": str(destination / "results.json")}
            report["cases"].append(row)
            save(output, report)
            budget = config["memory_gib"]
            argv = ["systemd-run", "--user", "--wait", "--pipe", "--collect",
                "--unit", output.name + "-" + key,
                "--property=MemoryMax=" + str(budget) + "G",
                "--property=MemoryHigh=" + str(budget - 2) + "G",
                "--property=MemorySwapMax=0", "--property=OOMPolicy=kill",
                "--property=KillMode=control-group", "/usr/bin/env", "PYTHONPATH=" + pythonpath,
                "/usr/bin/python3", "-m", "validation.cache_extent.board",
                "--config", str(config_path), "--output", str(destination)]
            print("RUNNING " + key, flush=True)
            try:
                with (output / (key + ".driver.log")).open("x") as log:
                    result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=7200)
                captured = json.loads((destination / "results.json").read_text())
                row.update(status=captured["status"], exit_code=result.returncode,
                           summary=captured.get("summary", {}))
                if result.returncode or not captured.get("board_tested"):
                    row["status"] = "FAILED_RETAINED"
                if "error" in captured:
                    row["error"] = captured["error"]
            except Exception as error:
                row.update(status="FAILED_RETAINED", error=repr(error))
            print(json.dumps(row, allow_nan=False), flush=True)
            save(output, report)
    report["status"] = "FPGA_SINGLE_PASS_COMPLETE" if report["passed_cases"] == 24 else "INCOMPLETE_RETAINED"
    save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--hosts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pythonpath", required=True)
    parser.add_argument("--resume", action="store_true", help="skip all previously attempted cases")
    args = parser.parse_args()
    print(run(args.previous, args.hosts, args.output, args.pythonpath, args.resume)["status"], flush=True)


if __name__ == "__main__":
    main()
