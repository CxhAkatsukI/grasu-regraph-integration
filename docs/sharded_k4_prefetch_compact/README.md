# Sharded K4 Prefetch/Compact Source Port

## Status And Reading Order

This default-off source candidate ports the frozen simulator profile at
`567a37a406dddea8917cbdc8ba8c59d8cee87198`, including its
`prefetch_gather_reuse` input/Gather path. It does not replace the previously
routed design, reproduce publication performance, or establish FPGA timing.

Read the source map below, the validation scope, then the full-system budget
blocker before running a build. The simulator repository owns the cross-repo
handoff in `docs/implementation/hls_simulator_alignment/`.

## Source Map And Contract

| Owner | Responsibility |
| --- | --- |
| [Adapter types](../../kernels/pma_prefetch_compact/types.hpp) | Word, segment and directory-tile formats; explicit capacities |
| [Readers](../../kernels/pma_prefetch_compact/readers.hpp) | Two 1024-row directory tiles; independent even/odd readers; 512 returned-or-reserved lines per bank; at most 16 parents of at most 16 beats |
| [Join](../../kernels/pma_prefetch_compact/join.hpp) | Source-order traversal, up to eight consecutive empty rows skipped, explicit release credits and requested two-cycle segment register |
| [Compactor](../../kernels/pma_prefetch_compact/compactor.hpp) | Stable 16-lane selection into 32 lanes, eight edges per packet, no mixed 4096-source windows, finite three-packet publisher |
| [Adapter top](../../kernels/pma_prefetch_compact/top.cpp) | Three AXI masters per frontend: directory, even PMA and odd PMA; finite DATAFLOW channels |
| [Framed Scatter](../../kernels/regraph_stream_little_gs/framed/scatter.hpp) | Independent source-window preload while input is empty; two windows and eight cache replicas; TLAST termination |
| [Reusable Gather](../../kernels/regraph_stream_little_gs/framed/gather.hpp) | Existing policy reductions, explicit forwarding and full publication/clear; first invocation reset only |
| [Framed top](../../kernels/regraph_stream_little_gs/framed/run.hpp) | Scatter/Gather/publication composition, separately owned from the legacy implementation |
| [Integer Apply](../../kernels/regraph_sssp_apply_status/prefetch.hpp) | SSSP/CC explicit-burst old-state read, Apply and independent write port; read-before-write completion tokens for aliased BOs |

The physical PMA, dummy slots and source-directory work are not removed. There
is no host-created active-source shortcut. Shards contain local destinations;
the new framed path must not subtract the global destination base again.

Inputs must come from a validated monotone, 16-slot-aligned row directory.
An invalid final extent becomes an empty frame; the adapter has no error-status
port and does not validate every row. That fallback is not correctness admission
for malformed external inputs.

Kernel names and the adapter's five memory-argument positions are retained,
but the adapter uses a 512-bit directory ABI and burst masters. This is not a
drop-in replacement for old XOs/hosts. Build the host with `--prefetch-compact`.
It pads row buffers, resets each Gather CU only on first use, and aliases the
integer Apply's additional argument 7 to its existing state BO. Per-CU event
dependencies serialize reuse. Existing defaults remain unchanged.

The opt-in compile macro is `GRASU_REGRAPH_PREFETCH_COMPACT=1`; the build
generators select it through `--adapter-policy prefetch-compact`. The policy
is restricted to `sharded-k4`. Do not mix it with legacy slot-count termination
or the old Apply ABI.

## Validation On 2026-10-24

| Check | Result and limit |
| --- | --- |
| Independent adapter | 132 cases in each of weighted, destination-only and unit-weight formats: 396 checks; 48,244 packets per format |
| Framed ReGraph | SSSP, CC and PR policy; six invocations with preconstructed packets and six with the actual new adapter per policy: 36 checks |
| Integer Apply | SSSP/CC, partitions 0/1/2, separate and identical read/write allocations: 12 checks |
| Native hosts | Four algorithms compile with `-Wall -Wextra -Werror`; six-destination-partition prepare-only/CPU-oracle checks pass with both legacy and candidate profiles |
| Candidate build generation | Four algorithms, `hw`/`hw_emu`; source flags, hashes, connectivity, shell syntax and link admission checked |
| Legacy build generation | Existing four-algorithm compile/link/connectivity commands remain byte-identical to the pre-profile control |
| AXI budget gate | Synthetic XO metadata verifies 34/39/40-master rejection before sourcing tools or launching the linker; this is not new synthesized XO evidence |

Adapter tests include empty graphs, partial directory lines, tile boundaries,
ring wrap, cache/external transitions, long segments, all-dummy inputs, local
destination limits, stable ordering and final markers. Framed tests include
repeated empty invocations and source-window changes. PR checks use an exact
binary-fraction oracle; the Apply tests use the established `applyFunc` and
check its plumbing, not an independently rederived algorithm implementation.

The aliased Apply test initially failed: a write burst could be announced
before the old-state read completed. The fix passes a per-burst read-complete
token to the writer. A C-simulation-only mutex also protects the vendor burst
model's non-thread-safe pointer bookkeeping; it is absent from synthesized
logic. The original failure is retained in the simulator handoff evidence.

C++ streams are not finite RTL co-simulation: the framed output reaches
32,768 queued items in the C model. Source FIFO depths, explicit reservations
and credit checks do not prove finite-channel RTL liveness or achieved II.
Likewise, `LATENCY` directives and publisher countdown iterations are requests,
not measured two-cycle hardware schedules.

## Full-System Link Is Not Admitted

| Source-derived projection | SSSP/CC | FullPR | ResPR |
| --- | ---: | ---: | ---: |
| Complete G update | 18 | 18 | 18 |
| Four adapter frontends | 12 | 12 | 12 |
| Shared source wrapper | 2 | 2 | 2 |
| Apply | 2 | 2 | 3 |
| Degree update and PR source preparation | 0 | 5 | 5 |
| Total AXI master instances | **34** | **39** | **40** |
| Current U55C user budget | 32 | 32 | 32 |

These are source/interface estimates, not newly compiled XO counts. Integer R
alone uses 16 masters and three full-state copies; original A4 uses 13 masters
and four copies. Four frontends do not imply identical resources.

Both generated hardware link scripts audit actual XO metadata before tool
setup. Missing XOs or an exceeded budget stop the link. Raising the audit limit
does not create physical ports and is not a solution. Do not serialize or merge
ports silently to claim the frozen simulator topology has been preserved.

Full-system integration still needs an explicit physical sharing/integration
decision, matching simulator arbitration, finite RTL checks, synthesis/interface
inspection, routing and common-state resident FPGA comparisons. PR-specific
Apply/source-prepare schedules have not been newly ported to explicit-burst
owners here. No source candidate is promoted to calibrated hardware evidence.

## Reproduce Functional Checks

Run from the repository root, with actual dependency roots and fresh output
directories. Each command can be wrapped with
`prlimit --as=8589934592 -- timeout 1200` for these small C++/host checks.
This per-process limit is not an aggregate FPGA-build memory policy.

```bash
export GRASU_ROOT=/home/chuxiao/GraSU
export REGRAPH_ROOT=/home/chuxiao/regraph/ReGraph
export HLS_INCLUDE=/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include
bash scripts/check_pma_prefetch_compact.sh --out-dir /data/chuxiao/checks/adapter-NEW
bash scripts/check_regraph_framed.sh --out-dir /data/chuxiao/checks/framed-NEW
OUT_DIR=/data/chuxiao/checks/host-NEW bash scripts/check_sharded_k4_native_host.sh --prefetch-compact
python3 -m unittest discover -s tests -p test_pma_adapter_selection.py -v
python3 -m unittest discover -s tests -p test_check_pipeline_master_budget.py -v
```

## Generate Later Build Packets

These commands **only generate commands/configurations**. They do not start
Vitis. Use distinct fresh roots for each algorithm and select the correct
platform paths. Generate the other integer algorithm by changing
`weighted_sssp` to `connected_components`; change `residual_pagerank` to
`full_pagerank` for dense PR.

```bash
bash scripts/prepare_pure_hw_pipeline_build.sh --target hw \
  --algorithm weighted_sssp --pipeline-mode sharded-k4 \
  --grasu-implementation complete-search-cache --adapter-policy prefetch-compact \
  --kernel-frequency 150 --build-root /data/chuxiao/builds/gr-sssp-NEW
bash scripts/prepare_pagerank_pipeline_build.sh --target hw \
  --algorithm residual_pagerank --pipeline-mode sharded-k4 \
  --grasu-implementation complete-search-cache --adapter-policy prefetch-compact \
  --kernel-frequency 150 --build-root /data/chuxiao/builds/gr-respr-NEW
```

Inspect `inputs.tsv`, `manifest.env` and `config/` before any expensive work.
New-profile generated scripts permit `GRI_VITIS_SETTINGS` to override the tool
settings path. Compile-only XO investigation can use `compile_commands.sh`
after a separate memory admission/containment decision; **do not launch
`run_build.sh` expecting an admitted complete bitstream**. No routing was
started during this source handoff, and no figures or paper text were changed.
