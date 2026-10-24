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

The shared-ingress SSSP packet now has all eleven XOs. The actual-interface
audit counts 26 master instances: four search, two cache, eight external PMA,
eight adapter, two Apply and two HBM-wrapper instances. Its audit artifact is
`/data/chuxiao/builds/gr-prefetch-shared-channels-trif-20261024/sssp/pipeline_master_budget.json`.
This is an interface-budget pass only; PR needs its own actual-XO audit.

## Evidence Boundary

Arbitration and burst contention differ from independent ingress. A matching
simulator profile must model those effects before these builds can be called
cycle-aligned. The same caveat applies to the selector pipeline and held-input
register described in [the repair log](REPAIR.md). We do not silently relabel
the frozen model as the physical implementation.
