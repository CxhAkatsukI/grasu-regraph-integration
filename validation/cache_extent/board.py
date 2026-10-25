"""Run pinned resident FPGA pairs; never substitute an older failed artifact."""

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from validation.grasu_complete import preparation, runtime
from .route import verify
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware import concurrent
from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware.containment import current, other_builds
from spine_cycle_sim.experiments.upstream_controls.execution import available_memory_bytes

REPOSITORY = Path(__file__).resolve().parents[2]


def load_logs():
    path = REPOSITORY / "scripts/compare_resident_fpga_logs.py"
    spec = importlib.util.spec_from_file_location("resident_logs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_requirements(config, report, save):
    deadline = time.monotonic() + 259200
    while True:
        pending = []
        for requirement in config.get("requirements", []):
            path = Path(requirement["path"])
            state = json.loads(path.read_text()).get("status") if path.exists() else None
            if state == "FAILED_RETAINED":
                raise RuntimeError("prerequisite failed: " + str(path))
            if state != requirement["status"]:
                pending.append(str(path))
        report.update(status="WAITING_FOR_ARTIFACT_REQUIREMENTS", pending=pending)
        save()
        if not pending:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("required artifacts unavailable after three days")
        time.sleep(15)


def admit(lock, lease, pins, report, save, policy):
    deadline = time.monotonic() + 21600
    while True:
        preparation.unchanged(pins)
        held = False
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held = True
        except BlockingIOError:
            pass
        if held:
            users = subprocess.run(["fuser", "/dev/dri/renderD129"],
                                   capture_output=True, text=True, timeout=30)
            if users.returncode not in (0, 1):
                raise ValueError("cannot inspect external board users")
            if users.returncode == 1 and not (users.stdout.strip() or users.stderr.strip()):
                report["admission"] = lease.sample(available_memory_bytes(), other_builds(), policy, commit=True)
                if report["admission"]["admitted"]:
                    return
            fcntl.flock(lock, fcntl.LOCK_UN)
        report["status"] = "WAITING_FOR_FREE_BOARD_AND_MEMORY"
        save()
        if time.monotonic() >= deadline:
            raise TimeoutError("free card and complete memory budgets unavailable")
        time.sleep(15)


def clocks(binary, output):
    subprocess.run(["/opt/xilinx/xrt/bin/xclbinutil", "--input", str(binary),
                    "--dump-section", "CLOCK_FREQ_TOPOLOGY:JSON:" + str(output)],
                   check=True, capture_output=True, timeout=120)
    rows = json.loads(output.read_text())["clock_freq_topology"]["m_clock_freq"]
    data = [row for row in rows if row["m_type"] == "DATA"]
    if not data or any(float(row["m_freq_Mhz"]) <= 0 for row in data):
        raise ValueError("positive actual FPGA data clocks required")
    return rows


def measure(index, config, output, pins, environment, logs):
    order = ("gr", "spine") if index % 2 == 0 else ("spine", "gr")
    destination = output / ("sample-" + str(index))
    destination.mkdir()
    resources, texts = {}, {}
    for architecture in order:
        preparation.unchanged(pins)
        if architecture == "gr":
            argv = ["bash", str(REPOSITORY / "scripts/run_pma_native_hw.sh"),
                    "--algorithm", config["logical"], "--host", config["gr_host"],
                    "--xclbin", config["gr_binary"], "--graph", config["graph"],
                    "--out-dir", str(destination / "gr"), "--device-index", "1",
                    "--source", str(config["source"]), "--max-supersteps", "256", "--timeout", "1800"]
            result_path = destination / "gr/run.log"
        else:
            argv = [config["spine_host"], config["spine_binary"], "--dynamic-graph", config["graph"],
                    "--source", str(config["source"]), "--resident-benchmark"]
            result_path = destination / "spine.stdout.txt"
        result = runtime.run_link(argv, destination, destination / architecture, timeout=1860,
                                  tree_memory_gib=config["memory_gib"], reserve_gib=24,
                                  environment=environment)
        resources[architecture] = result
        if result["exit_code"] or result["stop_reason"] != "process_exit" or result["cleanup_snapshot_error"]:
            raise RuntimeError("FPGA sample failed: " + architecture + "/" + str(index))
        texts[architecture] = result_path.read_text()
    pair = logs.compare(config["logical"], texts["gr"], texts["spine"], config["source"])
    return {"sample_index": index, "warmup": index == 0, "order": order,
            "pair": pair, "resources": resources}


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text())
    budget = config["memory_gib"]
    if type(budget) is not int or budget not in (8, 16, 24, 32):
        raise ValueError("explicit 8/16/24/32-GiB board-host budget required")
    policy = {"tree_memory_gib": budget, "reserve_gib": 24, "allow_bounded_builds": True}
    logs = load_logs()
    group = current()
    concurrent.verify = verify
    guard = verify(group, memory_gib=budget)
    if int(guard["limits"]["memory.max"]) != budget * 1024**3 or \
            int(guard["limits"]["memory.high"]) > (budget - 2) * 1024**3:
        raise ValueError("exact board-host cap and >=2-GiB high-watermark margin required")
    lease = concurrent.Lease(Path.home() / ".cache/spine-cycle-sim/compiler-reservations", group)
    report = {"status": "PREPARING", "config": config, "containment": guard,
              "samples": [], "policy": policy, "board_tested": False, "boundary": logs.BOUNDARY}
    save = lambda: atomic_write_json(args.output / "results.json", report)
    try:
        wait_requirements(config, report, save)
        preparation.unchanged(config["expected_pins"])
        paths = [args.config, Path(__file__), Path(__file__).with_name("route.py"),
                 REPOSITORY / "scripts/compare_resident_fpga_logs.py",
                 REPOSITORY / "scripts/run_pma_native_hw.sh", REPOSITORY / "scripts/env.sh"]
        paths += [Path(config[key]) for key in ("gr_host", "gr_binary", "spine_host", "spine_binary", "graph")]
        pins = config["expected_pins"] + [preparation.pin(path) for path in paths]
        report["clocks"] = {name: clocks(config[name + "_binary"], args.output / (name + "-clocks.json"))
                            for name in ("gr", "spine")}
        atomic_write_json(args.output / "manifest.json", {"pins": pins, "config": config,
                              "boundary": logs.BOUNDARY, "clocks": report["clocks"]})
        pins.append(preparation.pin(args.output / "manifest.json"))
        with Path(config["board_lock"]).open("a") as lock:
            admit(lock, lease, pins, report, save, policy)
            affinity = sorted(os.sched_getaffinity(0))[:4]
            os.sched_setaffinity(0, affinity)
            report["cpu_affinity"] = affinity
            environment = dict(os.environ, XILINX_XRT="/opt/xilinx/xrt", XCL_DEVICE_INDEX="1",
                SPINE_EXPECT_BDF="0000:c1:00.1", GRASU_REGRAPH_EXPECT_BDF="0000:c1:00.1",
                GRASU_ROOT="/home/chuxiao/GraSU", REGRAPH_ROOT="/home/chuxiao/regraph/ReGraph",
                LD_LIBRARY_PATH="/opt/xilinx/xrt/lib:/usr/lib/x86_64-linux-gnu",
                GRASU_UPDATE_REPEATS="1", GRASU_SHARDED_PREMIGRATE_INPUTS="1")
            environment.pop("XCL_EMULATION_MODE", None)
            report["status"] = "RUNNING_FPGA_PAIRS"
            save()
            for index in range(4):
                report["current_sample"] = index
                save()
                report["samples"].append(measure(index, config, args.output, pins, environment, logs))
                save()
            preparation.unchanged(pins)
            report.update(summary=logs.summarize(report["samples"]),
                          status="RESIDENT_PAIR_PASS", board_tested=True)
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
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.config, args.output = args.config.resolve(), args.output.resolve()
    print(run(args)["status"], flush=True)


if __name__ == "__main__":
    main()
