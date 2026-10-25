"""Freeze the complete resident workload matrix without silently changing inputs."""

import hashlib
import json
from pathlib import Path
import subprocess

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json

DATASETS = ("AU", "SU", "WK", "SO", "PK", "LJ", "LJ08", "R19")
ALGORITHMS = {"sssp": "weighted_sssp", "cc": "connected_components",
              "respr": "residual_pagerank"}
GIB_BUDGETS = {"AU": 16, "SU": 16, "WK": 16, "SO": 32,
               "PK": 24, "LJ": 32, "LJ08": 32, "R19": 16}


def pin(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest}


def unchanged(pins):
    for row in pins:
        if pin(row["path"])["sha256"] != row["sha256"]:
            raise ValueError("matrix input changed: " + row["path"])


def workloads(manifest):
    rows = json.loads(manifest.read_text())["records"]
    expected = {(algorithm, dataset) for algorithm in ALGORITHMS.values() for dataset in DATASETS}
    keys = [(row["algorithm"], row["dataset"]) for row in rows]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("exactly three algorithms by eight datasets required")
    if any(row["batch_size"] != 8 or row["updates"] <= 0 for row in rows):
        raise ValueError("the frozen insertion-eight logical batches are required")
    return sorted(rows, key=lambda row: (list(ALGORITHMS.values()).index(row["algorithm"]),
                                        DATASETS.index(row["dataset"])))


def cc_evidence(repository, output):
    evidence = repository / "docs/evidence/paper_owner_fifo_cc_routed_v1.json"
    row = json.loads(evidence.read_text())["algorithms"]["cc"]
    binary = pin(row["xclbin"])
    if binary["sha256"] != row["xclbin_sha256"]:
        raise ValueError("CC bitstream differs from routed evidence")
    recorded = row["build_provenance"]
    provenance = Path(recorded["path"])
    if pin(provenance)["sha256"] != recorded["sha256"]:
        raise ValueError("CC build provenance changed")
    build = json.loads(provenance.read_text())
    if build["git_dirty"] is not False or build["git_commit"] != recorded["git_commit"]:
        raise ValueError("clean CC build identity required")
    prefix = ["git", "-C", str(repository)]
    if subprocess.check_output(prefix + ["status", "--porcelain", "--untracked-files=no", "--", "src"],
                               text=True, timeout=30):
        raise ValueError("dirty Spine kernel source")
    changed = subprocess.check_output(prefix + ["diff", "--name-only", build["git_commit"],
                                               "HEAD", "--", "src"], text=True, timeout=30)
    allowed = {"src/spine_pagerank_compute.hpp", "src/spine_residual_apply_bitmap.hpp"}
    if not set(changed.splitlines()) <= allowed:
        raise ValueError("CC source equivalence no longer holds")
    patch = subprocess.check_output(prefix + ["diff", build["git_commit"], "HEAD", "--", "src"],
                                   text=True, timeout=30)
    path = output / "spine-cc-source-difference.patch"
    path.write_text(patch)
    paths = [evidence, provenance, path, *(repository / "src").glob("*.hpp")]
    return binary, [pin(path) for path in paths]


def prepare(args):
    args.output.mkdir(parents=True, exist_ok=False)
    rows = workloads(args.workloads)
    prior = json.loads(args.sssp_reference.read_text())
    unchanged(prior["pins"])
    spine_bits = [row for row in prior["pins"] if Path(row["path"]).suffix == ".xclbin"
                  and Path(row["path"]).name.startswith("spine_")]
    if len(spine_bits) != 1:
        raise ValueError("one previously tested SSSP bitstream required")
    cc_bit, cc_pins = cc_evidence(args.spine_repository, args.output)
    host_root = args.prior_root / "spine-resident-host-v7"
    if (host_root / "decision.txt").read_text().strip() != \
            "RESIDENT_BENCHMARK_HOST_TESTS_PASS scope=offboard_not_fpga":
        raise ValueError("Spine resident host regression gate failed")
    subprocess.run(["sha256sum", "--check", str(host_root / "binary-sha256.txt")],
                   check=True, capture_output=True, timeout=30)
    spine_hosts = {"sssp": prior["options"]["host"],
        "cc": str(host_root / "connected_components.host"),
        "respr": str(host_root / "thresholded_residual_pagerank.host")}
    host_algorithms = {"sssp": "sssp", "cc": "cc", "respr": "residual_pagerank"}
    gr_hosts = {key: str(args.build_root / "hosts" / key /
                        ("sharded_k4_" + host_algorithms[key] + "_native_host"))
                for key in ALGORITHMS}
    pins = prior["pins"] + cc_pins
    paths = [args.workloads, args.sssp_reference, *Path(__file__).parent.glob("*.py")]
    paths += [Path(value) for value in (*spine_hosts.values(), *gr_hosts.values())]
    paths += [host_root / name for name in ("decision.txt", "source-commit.txt", "source-sha256.txt",
                                          "source.patch", "binary-sha256.txt", "compiler.txt")]
    for row in rows:
        graph = pin(row["graph"])
        if graph["sha256"] != row["sha256"]:
            raise ValueError("workload hash mismatch: " + row["graph"])
        pins.append(graph)
    pins += [pin(path) for path in paths]
    plan = {"schema": 1, "workloads": rows, "pins": pins, "build_root": str(args.build_root),
        "route_directory": args.route_directory, "spine_directory": args.spine_directory,
        "gr_hosts": gr_hosts, "spine_hosts": spine_hosts,
        "spine_bits": {"sssp": spine_bits[0], "cc": cc_bit}, "memory_gib": GIB_BUDGETS,
        "board_lock": str(args.prior_root / "board-device-one.lock"),
        "runtime_pythonpath": args.runtime_pythonpath,
        "boundary": "resident_update_to_final_readback_wall_including_host_relaunch",
        "repeats": {"warmup_pairs": 1, "measured_pairs": 3},
        "initial_state": "same converged old graph; one update batch to new convergence",
        "failure_policy": "retain failures; failed AU gate blocks remaining algorithm; no old-data substitution"}
    atomic_write_json(args.output / "plan.json", plan)
    return plan
