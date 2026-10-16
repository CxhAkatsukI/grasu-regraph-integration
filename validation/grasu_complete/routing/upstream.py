"""Verify reused dispatch/cold XOs against their compile packet and source."""

import csv
import hashlib
from pathlib import Path
import shlex
import zipfile

from ..preparation import pin, unchanged

SOURCES = {"dispatch": "kernel_dispatch.cpp", "process_ddr": "kernel_process_ddr.cpp"}
BASE_DEFINES = {"-D_GTHREAD_USE_COND_INIT_FUNC", "-DGRASU_MAX_CACHE_SEGMENT=131072",
                "-DGRASU_COMPACT_HBM_PORTS"}


def review(build, basis, connected):
    """Check physical bindings separately from the connected CPU fixture."""
    commands_path, inputs_path = build / "compile_commands.sh", build / "inputs.tsv"
    commands = [shlex.split(line) for line in commands_path.read_text().splitlines()
                if line.startswith("v++ ")]
    with inputs_path.open() as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["role", "status", "sha256", "bytes", "path"]:
            raise ValueError("reviewed upstream input-table schema required")
        inputs = list(reader)
    sources = {row["member"]: row for row in connected["sources"]}
    if len(sources) != len(connected["sources"]):
        raise ValueError("duplicate connected source member")
    pins = [pin(commands_path), pin(inputs_path)]
    for name in ("kernel_config.h", *SOURCES.values()):
        rows = [row for row in inputs if Path(row["path"]).name == name]
        frozen = sources.get("upstream/" + name)
        if (len(rows) != 1 or rows[0]["status"] != "present" or frozen is None
                or rows[0]["sha256"] != frozen["sha256"]):
            raise ValueError("upstream compilation differs from connected source: " + name)
        path = Path(rows[0]["path"])
        if path.stat().st_size != int(rows[0]["bytes"]) or pin(path)["sha256"] != frozen["sha256"]:
            raise ValueError("historical upstream input changed: " + name)
        pins += [pin(path), pin(Path(frozen["path"]))]

    checked = {}
    for kernel, source in SOURCES.items():
        rows = [row for row in commands if row and Path(row[-1]).name == source]
        if len(rows) != 1:
            raise ValueError("one upstream compile command required: " + kernel)
        command = rows[0]
        for flag, value in (("--target", "hw"), ("--kernel_frequency", "150")):
            if command.count(flag) != 1 or command[command.index(flag) + 1] != value:
                raise ValueError("changed upstream target or clock")
        expected = BASE_DEFINES | ({"-DGRASU_ENABLE_COMPLETION_TOKEN"} if kernel == "process_ddr" else set())
        defines = [arg for arg in command if arg.startswith("-D")]
        if set(defines) != expected or len(defines) != len(expected) or command.count("--compile") != 1:
            raise ValueError("changed upstream kernel defines")
        if command.count("-o") != 1 or command.count("--config") != 1:
            raise ValueError("ambiguous upstream compile output/configuration")
        original = Path(command[command.index("-o") + 1])
        selected = basis / "inputs" / (kernel + ".hw.xo")
        if pin(original)["sha256"] != pin(selected)["sha256"]:
            raise ValueError("reused XO differs from original compilation")
        with zipfile.ZipFile(selected) as archive:
            member = kernel + "/cpu_sources/" + source
            if (archive.namelist().count(member) != 1 or
                    hashlib.sha256(archive.read(member)).hexdigest() != sources["upstream/" + source]["sha256"]):
                raise ValueError("XO embedded source differs from connected kernel")
        configuration = Path(command[command.index("--config") + 1])
        pins += [pin(original), pin(selected), pin(configuration)]
        checked[kernel] = {"compile_command": command, "xo": pin(selected),
                           "source_member": member, "defines": sorted(expected)}
    unchanged(pins)
    return {"kernels": checked, "pins": pins,
            "cold_axi_masters": 4, "connected_host_cold_axi_masters": "not_modeled",
            "binding_note": "CPU fixture defines GRASU_SHARE_HBM_PORTS; reused cold XO does not. "
                            "This changes AXI pragmas, not CPU operations; physical aliasing remains a board gate."}
