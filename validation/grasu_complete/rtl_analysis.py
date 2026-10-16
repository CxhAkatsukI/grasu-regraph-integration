"""Require oracle checks, every RTL transaction and exact production interfaces."""

import re

from spine_cycle_sim.experiments.evaluation_impact.common_g.search_pipeline.rtl_analysis import transactions as search_transactions
from spine_cycle_sim.experiments.evaluation_impact.common_g.cache_probe.analysis import transactions as cache_transactions
from . import abi, analysis, preparation


def inspect(directory, variant, reference):
    top = "bin_search" if variant == "search" else "process_cache"
    solution = directory / "project/solution"
    csim = solution / "csim/report" / (top + "_csim.log")
    cosim = solution / "sim/report" / (top + "_cosim.rpt")
    transaction = solution / "sim/report/verilog/result.transaction.rpt"
    functional = analysis.functional(csim.read_text(), variant)
    if not re.search(r"Verilog\s*\|\s*Pass\s*\|", cosim.read_text()):
        raise ValueError("production RTL co-simulation did not pass")
    rows = (search_transactions(transaction.read_text()) if variant == "search" else
            cache_transactions(transaction.read_text(), full=True, full_extended=True))
    if any(row["latency"] <= 0 or (row["interval"] is not None and row["interval"] <= 0) for row in rows):
        raise ValueError("invalid production RTL timing observation")
    exported = analysis.exported(directory, variant)
    interface = abi.review(directory / "candidate.xo", variant, reference)
    return {"functional": functional, "transactions": rows, "export": exported, "abi": interface,
            "artifacts": [preparation.pin(path) for path in (csim, cosim, transaction,
                          directory / "candidate.xo", directory / "project/solution/syn/report" / (top + "_csynth.xml"))],
            "rtl_validated": True, "full_abi_reviewed": True,
            "external_RTL_backpressure_tested": False, "integrated_g_admitted": False,
            "routed": False, "board_validated": False, "performance_matched": False}
