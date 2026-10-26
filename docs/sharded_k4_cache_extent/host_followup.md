# Spine CC/ResPR Host-Only Follow-Up

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
- `full-inputs-v1/`, `full-matrix-v1/`: the declared 24-case follow-up.

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
