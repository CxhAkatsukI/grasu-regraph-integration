"""Fresh functional execution or real HLS-driver export of the production candidate."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import analysis, commands, preparation, reference, runtime


def run(output, fixture, config, include, *, stage="source", source_reference=None,
        hls_settings=None, wait_seconds=86400):
    if stage not in ("source", "hls") or not 1 <= wait_seconds <= 86400:
        raise ValueError("known stage and finite memory wait required")
    if stage == "hls" and (not source_reference or not hls_settings):
        raise ValueError("fresh source reference and HLS settings required")
    group, containment, policy, lease = runtime.bounds(stage)
    compiler = Path(shutil.which("g++") or "/missing/compiler").resolve()
    pins, sources = preparation.prepare(output, fixture, config, include)
    pins += [preparation.pin(compiler), preparation.pin(Path(sys.executable).resolve())]
    if stage == "hls":
        pins += reference.freeze(output, source_reference, sources)
        pins += [preparation.pin(hls_settings), preparation.pin(hls_settings.parent / "bin/vitis_hls")]
        pins += preparation.toolchain_headers(output, hls_settings)
    report = {"schema": 1, "stage": stage, "status": "PREPARED", "errors": [],
              "steps": [], "functional": {}, "exports": {}, "pins": pins, "sources": sources,
              "containment": containment, "policy": policy, "python_version": sys.version,
              "compiler_version": subprocess.check_output([str(compiler), "--version"], text=True),
              "host_affinity": sorted(os.sched_getaffinity(0)),
              "rtl_validated": False, "routed": False, "board_validated": False,
              "publication_matched": False, "performance_matched": False,
              "scope": "production search/cache components only; not integrated GraSU or G+R"}
    save = lambda: atomic_write_json(output / "results.json", report)
    save()
    try:
        runtime.admit(report, output, lease, wait_seconds)
        environment = runtime.environment(output)
        report["environment"] = environment
        for variant in commands.VARIANTS:
            directory = output / variant
            directory.mkdir()
            if stage == "source":
                packet = commands.source_commands(output / "source", output / "source/vendor/include",
                                                   str(compiler), directory, variant)
                for phase, argv in packet:
                    runtime.execute(report, output, directory, variant, phase, argv, 300, environment)
                prefix = output / "raw" / (variant + "-execute")
                if prefix.with_suffix(".stderr.txt").read_text().strip():
                    raise ValueError("unexpected runtime diagnostic: " + variant)
                report["functional"][variant] = analysis.functional(prefix.with_suffix(".stdout.txt").read_text(), variant)
                report["pins"].append(preparation.pin(directory / "probe"))
            else:
                script = directory / "synthesize.tcl"
                script.write_text(commands.hls_script(output / "source", output / "source/vendor/include", variant))
                report["pins"].append(preparation.pin(script))
                argv = ["/bin/bash", "-c", 'source "$1" && exec "$2" -f "$3"', "hls-driver",
                        str(hls_settings), str(hls_settings.parent / "bin/vitis_hls"), str(script)]
                runtime.execute(report, output, directory, variant, "synthesis-export", argv, 10800, environment)
                report["exports"][variant] = analysis.exported(directory, variant)
            save()
        report["status"] = "SOURCE_FUNCTIONAL_PASS_NOT_RTL" if stage == "source" else "HLS_EXPORT_PASS_PENDING_INTERFACE_REVIEW"
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
    for name in ("output", "fixture", "config", "include"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("source-reference", "hls-settings"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--stage", choices=("source", "hls"), default="source")
    parser.add_argument("--wait-seconds", type=int, default=86400)
    args = parser.parse_args()
    paths = {name: path.resolve() if path else None for name, path in vars(args).items()
             if name not in ("stage", "wait_seconds")}
    print(run(**paths, stage=args.stage, wait_seconds=args.wait_seconds)["status"], flush=True)


if __name__ == "__main__":
    main()
