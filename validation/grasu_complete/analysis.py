"""Strict functional rows and source-based export observations, not board claims."""

import math
import re
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from .preparation import digest


COUNTS = (0, 1, 63, 64, 65, 127, 128, 129, 257)
CACHE_ROWS = ((0, 0), (16, 0), (64, 0), (4096, 0), (65536, 0), (4096, 1))


def target_period(text):
    try:
        target = Decimal(text)
        # csynth reports round the requested period to two decimal places.
        if (not target.is_finite() or target <= 0 or target.as_tuple().exponent > -2
                or target != Decimal("6.666666667").quantize(target)):
            raise ValueError("unexpected HLS target clock")
    except InvalidOperation as error:
        raise ValueError("invalid HLS target clock") from error
    return float(target)


def functional(stdout: str, variant: str) -> list[dict]:
    if variant == "search":
        rows = [tuple(map(int, match)) for match in re.findall(
            r"^SEARCH_BINDING_RTL_ROW generation=(\d+) updates=(\d+)$", stdout, re.M)]
        expected = [(generation, count) for count in COUNTS for generation in (0, 1)]
        checks = re.findall(r"^SEARCH_PIPELINE_PASS updates=(\d+) probes=(\d+) stalled=0 channels=0 "
                            r"output_blocked=0 host_vendor_keep_bits=\d+$", stdout, re.M)
        if rows != expected or [int(row[0]) for row in checks] != [count for _, count in expected]:
            raise ValueError("search fixture did not complete all eighteen ordered oracle checks")
        return [{"generation": generation, "updates": count, "probes": int(check[1])}
                for (generation, count), check in zip(rows, checks)]
    if variant not in ("cache-token", "cache-plain"):
        raise ValueError("unknown complete-G component")
    rows = [tuple(map(int, match)) for match in re.findall(
        r"^PRODUCTION_CACHE_PASS updates=(\d+) conflict=(\d+) capacity=131072 token=(\d+)$", stdout, re.M)]
    token = int(variant == "cache-token")
    if rows != [(count, conflict, token) for count, conflict in CACHE_ROWS]:
        raise ValueError("full-capacity cache state/token checks are incomplete")
    return [{"updates": count, "conflict": bool(conflict), "completion_token": bool(token)}
            for count, conflict, token in rows]


def exported(directory, variant):
    top = "bin_search" if variant == "search" else "process_cache"
    xo = directory / "candidate.xo"
    report = directory / "project/solution/syn/report" / (top + "_csynth.xml")
    root = ET.parse(report).getroot()
    period = float(root.findtext("PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod", "nan"))
    target = target_period(root.findtext("UserAssignments/TargetClockPeriod", "NaN"))
    if not math.isfinite(period) or period <= 0:
        raise ValueError("missing or unexpected HLS clock observations")
    with ZipFile(xo) as archive:
        member = top + "/kernel.xml"
        if archive.namelist().count(member) != 1 or archive.testzip() is not None:
            raise ValueError("canonical XO kernel metadata missing or corrupt")
        kernels = ET.fromstring(archive.read(member)).findall("kernel")
        if len(kernels) != 1 or kernels[0].get("name") != top:
            raise ValueError("wrong exported kernel")
        arguments = [node.get("name") for node in kernels[0].findall("args/arg")]
        expected = (["edges", *(f"binary_{i}" for i in range(4)),
                     *(f"row_offset_{i}" for i in range(4)), "edge_size", "segment_head_stream_out"]
                    if variant == "search" else ["pma_cache", "update_stream"] +
                    (["completion_token"] if variant == "cache-token" else []))
        if arguments != expected:
            raise ValueError("exported top-level argument names/order changed")
    return {"xo": str(xo), "xo_sha256": digest(xo), "report": str(report),
            "report_sha256": digest(report), "arguments": arguments,
            "estimated_period_ns": period, "target_period_ns": target,
            "estimate_meets_target": period <= target,
            "full_abi_reviewed": False, "rtl_validated": False, "routed": False}
