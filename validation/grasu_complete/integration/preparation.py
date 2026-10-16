"""Freeze the real connected kernels and keep the experiment's fixtures separate."""

from pathlib import Path
import shutil

from .. import commands, preparation as common


def prepare(output, fixture, upstream, include):
    for name in ("kernel_config.h", "kernel_dispatch.cpp", "kernel_process_ddr.cpp"):
        if not (upstream / name).is_file():
            raise ValueError("explicit actual upstream G source required: " + name)
    pins, sources = common.prepare(output, fixture, upstream / "kernel_config.h", include)
    copies = [(upstream / name, Path("upstream") / name)
              for name in ("kernel_dispatch.cpp", "kernel_process_ddr.cpp")]
    copies += [(path, Path("integration") / path.name)
               for path in sorted((Path(__file__).parent / "fixtures").iterdir())
               if path.is_file()]
    for original, relative in copies:
        frozen = output / "source" / relative
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, frozen)
        before, after = common.pin(original), common.pin(frozen)
        if before["sha256"] != after["sha256"]:
            raise ValueError("connected-G source changed during freeze")
        pins += [before, after]
        sources.append({"member": relative.as_posix(), "original": str(original), **after})
    # A module executed with `python -m` is named __main__; freeze it explicitly.
    for original in sorted(Path(__file__).parent.glob("*.py")):
        frozen = output / "runner/integration" / original.name
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, frozen)
        before, after = common.pin(original), common.pin(frozen)
        if before["sha256"] != after["sha256"]:
            raise ValueError("integration runner changed during freeze")
        pins += [before, after]
    return pins, sources


def packet(output, compiler):
    source = output / "source"
    include = source / "vendor/include"
    directory = output / "connected"
    obj = directory / "unit.o"
    flags = [*commands.flags(source, include, "search"), "-DCACHE_BANK_REGISTERED",
             "-DGRASU_ENABLE_COMPLETION_TOKEN", "-DGRASU_SHARE_HBM_PORTS", "-O1", "-g0",
             "-D_GLIBCXX_ASSERTIONS", "-DDISABLE_MAX_HLS_STREAM_DEPTH_PRINT",
             "-Wno-unknown-pragmas", "-Wno-deprecated-declarations",
             "-isystem", str(include), "-isystem", str(include / "etc")]
    return [("compile-0", [str(compiler), *flags, "-MD", "-MF", str(obj.with_suffix(".d")),
                           "-MT", "probe", "-c", str(source / "integration/bench.cpp"), "-o", str(obj)]),
            ("link", [str(compiler), str(obj), "-lgmp", "-pthread", "-o", str(directory / "probe")]),
            ("execute", [str(directory / "probe")])]
