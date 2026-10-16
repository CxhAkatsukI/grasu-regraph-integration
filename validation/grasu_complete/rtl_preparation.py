"""Freeze an exact source continuation of a successful production HLS campaign."""

import json
from pathlib import Path
import shutil

from . import abi, analysis, commands, preparation


def freeze(output, baseline, search_reference, cache_reference, settings):
    report_path = baseline / "results.json"
    report = json.loads(report_path.read_text())
    if report.get("stage") != "hls" or report.get("status") != "HLS_EXPORT_PASS_PENDING_INTERFACE_REVIEW":
        raise ValueError("passing production HLS campaign required")
    preparation.unchanged(report["pins"])
    if [(row["variant"], row["phase"]) for row in report["steps"]] != [
            (variant, "synthesis-export") for variant in commands.VARIANTS]:
        raise ValueError("incomplete HLS component matrix")
    for row in report["steps"]:
        if row["exit_code"] or row["stop_reason"] != "process_exit" or row["cleanup_snapshot_error"]:
            raise ValueError("failed production HLS step")
    for variant in commands.VARIANTS:
        if analysis.exported(baseline / variant, variant) != report["exports"][variant]:
            raise ValueError("HLS export observations changed")
    source = baseline / "source"
    pins, sources = preparation.prepare(output, source / "grasu_complete",
                                        source / "upstream/kernel_config.h", source / "vendor/include")
    keys = lambda rows: {row["member"]: row["sha256"] for row in rows}
    if keys(sources) != keys(report["sources"]):
        raise ValueError("RTL cores, fixtures or headers differ from HLS campaign")
    copies = [(report_path, Path("reference/hls-results.json"))]
    copies.append((Path(__file__).parent / "fixtures/search_host_config.hpp",
                   Path("runner/search_host_config.hpp")))
    for variant in commands.VARIANTS:
        copies.append((baseline / variant / "candidate.xo", Path("reference/exports") / variant / "candidate.xo"))
    for name, reference in (("search", search_reference), ("cache", cache_reference)):
        copies += [(reference / member, Path("reference") / name / member)
                   for member in ("kernel.xml", "component.xml")]
    for original, relative in copies:
        frozen = output / relative
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, frozen)
        if preparation.digest(original) != preparation.digest(frozen):
            raise ValueError("RTL reference changed during freeze")
        pins += [preparation.pin(original), preparation.pin(frozen)]
    pins += [preparation.pin(settings), preparation.pin(settings.parent / "bin/vitis_hls")]
    pins += preparation.toolchain_headers(output, settings)
    reviews = {}
    for variant in commands.VARIANTS:
        reference = output / "reference" / ("search" if variant == "search" else "cache")
        reviews[variant] = abi.review(output / "reference/exports" / variant / "candidate.xo", variant, reference)
    return pins, sources, reviews


def script(source, variant):
    # The driver selects synthesis headers. Only non-synthesis C simulation gets
    # the explicit finite harness; the same synthesizable core is used unchanged.
    top = "bin_search" if variant == "search" else "process_cache"
    include = source / "vendor/include"
    common = commands.flags(source, include, variant)
    simulation = [flag for flag in common
                  if not flag.startswith("-DGRASU_SEARCH_HOST_HARNESS")
                  and flag not in ("-I" + str(include), "-I" + str(include / "etc"))]
    simulation += ["-I" + str(include / "etc")]
    if variant == "search":
        # HLS reparses -cflags before invoking make: quoted -D header names lose
        # their quotes. A frozen host-only preinclude avoids that extra parser.
        simulation += ["-include", str(source.parent / "runner/search_host_config.hpp")]
    root = source / "grasu_complete"
    core = root / ("search_binding/top.cpp" if variant == "search" else "process_cache.cpp")
    bench = root / "search_binding/rtl_control.cpp" if variant == "search" else source / "grasu_complete_cache_tb.cpp"
    if variant not in commands.VARIANTS or any(char.isspace() or char in "{}" for char in str(source)):
        raise ValueError("invalid RTL variant or Tcl path")
    return f'''open_project -reset project
set_top {top}
add_files {{{core}}} -cflags {{{' '.join(simulation)}}}
add_files -tb {{{bench}}} -cflags {{{' '.join(simulation)}}}
open_solution -reset solution -flow_target vitis
set_part {{xcu55c-fsvh2892-2L-e}}
create_clock -period 6.666666667 -name default
config_rtl -deadlock_detection sim
csim_design -ldflags {{-pthread}}
csynth_design
cosim_design -rtl verilog -tool xsim -ldflags {{-pthread}}
export_design -format xo -output candidate.xo
exit
'''
