"""Memory-contained continuation from production source/HLS to component RTL."""

import argparse
import os
from pathlib import Path
import sys

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import commands, preparation, rtl_analysis, rtl_preparation, runtime


def run(output, baseline, search_reference, cache_reference, hls_settings, wait_seconds=86400):
    if not 1 <= wait_seconds <= 86400:
        raise ValueError("finite RTL memory wait required")
    group, containment, policy, lease = runtime.bounds("rtl")
    pins, sources, interfaces = rtl_preparation.freeze(output, baseline, search_reference,
                                                      cache_reference, hls_settings)
    pins += [preparation.pin(Path(sys.executable).resolve())]
    report = {"schema": 1, "stage": "rtl", "status": "PREPARED", "errors": [],
              "steps": [], "components": {}, "hls_abi_review": interfaces,
              "pins": pins, "sources": sources, "containment": containment, "policy": policy,
              "host_affinity": sorted(os.sched_getaffinity(0)), "python_version": sys.version,
              "rtl_validated": False, "routed": False, "board_validated": False,
              "performance_matched": False, "publication_matched": False,
              "scope": "isolated production search/token-cache/plain-cache; not integrated G or G+R"}
    save = lambda: atomic_write_json(output / "results.json", report)
    save()
    try:
        runtime.admit(report, output, lease, wait_seconds)
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                       "LANG": "C", "LC_ALL": "C", "MALLOC_ARENA_MAX": "2"}
        report["environment"] = environment
        for variant in commands.VARIANTS:
            directory = output / variant
            directory.mkdir()
            script = directory / "cosim.tcl"
            script.write_text(rtl_preparation.script(output / "source", variant))
            report["pins"].append(preparation.pin(script))
            argv = ["/bin/bash", "-c", 'source "$1" && exec "$2" -f "$3"', "hls-driver",
                    str(hls_settings), str(hls_settings.parent / "bin/vitis_hls"), str(script)]
            runtime.execute(report, output, directory, variant, "rtl-cosimulation", argv, 21600, environment)
            reference = output / "reference" / ("search" if variant == "search" else "cache")
            report["components"][variant] = rtl_analysis.inspect(directory, variant, reference)
            report["pins"] += report["components"][variant]["artifacts"]
            save()
        report["rtl_validated"] = True
        report["status"] = "PRODUCTION_COMPONENT_RTL_ABI_PASS_NOT_INTEGRATED_OR_ROUTED"
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
    for name in ("output", "baseline", "search-reference", "cache-reference", "hls-settings"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=86400)
    args = parser.parse_args()
    paths = {name: value.resolve() for name, value in vars(args).items() if name != "wait_seconds"}
    print(run(**paths, wait_seconds=args.wait_seconds)["status"], flush=True)


if __name__ == "__main__":
    main()
