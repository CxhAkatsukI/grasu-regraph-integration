# Bounded Cache Transfers And Resident FPGA Comparisons

## Scope And Status

This study changes the GraSU input path used by the actual sharded K4 system.
It does not retune ReGraph to reproduce a published number. The original
ReGraph publication-scale comparison remains about 2.47 times slower in our
ported hardware configuration; that disclosed gap is accepted for this study,
not renamed a successful paper reproduction.

| Gate | Status at this checkpoint |
| --- | --- |
| Cache state, valid-span boundaries, token/plain bindings | Passed |
| Fresh HLS/XO and exact exported-interface review | Passed |
| Three native hosts, legacy/new ABI selection | Built |
| Simulator bounded-span state and traffic regression | Passed |
| Three revised G+R hardware links | Queued under finite memory admission |
| Fresh sparse-apply Spine ResPR hardware | Memory-safe retry queued; previous attempt stopped at the live reserve |
| Revised-kernel SSSP/CC/ResPR x eight FPGA pairs | Pending, zero admitted pairs |

This is a source/export checkpoint, not a completed board result. Live
machine-readable results below supersede this snapshot when builds finish.
Failed or interrupted attempts remain in their own directories.

## What Changes

The physical cache remains sixteen URAM banks with 131072 512-bit words.
Previously every launch transferred the entire cache even for a short PMA
half. The new last unsigned scalar, `valid_segments`, limits preload and
writeback to the populated span, rounded up to sixteen banks. It does not
change the update algorithm, comparison stage, transfer II, sorting, cache
capacity, adapter layout, ReGraph topology, or requested 150-MHz clock.
Empty spans still consume completion and preserve required token behavior.

The host derives the extent from each shard's actual even/odd segment count,
clamped to physical cache capacity. SSSP/CC add argument 3 after the completion
stream; PageRank adds argument 2 without a token stream. Export review permits
only that scalar and its necessary AXI-Lite control aperture/register change.
An old argument count selects the legacy ABI; any other count fails explicitly.

Both native hosts now share
[`tools/sharded_cache_runtime.hpp`](../../tools/sharded_cache_runtime.hpp).
Initial PMA, row/source metadata and update buffers are explicitly migrated
before any update. `GRASU_SHARDED_PREMIGRATE_INPUTS=1` is the default;
`0` is retained as a matched diagnostic control. Migration after updates is
forbidden because stale host PMA data could overwrite updated device state.

## Build And Evidence Ownership

Select the new ABI explicitly with
`--grasu-implementation complete-search-cache-bounded` in either build
generator. Existing `legacy-direct-cache` and `complete-search-cache` packet
defaults remain unchanged. The bounded candidate requires sharded K4, full
131072-segment physical cache and target `hw` or `hw_emu`.

[`validation/cache_extent/`](../../validation/cache_extent/) owns the study:

| Module | Responsibility |
| --- | --- |
| `study.py`, `abi.py` | Frozen source checks, HLS export, exact ABI review |
| `route.py`, `spine.py` | Fresh cache links and sparse Spine ResPR build |
| `matrix_inputs.py`, `configuration.py` | Immutable 24-case matrix and controls |
| `board.py`, `matrix.py` | Board admission, correctness, repeated paired runs |
| `delivery.py` | Revalidate and package terminal board evidence without replacing missing rows |

Live root: `/data/chuxiao/builds/grasu-cache-extent-20261025`:

- `source-v1/results.json`: executable source checks.
- `hls-v1/results.json`: both fresh cache exports, not routed timing.
- `route-v3/sssp/`: fresh SSSP link retry after a live-reserve stop.
- `route-v3/{cc,respr}`: links to the unchanged, live `route-v2` jobs.
- `spine-respr-v3/`: fresh sparse-apply Spine ResPR retry and source provenance.
- `matrix-inputs-v5/plan.json`: 24 cases, actual binary/source/input pins.
- `matrix-v4/{results.json,summary.csv}`: all-case status and eventual results.
- `host-control-au-v1/`: new host with an OLD G+R kernel, not the new matrix.

The `spine-respr-v2` attempt completed three HLS XOs but was stopped during
Vivado synthesis when system available memory fell below the 24-GiB live
reserve (`stop_reason=live_memory_reserve`, minimum 24,889,225,216 bytes).
This was a watchdog stop, not a reported RTL/synthesis error. Its sources,
XOs and raw logs remain intact. The existing fresh-build entry point rejects
reuse of a provenance directory, so `v3` uses a fresh directory rather than
overwriting the failed attempt. `matrix-v2` was interrupted with zero board
pairs. The later `route-v2/sssp` attempt was also stopped at the live reserve:
minimum available memory was 24,537,829,376 bytes, with a process-tree peak
of 5,192,324 KiB and no reported synthesis/routing error. Its logs remain
intact. `route-v3/sssp` is a fresh retry; `route-v3/{cc,respr}` are explicit
links to the unchanged `route-v2` jobs, not copies or old-kernel fallbacks.
`matrix-v3` was interrupted before any board pair; `matrix-v4` now uses
`matrix-inputs-v5` to require the SSSP retry and the `v3` Spine build.

Each compiler tree has a 56-GiB hard cap, 52-GiB high watermark, zero swap
and group OOM termination. Admission preserves 24 GiB of system memory and
counts the complete finite budgets of other admitted builds in addition to
the new build's budget. Historical G+R process
trees peaked around 41--45 GiB. More than one compiler is allowed only when
the live budget admits it; another FPGA tool merely existing is not a block.
Board runs use separately bounded 16--32-GiB groups, the same reserve and a
device lock. Interrupted `v1` attempts were never promoted to passing results.

## Measurement Contract

Every pair uses the same graph, old converged state, eight logical updates
and convergence requirement. The resident wall-time interval includes GraSU
updates, adapter/ReGraph propagation, host launch/wait and inter-round
relaunch, and final readback. Initial graph/PMA creation, initial residency,
old-state loading, batch preparation/upload and CPU oracles are outside both
systems' resident interval and retained separately. This is not whole-application
setup-inclusive latency. Spine still has host orchestration; it is not a
claimed autonomous persistent device.

For each algorithm, AU must pass first before the remaining seven datasets.
One warmup and three measured pairs alternate order. Actual positive data
clock frequencies are recorded even if below the requested 150 MHz. A failed
correctness, old/new convergence or state-mismatch check cannot produce a
speedup. No old G+R bitstream may fill a missing new-kernel row.
The G+R hosts use GCC 15.2/C++17 `-O2`; existing Spine resident hosts use
GCC 15.2 `-O3`. This difference is disclosed rather than silently hidden.

## Reproduce Or Inspect

Use fresh output directories and identical source/input pins for replay.
Do not execute a compiler outside the cgroup/admission runner.

```bash
python3 -m unittest discover -s tests -p 'test_cache_extent.py'
python3 -m unittest discover -s tests -p 'test_grasu_kernel_selection.py'
python3 -m unittest discover -s tests -p 'test_grasu_complete_source_identity.py'
python3 -m validation.cache_extent.route --help
python3 -m validation.cache_extent.spine --help
python3 -m validation.cache_extent.matrix_inputs --help
python3 -m validation.cache_extent.matrix --help
systemctl --user status gr-cache-extent-sssp-20261025-v3.service \
  gr-cache-extent-cc-20261025-v2.service \
  gr-cache-extent-respr-20261025-v2.service \
  spine-cache-study-respr-20261025-v3.service \
  gr-cache-extent-matrix-20261025-v4.service
```

The simulator repository's companion guide is
`docs/experiments/comparisons/grasu_regraph_stage_validation/evaluation_impact/cache_extent/README.md`.
It separates source-grounded component predictions from hardware timing.

## Terminal Delivery

After the matrix terminates, create one reviewable folder:

```bash
python3 -m validation.cache_extent.delivery \
  --matrix <matrix-v4/results.json> --output <fresh-delivery-directory>
```

A running matrix is rejected. Both complete and
incomplete terminal matrices retain all 24 rows; only correctness-admitted
board pairs receive speedups. The exporter rechecks source/binary/workload
hashes, reparses all four paired raw logs, and recomputes medians before
copying reports, manifests, clock dumps and bounded-size logs. Graphs,
bitstreams and compiler trees are indexed by hash rather than copied.
`summary.csv` includes actual data frequencies and `README.md` explains the
resident boundary and outstanding limitations. An incomplete package does not
complete the FPGA goal. Test with `python3 -m unittest discover -s tests -p
'test_cache_extent_delivery.py'`.
