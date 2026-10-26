# Spine CC/ResPR Host-Only Follow-Up

## Final Status

Complete: the full 24-case matrix passes, with 96 paired runs including
excluded warmups. Every measured case favors Spine. Raw-log reparsing,
source/binary/input/clock/memory checks, isolated plot/profile reproduction
and visual review pass. No FPGA recompilation was needed for this follow-up.

Speedup is `median G+R wall / median Spine wall`, with one excluded warmup
and three formal pairs per case, alternating order. The fixed resident
interval includes host launch/wait, relaunch and final full-state readback;
initial preparation, residency, batch preparation/upload and CPU oracles
remain excluded on both sides. There is no sample removal or timing fit.

| Graph | SSSP | CC | ResPR |
| --- | ---: | ---: | ---: |
| AU | 4.355 | 3.868 | 3.083 |
| SU | 6.252 | 5.391 | 3.465 |
| WK | 7.099 | 9.991 | 4.069 |
| SO | 45.991 | 32.647 | 5.589 |
| PK | 74.174 | 57.562 | 3.327 |
| LJ | 96.479 | 78.626 | 5.095 |
| LJ08 | 91.021 | 76.674 | 4.494 |
| R19 | 19.512 | 16.099 | 1.492 |

**All eight ResPR cases have zero propagation rounds on both implementations
and their CPU oracles.** Their speedups demonstrate update/correction/completion,
not iterative PageRank propagation. SSSP and CC formal propagation counts
match between systems. Thresholds, clocks, bitstreams and workload semantics
are unchanged from the prior matrix. Actual ResPR clocks remain G+R DATA
149/HBM 432 MHz and Spine DATA 150/HBM 448 MHz; walls are not normalized.

The reviewed portable package is committed in `CxhAkatsukI/spine-cycle-sim`,
under
`docs/experiments/comparisons/grasu_regraph_stage_validation/evaluation_impact/cache_extent/fpga_results_v2/`.
It contains the Python plot/profile code, PNG/PDF, exact measurements,
old/new comparison, 638-file raw archive and independent review receipt.
All 24 case memory-event records show zero pressure-limit and OOM events.

For example, Spine CC AU changes from 82.3447 to 3.05053 ms; WK changes from
132.312 to 7.54539 ms. The unchanged G+R CC medians vary by at most 1.3%.
These campaigns were collected separately, not as a simultaneous per-change
A/B test. SSSP's executable is unchanged and its variation is not a code gain.
The earlier package and every failed attempt remain intact. The results do
not establish new simulator timing calibration or original-publication matching.

## Scope

The preceding bounded-cache FPGA matrix used the optimized Spine SSSP host,
but the older CC and ResPR hosts. This follow-up builds those two algorithms
from the already existing optimized Spine runtime; it changes no HLS source
and reuses the exact same bitstreams, graphs, batches and timing boundary.

Spine source: `codex/spine-resident-host-optimization-20261025`, clean commit
`cb42376663c534f0bd0c25d271737ca34893135e`. The build receipt records this
identity along with source hashes, compiler version, commands and binaries.

The existing runtime avoids uploading unused device-written scratch on its
first use, clearing the unused active-array tails every round, and restoring
the complete static metadata image. Scratch allocation occurs with initial
residency using `CL_MIGRATE_MEM_OBJECT_CONTENT_UNDEFINED`: it supplies no
batch input or precomputed frontier. Counted prefixes are produced before
consumption. Active publication, full-state readback, host correction and
inter-round relaunch remain in their existing paths and measured interval.

No new kernel, device-active implementation or simulator calibration is
claimed here. The eight frozen ResPR cases previously had zero propagation
rounds; retained round counts must accompany any new ratios. They cannot
establish iterative ResPR propagation performance.

## Ownership

| Module | Responsibility |
| --- | --- |
| `validation/cache_extent/host_followup.py` | Verify the offboard regression, build default native hosts, derive a fresh immutable plan |
| `validation/cache_extent/host_matrix.py` | Run the complete follow-up with case-local workload hashing |
| Existing `board.py`, `matrix.py` | Unchanged FPGA admission, repetition, correctness and timing |
| Delivery-review worktree's `delivery.py` | Independently reparse all saved logs and verify provenance, clocks and memory containment |

The delivery-review branch includes the existing reciprocal-CC update-count
and propagation-scope checks. Its exporter is distinct from the earlier
source-pinned runtime. Do not rewrite frozen runner hashes to switch versions.

## Reproduction

On trifoliate the fresh output root is
`/data/chuxiao/checks/spine-cc-respr-host-20261026`. Its directories are:

- `regression-v1/`: four-specialization build and offboard regression receipt.
- `default-hosts-v1/`: clean-source `-O3` CC/ResPR executables and build receipt.
- `au-inputs-v1/`, `au-matrix-v1/`: independent AU correctness/performance gate.
- `full-inputs-v1/`, `full-matrix-v2/`: the declared 24-case follow-up.
- `full-matrix-v1/`: retained pre-board validation failure. Identical path/hash
  pins with optional size metadata were incorrectly rejected as conflicting.
  The corrected deduplication accepts a missing optional size but still rejects
  inconsistent hashes or two conflicting sizes. No board execution occurred
  in this failed attempt; the fresh v2 run retains the same measured boundary.

From the integration worktree, with the recorded runtime Python path:

```bash
python3 -B -m validation.cache_extent.host_followup build \
  --source /path/to/clean/optimized-spine \
  --regression /path/to/passing/offboard-receipt --output /fresh/host-build
python3 -B -m validation.cache_extent.host_followup prepare \
  --prior /path/to/frozen/old/plan.json --build /fresh/host-build/build.json \
  --scope full --output /fresh/followup-inputs
python3 -B -m validation.cache_extent.host_matrix \
  --plan /fresh/followup-inputs/plan.json --output /fresh/followup-matrix
```

Launch the supervisor in a finite 2-GiB, zero-swap cgroup. The existing board
runner applies the dataset's 16/24/32-GiB hard cap, 2-GiB high-watermark margin,
zero swap, group OOM policy, board lock and 24-GiB system reserve. Admission
uses the existing bounded-evictable-ZFS-ARC-aware estimate, not `MemFree`.

The complete parent plan is checked before and after the matrix. Each case
rechecks all non-workload pins, its selected graph, parent plan and runner
identity before every sample. Unrelated graphs are not rehashed for every
execution. This saves file-validation work only; no measured event is moved.

Each case retains one excluded warmup and three formal pairs, alternating
execution order. An AU failure blocks the remaining datasets for that algorithm.
Failed attempts remain evidence. Final export must reparse raw logs; a
running job or a favorable warmup is not a completed result. The earlier
matrix and simulator figure packages remain unchanged.

## Earlier Independent AU Gate

Both algorithms pass correctness with one excluded warmup and three formal
paired samples. Values below are the formal wall medians, not warmup results.

| Algorithm | Spine ms | G+R ms | G+R / Spine | Formal propagation rounds per side |
| --- | ---: | ---: | ---: | --- |
| CC | 3.124300 | 11.758630 | 3.763605 | 1, 1, 1 |
| ResPR | 7.350940 | 20.705205 | 2.816674 | 0, 0, 0 |

The earlier frozen AU medians were 82.3447 ms for Spine CC and 53.8355 ms
for Spine ResPR. The new independent gate is evidence that applying the
existing host optimization removes a substantial cost on AU. It is a separate
gate, not a replacement for the completed eight-graph matrix above or a
simultaneous per-change A/B experiment.
ResPR here measures correction/completion without iterative propagation.

The separate full matrix and terminal review are complete. Its portable
plot/profile package belong to the simulator repository, under
`docs/experiments/comparisons/grasu_regraph_stage_validation/evaluation_impact/cache_extent/fpga_results_v2/`.
No paper or frozen v1 package is changed.
