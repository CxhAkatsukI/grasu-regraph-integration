"""Build existing optimized Spine hosts and derive an immutable follow-up plan."""

import argparse
import copy
import json
from pathlib import Path
import subprocess

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import matrix_inputs as inputs
from .delivery import BOUNDARY

SPECIALIZATIONS = {"cc": "connected_components", "respr": "thresholded_residual_pagerank"}
REGRESSION_PASS = "RESIDENT_BENCHMARK_HOST_TESTS_PASS scope=offboard_not_fpga"


def checked_regression(root):
    if (root / "decision.txt").read_text().strip() != REGRESSION_PASS:
        raise ValueError("four-specialization offboard regression required")
    for name in ("source-sha256.txt", "binary-sha256.txt"):
        subprocess.run(["sha256sum", "--check", str(root / name)],
                       check=True, capture_output=True, timeout=60)


def build(source, regression, output):
    checked_regression(regression)
    output.mkdir(parents=True, exist_ok=False)
    test_dir = source / "tests/test_integration"
    paths = [*source.glob("src/*.hpp"), *test_dir.glob("host_resident_benchmark*"),
             *(test_dir / name for name in ("host_partitioned_algorithms_smoke.cpp",
                "host_split.hpp", "xcl2.cpp", "xcl2.hpp", "Makefile"))]
    paths += [regression / name for name in ("decision.txt", "source-commit.txt",
              "source.patch", "source-sha256.txt", "binary-sha256.txt", "compiler.txt")]
    pins = [inputs.pin(path) for path in paths if path.is_file()]
    receipt = {"status": "BUILDING", "source": str(source), "regression": str(regression),
               "pins": pins, "hosts": {}, "commands": {}, "kernel_rebuilt": False}
    git = ["git", "-C", str(source)]
    receipt["source_commit"] = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    receipt["source_status"] = subprocess.check_output(git + ["status", "--porcelain"], text=True)
    if receipt["source_status"]:
        raise ValueError("build from the clean optimized source worktree")
    (output / "compiler.txt").write_text(subprocess.check_output(["g++", "--version"], text=True))
    try:
        for key, algorithm in SPECIALIZATIONS.items():
            host = output / (algorithm + ".host")
            command = ["make", "-B", "-C", str(test_dir), "TARGET=hw", "KERNEL_FREQ=150",
                "PAPER_ALIGNMENT=1", "MAX_N=16777216", "VS_PARTITION_SIZE=1048576",
                "MAX_SORT_N=131072", "EDGE_BUF_CHUNK_SIZE=33554432", "ALGORITHM=" + algorithm,
                "PARTITIONED_ALGORITHM_SMOKE=" + str(host), str(host)]
            receipt["commands"][key] = command
            with (output / (key + ".compile.log")).open("x") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
            receipt["hosts"][key] = str(host)
            pins.append(inputs.pin(host))
        pins.append(inputs.pin(output / "compiler.txt"))
        inputs.unchanged(pins)
        receipt["status"] = "DEFAULT_HOSTS_BUILT"
    except BaseException as error:
        receipt.update(status="FAILED_RETAINED", error=repr(error))
        raise
    finally:
        atomic_write_json(output / "build.json", receipt)
    return receipt


def derive(prior_path, build_path, scope):
    if scope not in ("au-gate", "full"):
        raise ValueError("unknown follow-up scope")
    prior = json.loads(prior_path.read_text())
    receipt = json.loads(build_path.read_text())
    if prior["boundary"] != BOUNDARY or prior["repeats"] != {"warmup_pairs": 1, "measured_pairs": 3}:
        raise ValueError("retain the resident wall boundary and repetition contract")
    expected = {(logical, dataset) for logical in inputs.ALGORITHMS.values() for dataset in inputs.DATASETS}
    keys = [(row["algorithm"], row["dataset"]) for row in prior["workloads"]]
    if len(keys) != 24 or set(keys) != expected:
        raise ValueError("parent must contain the complete frozen 24-case matrix")
    if receipt["status"] != "DEFAULT_HOSTS_BUILT" or receipt["kernel_rebuilt"] is not False or \
            set(receipt["hosts"]) != set(SPECIALIZATIONS):
        raise ValueError("only the two verified host replacements are admitted")
    inputs.unchanged(prior["pins"] + receipt["pins"])
    for path in receipt["hosts"].values():
        if inputs.pin(path) not in receipt["pins"]:
            raise ValueError("replacement executable is not pinned")
    plan = copy.deepcopy(prior)
    plan["spine_hosts"].update(receipt["hosts"])
    plan["pins"] += receipt["pins"] + [inputs.pin(prior_path), inputs.pin(build_path), inputs.pin(__file__)]
    plan["host_followup"] = {"parent_plan": str(prior_path), "build": str(build_path),
        "scope": scope, "changes": "CC/ResPR host scratch handling only; no HLS or boundary changes"}
    if scope == "au-gate":
        plan["workloads"] = [row for row in plan["workloads"] if row["dataset"] == "AU"
                             and row["algorithm"] in ("connected_components", "residual_pagerank")]
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    compile_host = modes.add_parser("build")
    for name in ("source", "regression", "output"):
        compile_host.add_argument("--" + name, type=Path, required=True)
    prepare = modes.add_parser("prepare")
    for name in ("prior", "build", "output"):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--scope", choices=("au-gate", "full"), required=True)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, key, value.resolve())
    if args.mode == "build":
        result = build(args.source, args.regression, args.output)
    else:
        result = derive(args.prior, args.build, args.scope)
        args.output.mkdir(parents=True, exist_ok=False)
        atomic_write_json(args.output / "plan.json", result)
    print(result.get("status", "HOST_FOLLOWUP_FROZEN_NOT_BOARD_TESTED"), flush=True)


if __name__ == "__main__":
    main()
