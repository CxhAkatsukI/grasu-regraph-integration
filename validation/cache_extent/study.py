"""Freeze and validate the bounded-transfer cache before integration routing."""

import argparse
import json
from pathlib import Path
import shutil
import sys

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from validation.grasu_complete import analysis, commands, preparation, runtime


VARIANTS = ("cache-token", "cache-plain")


def freeze_reference(output, reference, sources):
    path = reference / "results.json"
    report = json.loads(path.read_text())
    if report.get("status") != "CACHE_EXTENT_SOURCE_PASS" or report.get("stage") != "source":
        raise ValueError("fresh bounded and legacy source pass required")
    preparation.unchanged(report["pins"])
    keys = lambda rows: {row["member"]: row["sha256"] for row in rows}
    if keys(sources) != keys(report["sources"]):
        raise ValueError("source and synthesis identities differ")
    expected = [(variant + suffix, phase) for suffix in ("-legacy", "-bounded")
                for variant in VARIANTS for phase in ("compile-0", "link", "execute")]
    if [(row["variant"], row["phase"]) for row in report["steps"]] != expected:
        raise ValueError("incomplete source matrix")
    for step in report["steps"]:
        if step["exit_code"] or step["stop_reason"] != "process_exit" or step["cleanup_snapshot_error"]:
            raise ValueError("nonpassing reference step")
    for suffix in ("-legacy", "-bounded"):
        for variant in VARIANTS:
            name = variant + suffix
            prefix = reference / "raw" / (name + "-execute")
            parser = analysis.bounded_functional if suffix == "-bounded" else analysis.functional
            if prefix.with_suffix(".stderr.txt").read_text().strip():
                raise ValueError("unexpected source diagnostic")
            if parser(prefix.with_suffix(".stdout.txt").read_text(), variant) != report["functional"][name]:
                raise ValueError("source oracle log changed")
    frozen = output / "source-reference.json"
    shutil.copy2(path, frozen)
    return [preparation.pin(path), preparation.pin(frozen)]


def run(args):
    group, containment, policy, lease = runtime.bounds(args.stage)
    compiler = Path(shutil.which("g++")).resolve()
    pins, sources = preparation.prepare(args.output, args.fixture, args.config, args.include)
    pins += [preparation.pin(compiler), preparation.pin(Path(__file__))]
    if args.stage == "hls":
        if not args.source_reference or not args.hls_settings:
            raise ValueError("source reference and HLS settings required")
        pins += freeze_reference(args.output, args.source_reference, sources)
        pins += [preparation.pin(args.hls_settings),
                 preparation.pin(args.hls_settings.parent / "bin/vitis_hls")]
        pins += preparation.toolchain_headers(args.output, args.hls_settings)
    report = {"schema": 1, "stage": args.stage, "status": "PREPARED", "pins": pins,
              "sources": sources, "steps": [], "functional": {}, "exports": {}, "errors": [],
              "containment": containment, "policy": policy, "capacity_segments": 131072,
              "board_validated": False, "routed": False,
              "scope": "per-half transfer extent rounded to 16 banks; capacity and update logic unchanged"}
    save = lambda: atomic_write_json(args.output / "results.json", report)
    save()
    try:
        runtime.admit(report, args.output, lease, args.wait_seconds)
        env = runtime.environment(args.output)
        modes = (False, True) if args.stage == "source" else (True,)
        for bounded in modes:
            for variant in VARIANTS:
                name = variant + ("-bounded" if bounded else "-legacy")
                directory = args.output / name
                directory.mkdir()
                if args.stage == "source":
                    packet = commands.source_commands(args.output / "source", args.output / "source/vendor/include",
                                                       str(compiler), directory, variant, bounded=bounded)
                    for phase, argv in packet:
                        runtime.execute(report, args.output, directory, name, phase, argv, 600, env)
                    prefix = args.output / "raw" / (name + "-execute")
                    if prefix.with_suffix(".stderr.txt").read_text().strip():
                        raise ValueError("unexpected oracle diagnostic")
                    parser = analysis.bounded_functional if bounded else analysis.functional
                    report["functional"][name] = parser(prefix.with_suffix(".stdout.txt").read_text(), variant)
                    report["pins"].append(preparation.pin(directory / "probe"))
                else:
                    script = directory / "synthesize.tcl"
                    script.write_text(commands.hls_script(args.output / "source", args.output / "source/vendor/include",
                                                          variant, bounded=True))
                    report["pins"].append(preparation.pin(script))
                    argv = ["/bin/bash", "-c", 'source "$1" && exec "$2" -f "$3"', "hls-driver",
                            str(args.hls_settings), str(args.hls_settings.parent / "bin/vitis_hls"), str(script)]
                    runtime.execute(report, args.output, directory, name, "synthesis-export", argv, 10800, env)
                    report["exports"][variant] = analysis.exported(directory, variant, bounded=True)
                save()
        report["status"] = "CACHE_EXTENT_SOURCE_PASS" if args.stage == "source" else "CACHE_EXTENT_EXPORT_PASS_NOT_ROUTED"
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
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    print(run(args)["status"], flush=True)


if __name__ == "__main__":
    main()
