"""Freeze owned cores, an explicit external search fixture, and runner identity."""

import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path: Path) -> dict:
    return {"path": str(path), "sha256": digest(path)}


def unchanged(pins: list[dict]) -> None:
    for row in pins:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("frozen validation input changed: " + row["path"])


def toolchain_headers(output: Path, settings: Path) -> list[dict]:
    """Pin the driver's internal synthesis headers without overriding selection."""
    pins = []
    for relative in (Path("common/technology/autopilot"), Path("vcxx/data")):
        root = settings.parent / relative
        if not root.is_dir() or not any(root.rglob("hls_stream.h")):
            raise ValueError("missing HLS-driver synthesis header tree")
        for original in sorted(root.rglob("*")):
            if not original.is_file():
                continue
            frozen = output / "toolchain" / relative / original.relative_to(root)
            frozen.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, frozen)
            before, after = pin(original), pin(frozen)
            if before["sha256"] != after["sha256"]:
                raise ValueError("HLS-driver header changed during freeze")
            pins += [before, after]
    return pins


def reviewed(owner: Path, provenance: dict) -> None:
    if provenance.get("schema") != 1 or len(provenance["files"]) != 11:
        raise ValueError("eleven reviewed production source files required")
    names = [row["path"] for row in provenance["files"]]
    if len(set(names)) != 11:
        raise ValueError("duplicate production source")
    for row in provenance["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe production source")
        contents = (owner / relative).read_text()
        for transform in reversed(row["transforms"]):
            before, after = transform["before"], transform["after"]
            if not after:
                after, before = "#ifndef CACHE_BANK_REGISTERED", before + "#ifndef CACHE_BANK_REGISTERED"
            if contents.count(after) != 1:
                raise ValueError("unexpected production binding transform")
            contents = contents.replace(after, before)
        if hashlib.sha256(contents.encode()).hexdigest() != row["origin_sha256"]:
            raise ValueError("production source no longer matches reviewed origin")


def prepare(output: Path, fixture: Path, config: Path, include: Path) -> tuple[list[dict], list[dict]]:
    owner = ROOT / "kernels/grasu_complete"
    provenance = json.loads((owner / "provenance.json").read_text())
    reviewed(owner, provenance)
    copies = [(owner / row["path"], Path("grasu_complete") / row["path"])
              for row in provenance["files"]]
    copies += [(owner / "provenance.json", Path("grasu_complete/provenance.json")),
               (config, Path("upstream/kernel_config.h")),
               (ROOT / "tests/grasu_complete_cache_tb.cpp", Path("grasu_complete_cache_tb.cpp"))]
    for name in ("finite_host.hpp", "control.hpp"):
        copies.append((fixture / "search_pipeline" / name, Path("grasu_complete/search_pipeline") / name))
    copies.append((fixture / "search_binding/rtl_control.cpp", Path("grasu_complete/search_binding/rtl_control.cpp")))
    if not (include / "hls_stream.h").is_file() or not (include / "etc/ap_int_base.h").is_file():
        raise ValueError("installed vendor include tree required")
    copies += [(path, Path("vendor/include") / path.relative_to(include))
               for path in sorted(include.rglob("*")) if path.is_file()]
    for original, relative in copies:
        if not original.is_file() or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("missing or unsafe validation source: " + str(original))
    output.mkdir(parents=True, exist_ok=False)
    pins, sources = [], []
    for original, relative in copies:
        frozen = output / "source" / relative
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, frozen)
        record = pin(frozen)
        if record["sha256"] != digest(original):
            raise ValueError("validation input changed during copy")
        pins += [pin(original), record]
        sources.append({"member": relative.as_posix(), "original": str(original), **record})
    modules = {Path(module.__file__).resolve() for name, module in sys.modules.copy().items()
               if name.startswith(("validation.grasu_complete", "spine_cycle_sim.experiments"))
               and getattr(module, "__file__", None)}
    # `python -m ...study` executes under __main__, not the package module name.
    modules.update(Path(__file__).parent.glob("*.py"))
    for index, original in enumerate(sorted(modules)):
        frozen = output / "runner" / (str(index) + "_" + original.name)
        frozen.parent.mkdir(exist_ok=True)
        shutil.copy2(original, frozen)
        pins += [pin(original), pin(frozen)]
    return pins, sources
