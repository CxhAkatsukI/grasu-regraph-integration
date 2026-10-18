# Complete GraSU Search/Cache Source Candidate

This directory owns the production-source candidate for the reviewed 64-context
search and full-capacity registered URAM cache. Fresh functional execution,
HLS synthesis/XO export, full exported-interface review and component Verilog
co-simulation pass for the prior search and both cache bindings. The current
cache comparison-stage candidate needs its own fresh checks below. **Integrated metadata
refresh/backpressure, full resource/timing, production routing and board
validation remain open**.
The ongoing diagnostic route uses frozen exported XOs, not these relocated
sources. Keep those evidence classes separate.
The [production-source routing entry](../../validation/README.md#production-source-experimental-route)
now independently rechecks this owner's exported cores and connected state
before preparing a separate experimental route. It does not promote the old
diagnostic bitstream or admit integrated RTL and board performance.

## Code Map

| Owner | Responsibility |
| --- | --- |
| `search_binding/top.cpp`, `top.hpp` | Eleven-argument `bin_search` ABI; one edges master and one shared metadata master |
| `search_pipeline/types.hpp` | Packet formats, 64 contexts, eight groups, 32 metadata credits |
| `search_pipeline/search_worker.hpp` | Per-context binary-search state machine |
| `search_pipeline/workers.hpp` | Ordered input distribution and output merge |
| `search_pipeline/transport.hpp` | Group arbitration, metadata memory service and response routing |
| `search_pipeline/network.hpp` | Finite-stream dataflow composition; explicit host-harness selection |
| `cache_bank.hpp`, `cache_lane.hpp` | Bank types and registered sorted-segment updates |
| `cache_pipeline.hpp` | Full preload/update/writeback, 16 URAM banks, 131072 512-bit words |
| `process_cache.cpp` | Cache AXI/AXIS binding with pipeline-specific completion-token ABI |
| `provenance.json` | Frozen original hashes and the exact permitted binding transformations |

The original source owner is the simulator's
`cpp/tests/evaluation_impact/common_g/hls/` at commit `bb14f05`.
The search algorithm, arbitration, stream depths, cache algorithm, capacity
and preload/writeback loops were not retuned during promotion. The wrapper
changes are enumerated in `provenance.json`; the source-identity test reverses
them and checks the original hashes without depending on a live simulator tree.
Any later algorithm change needs a new identity and functional/RTL evidence.

## Cache Comparison-Stage Candidate

The ResPR physical route misses 150-MHz setup timing by 0.107 ns. Its longest
reported path runs from a URAM read through comparison and lane selection;
the 1.334-ns HLS estimate did not establish closure of this physical path.
`cache_lane.hpp` now gives the sixteen unsigned comparisons an explicit
one-cycle, non-inlined pipelined helper before lane selection. The requested
whole-edit latency remains three cycles with II=1. Fresh HLS confirms a
one-cycle comparison helper and three-cycle edit, both with II=1; the edit
estimate is 0.880 ns versus 1.334 ns before. The top estimate remains 4.867 ns.
This schedule is not evidence that the physical path now meets timing.
Cache capacity, sorting/insertion/deletion
semantics, bank assignment, AXI/AXIS ABI and completion token are unchanged.
The exact reversible source changes are recorded in `provenance.json`.

This candidate does not inherit the previous component RTL or physical-timing
approval. The ongoing routes still consume frozen earlier sources. First check
the segment oracle, both full-state cache bindings and fresh HLS scheduling;
then obtain fresh component RTL before integrating new exports into a route.
Neither a requested register stage nor a passing oracle proves routed timing.

Fresh checks for this candidate now pass: 26112 segment-oracle cases, both
full-state host cache bindings, HLS, eighteen search plus six transactions per
cache binding in component Verilog, independent RTL/interface re-admission
and connected host state. The fresh SSSP link packet uses these exact exports;
CC/ResPR/FullPR have their own v4 source compilation. These checks still do not
establish integrated finite-stream RTL, physical timing or board performance.
See the [latest validation checkpoint](../../validation/README.md#latest-registered-comparison-candidate)
for raw evidence and exact result/service identities.

`tests/grasu_complete_cache_segment_tb.cpp` checks all occupancy counts 0--16,
unsigned key boundaries and deterministic random segments/keys against a
`std::lower_bound` insertion/deletion oracle. It also checks every comparison
bit independently. This supplements the existing repeated/conflicting-bank
full-capacity fixture; it is not an FPGA performance test.

## Explicit Selection

Both build generators accept:

```text
--grasu-implementation legacy-direct-cache  # unchanged default
--grasu-implementation complete-search-cache
```

The complete candidate requires `--target hw` or `hw_emu`,
`--pipeline-mode sharded-k4` and `--max-cache-segment 131072`.
Unsupported combinations fail before an output directory is created. Example
from the integration repository root, with the correct external dependencies:

```bash
GRASU_ROOT=/path/to/frozen/GraSU REGRAPH_ROOT=/path/to/compatible/ReGraph \
  scripts/prepare_pure_hw_pipeline_build.sh \
  --target hw --pipeline-mode sharded-k4 --algorithm weighted_sssp \
  --kernel-frequency 150 --max-cache-segment 131072 \
  --grasu-implementation complete-search-cache --build-root /path/to/fresh/build
```

Use `connected_components` with that generator. Use
`prepare_pagerank_pipeline_build.sh` with `full_pagerank` or `residual_pagerank`
for PageRank. These commands only generate packets; they do not run `v++`.
Do not reuse an existing build directory or relabel an old XO as a new build.
Freeze the generated sources, flags, headers and dependencies before launching
any compiler. Memory admission and cgroup containment remain required.

SSSP/CC retain the existing cache completion token and completion barrier.
PageRank retains its existing two-argument cache ABI: no token is emitted into
an unconnected stream. This plain-cache variant now also has fresh isolated
component Verilog/interface checks; those are not integrated PageRank or
PageRank board evidence. Both variants run the same full registered cache
pipeline; neither may define the direct-cache shortcut.

`manifest.env` records the implementation, both source paths, capacity and
completion-token selection. `inputs.tsv` hashes the selected sources, all nine
owned headers, the selection helper and the actual upstream `kernel_config.h`.
It records source selection as **not hardware evidence**. External ReGraph
algorithm headers still need their own completeness/build checks; generator
success does not certify them. The public author's ReGraph checkout alone,
for example, does not provide the local weighted-SSSP UDF.

## Non-Synthesis Harness

The search network requires concurrent finite streams in host simulation.
Outside synthesis it fails explicitly unless `GRASU_SEARCH_HOST_HARNESS`
names a compatible harness header. The diagnostic finite host harness uses
the test stream-delegate extension, which stock vendor `hls::stream` lacks.
There is no claim that moving this source makes stock `sw_emu` work.
The synthesis branch excludes the harness and retains the original dataflow.
The cache includes the configured upstream `kernel_config.h`, not a
fixture-relative `upstream/` path.

## Verification Gates

Fresh executable functional tests and real HLS-driver export are owned by
[`validation/grasu_complete/`](../../validation/README.md). That guide defines
the three independent acceptance stages, frozen source-reference checks, explicit
external search fixture and concurrent memory admission. Source selection alone
does not admit the production candidate to routing or board experiments.

```bash
python3 -m unittest discover -s tests -p 'test_grasu_kernel_selection.py' -v
python3 -m unittest discover -s tests -p 'test_grasu_complete_source_identity.py' -v
```

The selection tests generate all four algorithms for both hardware targets,
check hashes and token flags, reject unsupported configurations and compare
legacy compile/link/connectivity packets byte-for-byte with integration
commit `6f5ebf2b0679f04f4f6e035e850fce7b6043a660`.
`tests/grasu_complete_abi.cpp` checks the search declaration and both cache
binding types with the installed Vitis host headers. It does not compile the
search dataflow body, run HLS scheduling, check RTL AXI registers/bundles, or
establish numerical equivalence. Do not define `__SYNTHESIS__` in this host check.

```bash
g++ -std=c++14 -fsyntax-only -DCACHE_BANK_REGISTERED \
  -DGRASU_MAX_CACHE_SEGMENT=131072 -DGRASU_ENABLE_COMPLETION_TOKEN \
  -Wno-unknown-pragmas -Wno-deprecated-declarations \
  -isystem /path/to/Vitis_HLS/include -isystem /path/to/Vitis_HLS/include/etc \
  -I/path/to/GraSU/GraSU/GraSU_kernels/src tests/grasu_complete_abi.cpp
```

Repeat without `-DGRASU_ENABLE_COMPLETION_TOKEN` for the PageRank binding.

Campaign records live outside source in
`/data/chuxiao/experiments/baseline_hardware_validation_20261015/`:

- `g-production-source-selection-v1`: retained failure because the historical
  default ReGraph symlink target no longer exists; it is not an algorithm failure.
- `g-production-source-selection-v2`: source-selection, identity and three legacy
  generator/relink regressions pass with explicit external ReGraph configuration.
- `g-production-source-selection-v3`: retained failed attempt to parse synthesis
  headers with GCC; vendor synthesis intrinsics are not GCC host intrinsics.
- `g-production-source-selection-v4`: retained failed direct invocation of the
  vendor synthesis frontend without the HLS driver's injected settings. Neither
  attempt establishes a kernel defect or a passing synthesis gate.
- `g-production-source-selection-v5`: **PASS**, both host binding checks and
  all five source generator/identity regressions. The job had a 1-GiB hard
  limit, 768-MiB high watermark, zero swap and group OOM termination; all memory
  event counters remained zero. Maximum individual child RSS was 219536 KiB.
  `results.json` preserves commands, exit codes, elapsed times and raw-log paths;
  `memory_events.json` preserves containment observations. These are source
  checks, not performance or hardware evidence.

Fresh `g-production-functional-v5`, `g-production-hls-v3` and
`g-production-rtl-v2` now pass isolated functional execution, synthesis/export
and component Verilog/interface checks. The RTL matrix includes eighteen
search transactions and six full-state transactions for each cache binding.
The next acceptance gates are integrated finite-stream/backpressure RTL,
timing/utilization review, then resident-state continuous-batch board tests.
Metadata contents changing at the same device address need an explicit test;
switching between prebuilt metadata buffers does not establish that behavior.
Only accepted fresh outputs may replace the frozen diagnostic exports.
The independent component re-admission and separate production storage screen
are described in the [validation guide](../../validation/README.md). Neither
promotes isolated component success to complete-G or board admission.
