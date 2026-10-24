#!/usr/bin/env python3
"""Record an explicit auto-scaled board profile, never physical timing signoff."""
import math


KEYS = {
    ("kernel", "0", "ulp_ucs/aclk_kernel_00"),
    ("kernel", "1", "ulp_ucs/aclk_kernel_01"),
    ("system", "", "hbm_aclk"),
}


def check(vitis_text, topology, *, hbm_mhz):
    if not math.isfinite(hbm_mhz) or not 0 < hbm_mhz <= 450:
        raise ValueError("explicit positive HBM profile at or below 450 MHz required")
    actual = {}
    for line in vitis_text.splitlines():
        fields = line.split(":")
        if len(fields) != 4:
            raise ValueError("complete Vitis clock rows required")
        key, value = tuple(fields[:3]), float(fields[3])
        if key not in KEYS or key in actual or not math.isfinite(value) or value <= 0:
            raise ValueError("unknown, duplicate, or invalid Vitis clock")
        actual[key] = value
    expected = dict(zip(sorted(KEYS), (150.0, 500.0, hbm_mhz)))
    if actual != expected:
        raise ValueError("build metadata differs from the explicit diagnostic profile")
    frequency = topology["clock_freq_topology"]
    rows = frequency["m_clock_freq"]
    packaged = {}
    for row in rows:
        key = row["m_type"], row["m_name"]
        value = float(row["m_freq_Mhz"])
        if key in packaged or not math.isfinite(value) or value <= 0:
            raise ValueError("duplicate or invalid packaged clock")
        packaged[key] = value
    expected_packaged = {("DATA", "DATA_CLK"): 150.0,
                         ("KERNEL", "KERNEL_CLK"): 500.0,
                         ("SYSTEM", "hbm_aclk"): float(int(hbm_mhz))}
    if int(frequency["m_count"]) != 3 or len(rows) != 3 or packaged != expected_packaged:
        raise ValueError("xclbin clock topology differs from the explicit profile")
    return {"status": "DIAGNOSTIC_CLOCK_PROFILE_RECORDED_NOT_TIMING_SIGNOFF",
            "compute_mhz": 150.0, "auxiliary_mhz": 500.0,
            "vitis_hbm_mhz": hbm_mhz, "packaged_hbm_mhz_integer": int(hbm_mhz),
            "fixed_450mhz_signoff": False,
            "scope": "metadata only; not a measured board clock or post-scale STA pass"}
