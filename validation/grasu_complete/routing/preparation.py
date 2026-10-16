"""Freeze an experimental production-source link without relabeling older XOs."""

from pathlib import Path
import shutil
import sys

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from spine_cycle_sim.experiments.evaluation_impact.common_g.complete_pipeline.hardware.preparation import (
    LINK_TIMEOUTS, freeze)
from .. import preparation as common
from . import gates


def prepare(build, basis, rtl, connected, fit, config, output, *, link_timeout_seconds=43200):
    if output.exists():
        raise FileExistsError("fresh production-source route attempt required")
    if type(link_timeout_seconds) is not int or link_timeout_seconds not in LINK_TIMEOUTS:
        raise ValueError("finite reviewed link timeout required")
    checked = gates.candidates(build, basis, rtl, connected, fit, config)
    manifest = freeze(build, basis, checked["replacements"], checked["reports"], checked["identity"],
                      fit, output, link_timeout_seconds=link_timeout_seconds)
    modules = {Path(module.__file__).resolve() for name, module in sys.modules.copy().items()
               if name.startswith(("validation.grasu_complete", "spine_cycle_sim.experiments"))
               and getattr(module, "__file__", None)}
    modules.update(Path(__file__).parent.glob("*.py"))
    pins = [*manifest["pins"], *checked["pins"], common.pin(Path(sys.executable).resolve())]
    for index, original in enumerate(sorted(modules)):
        destination = output / "runner" / (str(index) + "_" + original.name)
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(original, destination)
        before, after = common.pin(original), common.pin(destination)
        if before["sha256"] != after["sha256"]:
            raise ValueError("route runner changed while freezing")
        pins += [before, after]
    manifest.update(candidate_owner="production-source-grasu-complete",
                    production_source_evidence=checked["identity"],
                    claim="experimental_production_source_link_not_integrated_RTL_or_board_performance")
    manifest["pins"] = list({row["path"]: row for row in pins}.values())
    common.unchanged(manifest["pins"])
    atomic_write_json(output / "manifest.json", manifest)
    return manifest
