"""Bounded connected-G host checks; no RTL, device BO or performance claim."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments.sharded_k4_stages.link_runtime import run_link
from .. import preparation as common, runtime
from . import analysis, preparation


def run(output, fixture, upstream, include, *, wait_seconds=86400):
    if not 1 <= wait_seconds <= 86400:
        raise ValueError("finite admission wait required")
    group, containment, policy, lease = runtime.bounds("source")
    compiler = Path(shutil.which("g++") or "/missing/compiler").resolve()
    pins, sources = preparation.prepare(output, fixture, upstream, include)
    pins += [common.pin(compiler), common.pin(Path(sys.executable).resolve())]
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                   "LANG": "C", "LC_ALL": "C", "MALLOC_ARENA_MAX": "2"}
    report = {"schema": 1, "status": "PREPARED", "pins": pins, "sources": sources,
              "steps": [], "errors": [], "containment": containment, "policy": policy,
              "environment": environment, "python_version": sys.version,
              "compiler_version": subprocess.check_output([str(compiler), "--version"], text=True),
              "host_affinity": sorted(os.sched_getaffinity(0)),
              "scope": "four production search cores, dispatch, two hot and two cold updates; host only",
              "rtl_validated": False, "device_metadata_refresh_validated": False,
              "routed": False, "board_validated": False, "performance_matched": False,
              "publication_matched": False}
    save = lambda: atomic_write_json(output / "results.json", report)
    save()
    try:
        runtime.admit(report, output, lease, wait_seconds)
        directory = output / "connected"
        directory.mkdir()
        for phase, argv in preparation.packet(output, compiler):
            runtime.execute(report, output, directory, "connected", phase, argv, 300, environment)
        prefix = output / "raw/connected-execute"
        report["functional"] = analysis.functional(prefix.with_suffix(".stdout.txt").read_text())
        report["diagnostics"] = analysis.diagnostics(prefix.with_suffix(".stderr.txt").read_text())
        report["pins"].append(common.pin(directory / "probe"))
        common.unchanged(report["pins"])
        report["status"] = "RUNNING_EXPECTED_STALE_METADATA_REJECTION"
        save()
        prefix = output / "raw/connected-stale-metadata"
        step = run_link([str(directory / "probe"), "--stale-metadata"], directory, prefix,
                        timeout=300, tree_memory_gib=1, reserve_gib=24, environment=environment)
        report["steps"].append({"variant": "connected", "phase": "negative-stale-metadata", **step})
        save()
        report["stale_metadata_control"] = analysis.stale_rejection(
            step, prefix.with_suffix(".stdout.txt").read_text(), prefix.with_suffix(".stderr.txt").read_text())
        common.unchanged(report["pins"])
        report["status"] = "CONNECTED_G_HOST_FUNCTIONAL_PASS_NOT_RTL_OR_DEVICE_REFRESH"
    except BaseException as error:
        report["status"] = "FAILED_RETAINED"
        report["errors"].append(repr(error))
        raise
    finally:
        lease.release()
        report["memory_events_after"] = (group / "memory.events").read_text()
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "fixture", "upstream", "include"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=86400)
    args = parser.parse_args()
    print(run(args.output.resolve(), args.fixture.resolve(), args.upstream.resolve(),
              args.include.resolve(), wait_seconds=args.wait_seconds)["status"], flush=True)


if __name__ == "__main__":
    main()
