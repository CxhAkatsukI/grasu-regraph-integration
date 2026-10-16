"""Compiler packets for the owned search and both full-cache bindings."""

from pathlib import Path


VARIANTS = ("search", "cache-token", "cache-plain")


def flags(source: Path, include: Path, variant: str) -> list[str]:
    if variant not in VARIANTS:
        raise ValueError("unknown complete-G component")
    result = ["-std=c++14", "-D_GTHREAD_USE_COND_INIT_FUNC",
              "-DGRASU_MAX_CACHE_SEGMENT=131072", "-I" + str(source / "upstream"),
              "-I" + str(include), "-I" + str(include / "etc")]
    if variant == "search":
        result += ['-DGRASU_SEARCH_HOST_HARNESS="finite_host.hpp"', "-pthread"]
    else:
        result.append("-DCACHE_BANK_REGISTERED")
        if variant == "cache-token":
            result.append("-DGRASU_ENABLE_COMPLETION_TOKEN")
    return result


def source_commands(source: Path, include: Path, compiler: str, directory: Path,
                    variant: str) -> list[tuple[str, list[str]]]:
    root = source / "grasu_complete"
    files = ([root / "search_binding/top.cpp", root / "search_binding/rtl_control.cpp"]
             if variant == "search" else
             [root / "process_cache.cpp", source / "grasu_complete_cache_tb.cpp"])
    common = [compiler, *flags(source, include, variant), "-O1", "-g0",
            "-D_GLIBCXX_ASSERTIONS", "-DDISABLE_MAX_HLS_STREAM_DEPTH_PRINT",
            "-Wno-unknown-pragmas", "-Wno-deprecated-declarations",
            "-isystem", str(include), "-isystem", str(include / "etc")]
    # Vendor stream headers define non-inline globals; use one host TU, not a
    # linker waiver for duplicate definitions. HLS compiles the core directly.
    obj = directory / "unit.o"
    result = [("compile-0", [*common, "-MD", "-MF", str(obj.with_suffix(".d")),
               "-MT", "probe", "-include", str(files[0]), "-c", str(files[1]), "-o", str(obj)])]
    result += [("link", [compiler, str(obj), "-lgmp", "-pthread",
                         "-o", str(directory / "probe")]),
               ("execute", [str(directory / "probe")])]
    return result


def hls_script(source: Path, include: Path, variant: str) -> str:
    # Synthesis uses the real HLS driver, never a standalone frontend invocation.
    # The HLS driver selects its synthesis headers. Its public include/ tree is
    # for host simulation; adding that tree overrides the driver's stream model.
    compile_flags = [flag for flag in flags(source, include, variant)
                     if not flag.startswith("-DGRASU_SEARCH_HOST_HARNESS")
                     and flag not in ("-I" + str(include), "-I" + str(include / "etc"), "-pthread")]
    top = "bin_search" if variant == "search" else "process_cache"
    filename = source / "grasu_complete" / ("search_binding/top.cpp" if variant == "search" else "process_cache.cpp")
    if any(char.isspace() or char in "{}" for path in (source, include) for char in str(path)):
        raise ValueError("unsupported Tcl path")
    return f'''open_project -reset project
set_top {top}
add_files {{{filename}}} -cflags {{{' '.join(compile_flags)}}}
open_solution -reset solution -flow_target vitis
set_part {{xcu55c-fsvh2892-2L-e}}
create_clock -period 6.666666667 -name default
csynth_design
export_design -format xo -output candidate.xo
exit
'''
