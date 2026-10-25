"""Build the missing sparse-ResPR Spine independently of unrelated board gates."""

import argparse
import json
from pathlib import Path
import subprocess

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware import concurrent
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.containment import current
from validation.grasu_complete import preparation, runtime
from .route import GIB, verify


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    group = current()
    concurrent.verify = verify
    guard = verify(group, memory_gib=args.memory_gib)
    if int(guard["limits"]["memory.max"]) != args.memory_gib * GIB or \
            int(guard["limits"]["memory.high"]) > (args.memory_gib - 4) * GIB:
        raise ValueError("declared hard cap and at least 4-GiB high-watermark margin required")
    report = {"status": "PREPARING", "board_tested": False, "steps": [],
              "containment": guard, "pins": [], "residual_sparse_apply": 1,
              "policy": {"tree_memory_gib": args.memory_gib, "reserve_gib": 24, "allow_bounded_builds": True}}
    save = lambda: atomic_write_json(args.output / "results.json", report)
    lease = concurrent.Lease(Path.home() / ".cache/spine-cycle-sim/compiler-reservations", group)
    try:
        names = subprocess.check_output(["git", "-C", str(args.repository), "ls-files", "-z", "--",
            "src", "tests/test_integration/Makefile", "tests/test_integration/*.cfg",
            "tests/test_integration/*.tcl", "tests/test_integration/build_partitioned_algorithms.sh"],
            text=True, timeout=30)
        paths = [args.repository / name for name in names.split("\0") if name]
        build = args.repository / "tests/test_integration/build_partitioned_algorithms.sh"
        if build not in paths or not any(path.suffix == ".hpp" for path in paths):
            raise ValueError("missing kernel/build inputs")
        dirty = subprocess.check_output(["git", "-C", str(args.repository), "status", "--porcelain",
                                          "--untracked-files=no", "--", "src"], text=True, timeout=30)
        if dirty:
            raise ValueError("kernel sources must be committed before freezing")
        report["pins"] = [preparation.pin(path) for path in
            (*paths, Path(__file__), Path(__file__).with_name("route.py"), args.settings)]
        argv = ["bash", str(build), "hw", str(args.output / "build"), "respr"]
        manifest = {"pins": report["pins"], "command": argv, "selector": "SPINE_RESIDUAL_SPARSE_APPLY=1",
            "source_commit": subprocess.check_output(["git", "-C", str(args.repository), "rev-parse", "HEAD"],
                                                     text=True, timeout=30).strip(),
            "policy": report["policy"], "queue_gate": "finite memory admission only",
            "acceptance": "routed artifact, not board correctness or speedup"}
        atomic_write_json(args.output / "manifest.json", manifest)
        report["pins"].append(preparation.pin(args.output / "manifest.json"))
        environment = runtime.environment(args.output)
        environment.update(SPINE_RESIDUAL_SPARSE_APPLY="1", SPINE_BUILD_JOBS="1",
            SPINE_BUILD_MIN_AVAILABLE_GIB=str(args.memory_gib + 24), SPINE_VITIS_SETTINGS=str(args.settings),
            VIVADO_SYNTH_JOBS="1", VIVADO_IMPL_JOBS="1")
        runtime.admit(report, args.output, lease, args.wait_seconds)
        runtime.execute(report, args.output, args.output, "spine-respr", "compile-route",
                        argv, 86400, environment)
        binary = args.output / "build/respr/xclbin/spine_partitioned_split_e2e.respr.hw.xclbin"
        provenance = args.output / "build/respr/build_provenance.json"
        built = json.loads(provenance.read_text())
        if built["target"] != "hw" or built["algorithm"] != "thresholded_residual_pagerank" or \
                built["residual_sparse_apply"] != 1:
            raise ValueError("wrong Spine algorithm/selector")
        report.update(status="ROUTED_NOT_BOARD_TESTED", xclbin=preparation.pin(binary),
                      provenance=preparation.pin(provenance))
    except BaseException as error:
        report.update(status="FAILED_RETAINED", error=repr(error))
        raise
    finally:
        lease.release()
        report["memory_events_after"] = (group / "memory.events").read_text()
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository", "settings", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=172800)
    parser.add_argument("--memory-gib", type=int, choices=(48, 56, 64), default=64)
    args = parser.parse_args()
    for key in ("repository", "settings", "output"):
        setattr(args, key, getattr(args, key).resolve())
    print(run(args)["status"], flush=True)


if __name__ == "__main__":
    main()
