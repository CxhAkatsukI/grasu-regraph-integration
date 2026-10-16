"""Require matching production RTL, connected state and storage evidence."""

import json
from pathlib import Path

from spine_cycle_sim.experiments.evaluation_impact.common_g.complete_pipeline.resource_delivery import validate_fit
from spine_cycle_sim.experiments.evaluation_impact.common_g.complete_pipeline.resource_fit import resources
from .. import admission, preparation
from ..integration import delivery
from . import upstream


def candidates(build, basis, rtl, connected, fit, config):
    checked = admission.review(rtl, config)
    complete = delivery.recheck(connected)
    if complete["status"] != delivery.PASS:
        raise ValueError("passing connected production-host evidence required")
    sources = {row["member"]: row for row in complete["sources"]}
    rtl_sources = {row["member"]: row for row in json.loads((rtl / "results.json").read_text())["sources"]}
    if len(sources) != len(complete["sources"]):
        raise ValueError("duplicate connected source member")
    provenance = json.loads((preparation.ROOT / "kernels/grasu_complete/provenance.json").read_text())
    names = ["grasu_complete/" + row["path"] for row in provenance["files"]]
    names += ["grasu_complete/provenance.json", "upstream/kernel_config.h"]
    if any(name not in rtl_sources for name in names):
        raise ValueError("complete owned production source matrix required")
    # Host-only finite-FIFO fixtures have separate frozen identities and are not
    # synthesis inputs. Compare all owned cores/config, not the different benches.
    required = [rtl_sources[name] for name in names]
    for row in required:
        candidate = sources.get(row["member"])
        if candidate is None or candidate["sha256"] != row["sha256"]:
            raise ValueError("connected host and RTL use different production sources")
    ledger = json.loads((fit / "results.json").read_text())
    validate_fit(fit, ledger)
    relocated = ledger["single_cu_relocation_screen"]
    platform = relocated.get("platform_storage_screen")
    if (platform is None or any(row["uram_oversubscribed_slrs"] or row["total_uram_capacity_exceeded"]
                                for row in (relocated, platform))):
        raise ValueError("relocated production storage screen does not fit platform hard pblocks")
    replacements = {}
    for kernel, variant in (("bin_search", "search"), ("process_cache", "cache-token")):
        export = checked["exports"][variant]
        if resources(fit / "source/hls" / (kernel + ".xml"), kernel) != resources(Path(export["report"]), kernel):
            raise ValueError("resource screen differs from production RTL export")
        replacements[kernel] = Path(export["xo"])
    reused = upstream.review(build, basis, complete)
    reports = [rtl / "results.json", connected / "results.json", fit / "results.json"]
    pins = [*checked["pins"], *complete["pins"], *ledger["source"], *reused["pins"],
            *map(preparation.pin, reports)]
    preparation.unchanged(pins)
    return {"replacements": replacements, "reports": reports, "pins": pins,
            "identity": {"production_source_members": required,
                         "rtl_components_rechecked": True, "connected_host_rechecked": True,
                         "reused_upstream": reused,
                         "integrated_rtl_admitted": False, "device_metadata_refresh_admitted": False,
                         "production_baseline_admitted": False, "publication_match_admitted": False}}
