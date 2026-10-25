"""Check the audited sparse Spine ResPR on AU before G+R finishes linking.

This independent correctness smoke never contributes a paired speedup sample.
"""

import argparse
import json
import os
from pathlib import Path

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware import concurrent
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.containment import current
from validation.grasu_complete import preparation, runtime
from . import board
from .route import verify


def accepted_result(text, workload):
    logs = board.load_logs()
    result = logs.record(text, "SPINE_RESIDENT_BENCHMARK_PASS")
    logs.require(result, algorithm=2, source=workload["source"],
        vertices=workload["vertices"], logical_updates=8, physical_updates=workload["updates"],
        boundary=logs.BOUNDARY, final_validation="outside_wall",
        full_state_readback="each_round", host_correction_included=1)
    if int(result["iterations"]) < 0:
        raise ValueError("negative Spine iteration count")
    return {"record": result, "wall_ms": logs.finite(result, "wall_ms", positive=True)}


def inputs(plan_path):
    plan = json.loads(plan_path.read_text())
    selected = [row for row in plan["workloads"]
                if row["algorithm"] == "residual_pagerank" and row["dataset"] == "AU"]
    if len(selected) != 1 or selected[0]["batch_size"] != 8:
        raise ValueError("exact frozen AU residual PageRank batch required")
    audit_path = Path(plan["build_root"]) / plan["spine_directory"] / "results.json"
    audit = json.loads(audit_path.read_text())
    if audit.get("status") != "ROUTED_NOT_BOARD_TESTED" or \
            audit.get("recovery_kind") != "POSTPROCESS_DEPENDENCY_SCAN_ONLY":
        raise ValueError("exact independently audited sparse Spine artifact required")
    pins = plan["pins"] + audit["pins"] + [preparation.pin(path) for path in
        (plan_path, audit_path, Path(__file__), Path(board.__file__),
         board.REPOSITORY / "scripts/compare_resident_fpga_logs.py")]
    preparation.unchanged(pins)
    return plan, selected[0], audit, pins


def run(plan_path, output):
    output.mkdir(parents=True, exist_ok=False)
    group = current()
    concurrent.verify = verify
    guard = verify(group, memory_gib=16)
    if int(guard["limits"]["memory.max"]) != 16 * 1024**3 or \
            int(guard["limits"]["memory.high"]) > 14 * 1024**3:
        raise ValueError("exact 16-GiB cap and at least 2-GiB high margin required")
    lease = concurrent.Lease(Path.home() / ".cache/spine-cycle-sim/compiler-reservations", group)
    policy = {"tree_memory_gib": 16, "reserve_gib": 24, "allow_bounded_builds": True}
    report = {"status": "PREPARING", "containment": guard, "board_tested": False,
              "scope": "independent_Spine_AU_ResPR_correctness_not_paired_speedup"}
    save = lambda: atomic_write_json(output / "results.json", report)
    save()
    try:
        plan, workload, audit, pins = inputs(plan_path)
        host, binary = plan["spine_hosts"]["respr"], audit["xclbin"]["path"]
        argv = [host, binary, "--dynamic-graph", workload["graph"],
                "--source", str(workload["source"]), "--resident-benchmark"]
        report["clocks"] = board.clocks(binary, output / "spine-clocks.json")
        manifest = output / "manifest.json"
        atomic_write_json(manifest, {"pins": pins, "command": argv, "workload": workload,
                                    "clocks": report["clocks"], "policy": policy})
        pins += [preparation.pin(manifest), preparation.pin(output / "spine-clocks.json")]
        with Path(plan["board_lock"]).open("a") as lock:
            board.admit(lock, lease, pins, report, save, policy)
            affinity = sorted(os.sched_getaffinity(0))[:4]
            os.sched_setaffinity(0, affinity)
            report.update(status="RUNNING_SPINE_AU_RESPR", cpu_affinity=affinity)
            save()
            environment = dict(os.environ, XILINX_XRT="/opt/xilinx/xrt", XCL_DEVICE_INDEX="1",
                SPINE_EXPECT_BDF="0000:c1:00.1",
                LD_LIBRARY_PATH="/opt/xilinx/xrt/lib:/usr/lib/x86_64-linux-gnu")
            environment.pop("XCL_EMULATION_MODE", None)
            result = runtime.run_link(argv, output, output / "spine", timeout=1860,
                tree_memory_gib=16, reserve_gib=24, environment=environment)
            report["execution"] = result
            if result["exit_code"] or result["stop_reason"] != "process_exit" or \
                    result["cleanup_snapshot_error"]:
                raise RuntimeError("Spine correctness smoke failed or safely stopped")
            report["measurement"] = accepted_result((output / "spine.stdout.txt").read_text(), workload)
            preparation.unchanged(pins)
            report.update(status="SPINE_AU_RESPR_SMOKE_PASS", board_tested=True)
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
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.plan.resolve(), args.output.resolve())["status"], flush=True)


if __name__ == "__main__":
    main()
