# Physical Ingress Profile

This profile is an implementation candidate, not a hardware performance result.
The independent-port simulator prediction remains unchanged.

## Constraint

The installed U55C platform's direct HMSS ingress has 33 connections, one
reserved by the platform. This is not a universal limit on AXI masters in an
FPGA: extra arbitration or a different interconnect can multiplex more clients.
The direct-link audit deliberately retains the 32-connection limit.

The prefetch adapter's exported XO has three physical master ports (even,
odd, directory). Its five logical manual-burst clients use explicit channels
for the cache/external pairs. Integer Apply has two physical masters. With
four adapters, the independent integer topology projects to 34 connections;
PageRank requires additional state/degree clients.

## Explicit Sharing

`--physical-port-policy shared-ingress` requires `sharded-k4`,
`complete-search-cache`, `prefetch-compact`, and a hardware target. It is not
the default and does not bypass the actual-XO master audit.

- GraSU's update-edge reads share each search CU's existing metadata master.
  The four CUs still execute concurrently; contention within each CU is real.
- Each adapter's directory reader uses a third logical channel on the even
  physical master. It no longer has a separate physical ingress. Cache and
  external clients retain their explicit channel identities.
- All arguments on each shared master have the same HBM address range in the
  connectivity file. Host buffer group compatibility must be checked at link
  and runtime, not assumed from C simulation.

This saves eight direct connections in the projected four-frontend topology.
Actual interfaces must be read from the newly exported XOs before linking.
Projection is not a substitute for that check, nor for resource utilization,
routed timing, bounded-channel correctness and FPGA output verification.

The fresh blocking-write repair has eleven XOs for each integer algorithm
and twelve for residual PageRank. The actual-interface audits and Vitis
system-link checks pass for all three:

| Algorithm | Actual master instances | Direct-ingress budget |
| --- | --- | --- |
| Weighted SSSP | 26 | 32 |
| Connected components | 26 | 32 |
| Residual PageRank | 32 | 32 |

Each audit is retained under
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/<algorithm>/pipeline_master_budget.json`,
where `<algorithm>` is `sssp`, `cc` or `respr`. The integer count comprises
four search, two cache, eight external PMA, eight adapter, two Apply and two
HBM-wrapper instances. Passing these checks is not a routed timing or board
pass.

## Placed Resource Check

At 17:48 CST on 2026-10-24, the fresh SSSP relink has completed
`place_design` with zero errors. The fourth Little CU moved from SLR0 to
SLR1; no XO, clock or cache capacity changed. The actual fully placed report
confirms the previously screened URAM distribution:

| Resource | SLR0 | SLR1 | SLR2 |
| --- | --- | --- | --- |
| URAM used / available | 320 / 320 | 128 / 320 | 320 / 320 |
| Occupied CLB sites | 88.61% | 80.40% | 86.18% |
| CLB LUT utilization | 43.95% | 39.99% | 45.11% |

The SLR0/SLR1 crossing uses 64.05% of available SLLs; SLR1/SLR2 uses 40.80%.
The raw report is
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/route-slr-v2/sssp/work/link/vivado/vpl/prj/prj.runs/impl_1/slr_util_placed.rpt`.
The adjacent `runme.log` also retains the high-congestion warning. This
milestone establishes local resource placement, not routed connectivity or
150-MHz timing closure. Physical optimization and routing are still pending
at this timestamp, and no fresh board performance result is claimed.

## Evidence Boundary

Arbitration and burst contention differ from independent ingress. A matching
simulator profile must model those effects before these builds can be called
cycle-aligned. The same caveat applies to the selector pipeline and held-input
register described in [the repair log](REPAIR.md). We do not silently relabel
the frozen model as the physical implementation.
