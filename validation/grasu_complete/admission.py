"""Independently recheck production component evidence without promoting full G."""

import argparse
import json
from pathlib import Path

from spine_cycle_sim.experiments.campaign_runtime import atomic_write_json
from . import commands, preparation, rtl_analysis


PASS = "PRODUCTION_COMPONENT_RTL_RECHECK_PASS_NOT_COMPLETE_G"
RTL_PASS = "PRODUCTION_COMPONENT_RTL_ABI_PASS_NOT_INTEGRATED_OR_ROUTED"
CLAIMS = ("routed", "board_validated", "performance_matched", "publication_matched")


def review(attempt, config):
    """Require the complete matrix, raw observations and current owned source."""
    result = attempt / "results.json"
    result_pin = preparation.pin(result)
    report = json.loads(result.read_text())
    if (report.get("status") != RTL_PASS or report.get("stage") != "rtl"
            or report.get("errors") != [] or report.get("rtl_validated") is not True
            or any(report.get(key) is not False for key in CLAIMS)):
        raise ValueError("unpromoted complete production RTL evidence required")
    if (set(report["components"]) != set(commands.VARIANTS)
            or [(row["variant"], row["phase"]) for row in report["steps"]] != [
                (variant, "rtl-cosimulation") for variant in commands.VARIANTS]):
        raise ValueError("complete ordered production RTL matrix required")
    preparation.unchanged(report["pins"])

    owner = preparation.ROOT / "kernels/grasu_complete"
    provenance = json.loads((owner / "provenance.json").read_text())
    preparation.reviewed(owner, provenance)
    sources = {row["member"]: row for row in report["sources"]}
    if len(sources) != len(report["sources"]):
        raise ValueError("duplicate production evidence member")
    current = [(owner / row["path"], "grasu_complete/" + row["path"])
               for row in provenance["files"]]
    current += [(owner / "provenance.json", "grasu_complete/provenance.json"),
                (config, "upstream/kernel_config.h")]
    pins = [result_pin, *report["pins"]]
    for path, member in current:
        record = preparation.pin(path)
        frozen = sources.get(member)
        if frozen is None or record["sha256"] != frozen["sha256"]:
            raise ValueError("RTL evidence differs from current production source: " + member)
        if preparation.pin(attempt / "source" / member)["sha256"] != record["sha256"]:
            raise ValueError("frozen production source changed: " + member)
        pins.append(record)

    exports = {}
    for step in report["steps"]:
        variant = step["variant"]
        raw = attempt / "raw" / (variant + "-rtl-cosimulation.resources.json")
        if (step["exit_code"] != 0 or step["stop_reason"] != "process_exit"
                or step["cleanup_snapshot_error"] is not None
                or {key: value for key, value in step.items() if key not in ("variant", "phase")}
                   != json.loads(raw.read_text())):
            raise ValueError("unchanged successful raw production execution required")
        pins.append(preparation.pin(raw))
        reference = attempt / "reference" / ("search" if variant == "search" else "cache")
        observed = rtl_analysis.inspect(attempt / variant, variant, reference)
        if observed != report["components"][variant] or observed["export"]["estimate_meets_target"] is not True:
            raise ValueError("production component observation changed or misses clock target")
        pins += observed["artifacts"]
        exports[variant] = observed["export"]

    pins = list({row["path"]: row for row in pins}.values())
    preparation.unchanged(pins)
    return {"status": PASS, "errors": [], "original_result": result_pin,
            "original_result_modified": False, "pins": pins, "exports": exports,
            "component_rtl_rechecked": True, "integrated_g_admitted": False,
            "external_RTL_backpressure_tested": False,
            **dict.fromkeys(CLAIMS, False),
            "scope": "read-only component/source/ABI/clock-estimate recheck; not integrated G or route admission"}


def run(attempt, config, output):
    if output.exists():
        raise FileExistsError("fresh production recheck output required")
    checked = review(attempt, config)
    output.mkdir(parents=True, exist_ok=False)
    atomic_write_json(output / "results.json", checked)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("attempt", "config", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(run(args.attempt.resolve(), args.config.resolve(), args.output.resolve())["status"])


if __name__ == "__main__":
    main()
