"""Reuse the common atomic budget admission and process-tree watchdog."""

from pathlib import Path
import time

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments import host_memory
from spine_cycle_sim.experiments.sharded_k4_stages.link_runtime import run_link
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.concurrent import Lease
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.containment import current, other_builds, verify
from spine_cycle_sim.experiments.upstream_controls.execution import available_memory_bytes, dependency_identities
from .preparation import pin, unchanged


def environment(output):
    temporary = output / "temporary"
    temporary.mkdir(exist_ok=False)
    return {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
            "LANG": "C", "LC_ALL": "C", "MALLOC_ARENA_MAX": "2",
            "TMPDIR": str(temporary.resolve())}


def bounds(stage):
    memory = 1 if stage == "source" else 8
    group = current()
    guard = verify(group, memory_gib=memory)
    if int(guard["limits"]["memory.max"]) != memory * 1024**3:
        raise ValueError("exact declared cgroup memory budget required")
    high = 768 * 1024**2 if stage == "source" else 7 * 1024**3
    if int(guard["limits"]["memory.high"]) > high:
        raise ValueError("cgroup high watermark above declared policy")
    policy = {"tree_memory_gib": memory, "reserve_gib": 24, "allow_bounded_builds": True}
    lease = Lease(Path.home() / ".cache/spine-cycle-sim/compiler-reservations", group)
    return group, guard, policy, lease


def admit(report, output, lease, wait_seconds):
    source = pin(Path(host_memory.__file__).resolve())
    if source not in report["pins"]:
        report["pins"].append(source)
    report["host_memory_accounting"] = {"policy": host_memory.POLICY, "source": source}
    deadline = time.monotonic() + wait_seconds
    while True:
        unchanged(report["pins"])
        report["host_memory_snapshot"] = host_memory.sample_host_memory().record()
        report["admission"] = lease.sample(available_memory_bytes(), other_builds(), report["policy"], commit=True)
        report["status"] = "WAITING_FOR_MEMORY_NOT_OTHER_TOOLS"
        atomic_write_json(output / "results.json", report)
        if report["admission"]["admitted"]:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("full peer budgets plus reserve did not fit; no compiler started")
        time.sleep(min(10, remaining))


def execute(report, output, directory, variant, phase, argv, timeout, environment):
    unchanged(report["pins"])
    report["status"] = "RUNNING_" + variant + "_" + phase
    atomic_write_json(output / "results.json", report)
    step = run_link(argv, directory, output / "raw" / (variant + "-" + phase), timeout=timeout,
                    tree_memory_gib=report["policy"]["tree_memory_gib"], reserve_gib=24, environment=environment)
    report["steps"].append({"variant": variant, "phase": phase, **step})
    atomic_write_json(output / "results.json", report)
    if step["exit_code"] or step["stop_reason"] != "process_exit" or step["cleanup_snapshot_error"]:
        raise RuntimeError("validation child failed or safely stopped: " + variant + "/" + phase)
    if phase.startswith("compile-"):
        report["pins"] += dependency_identities(Path(argv[-1]).with_suffix(".d"), directory)
    unchanged(report["pins"])
