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
| HLS/XO and exact exported-interface review | Fresh `hls-zfs-v3` export passed; new link ABI review passed |
| Three native hosts, legacy/new ABI selection | Built |
| Simulator bounded-span state and traffic regression | Passed |
| Three revised G+R hardware links | `route-zfs-v2`: SSSP routed with passing final timing; CC and ResPR links running |
| Fresh sparse-apply Spine ResPR hardware | Compiled and independently audited; independent AU board correctness passed; not a paired speedup |
| Revised-kernel SSSP/CC/ResPR x eight FPGA pairs | Pending, zero admitted pairs |

This is a source/export/SSSP-route checkpoint, not a completed board result. Live
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
| `spine_recovery.py` | Audit a successful route rejected only by dependency postprocessing; preserve the failed attempt |
| `spine_smoke.py` | Check the audited Spine ResPR on the frozen AU input independently; never reuse it as a paired speedup sample |
| `matrix_inputs.py`, `configuration.py` | Immutable 24-case matrix and controls |
| `board.py`, `matrix.py` | Board admission, correctness, repeated paired runs |
| `delivery.py` | Revalidate and package terminal board evidence without replacing missing rows |

Live root: `/data/chuxiao/builds/grasu-cache-extent-20261025`:

- `source-v1/results.json`, `hls-v1/results.json`: original passing component
  checks and exports. Their runner hashes predate the corrected memory guard;
  they are retained, not repinned or reused as a current validation gate.
- `source-zfs-v3/results.json`: passing executable checks with the corrected guard.
- `hls-zfs-v3/results.json`: both fresh passing cache exports; not routed timing.
- `route-zfs-v2/{sssp,cc,respr}/`: new links with exact ABI reviews and bounded admission.
- `spine-respr-zfs-v1/`: successful compiler output with a retained wrapper failure.
- `spine-respr-zfs-audit-v1/`: independent artifact/provenance/clock audit;
  `ROUTED_NOT_BOARD_TESTED`, not board correctness or a speedup.
- `spine-respr-au-smoke-v1/`: separately contained single-system correctness
  check of that audited binary while G+R links; `SPINE_AU_RESPR_SMOKE_PASS`.
  Its status is independent of the matrix and replaces no paired sample.
- `matrix-inputs-zfs-v3/plan.json`, `matrix-zfs-v3/`: current frozen 24-case plan
  and runner. The SSSP AU task has started; no board pair has passed yet.
- `matrix-inputs-zfs-v2/plan.json`, `matrix-zfs-v2/`: superseded, stopped before
  any board pair after the old wrapper report blocked the eight ResPR rows.
- `route-v1` through `route-v4`, `route-zfs-v1`: retained attempts, not live results.
- `matrix-inputs-v1` through `matrix-inputs-v6`, `matrix-inputs-zfs-v1`:
  historical plans; none establishes completed FPGA comparisons.
- `matrix-v1` through `matrix-v5`: stopped/incomplete matrices, zero board pairs.
- `host-control-au-v1/`: new host with an OLD G+R kernel, not the new matrix.

### Corrected ZFS Memory Accounting

On trifoliate, Linux `MemAvailable` omits most reclaimable ZFS ARC data.
The previous guard therefore stopped jobs prematurely: btop showed about
137 GiB available while the raw Linux counter approached the 24-GiB reserve.
Those stops are not evidence of physical memory exhaustion or RTL errors.

The shared, source-pinned probe now estimates:

```text
allowance = min(mru_evictable_data + mfu_evictable_data,
                max(0, ARC_size - ARC_c_min), MemTotal - MemAvailable)
available = MemAvailable + allowance
```

It excludes ARC metadata and anonymous entries, preserves `c_min`, never
exceeds physical RAM, and falls back to Linux-only accounting if ARC counters
are missing or invalid. This is an admission estimate, not a guarantee that
every byte is instantly allocatable. No ZFS parameters were changed. Both
the watchdog and the Spine shell preflight use the same pinned probe.

| Retained attempt | Stop or rejection |
| --- | --- |
| `spine-respr-v2` | Old raw-only reserve, minimum 24,889,225,216 bytes; three HLS XOs completed |
| `spine-respr-v3` | Old raw-only reserve, minimum 25,444,921,344 bytes |
| `route-v2/sssp` | Old raw-only reserve, minimum 24,537,829,376 bytes |
| `route-v2/respr` | Old raw-only reserve, minimum 25,288,192,000 bytes; no cgroup OOM |
| `route-v2/cc` | Old raw-only reserve, minimum 25,756,872,704 bytes |
| `route-zfs-v1/*` | Rejected changed runner hashes in `hls-v1`; no link started |
| `source-zfs-v2` | Small-stage peer validator rejected the existing bounded 56-GiB Spine job |

The peer validator now accepts finite link jobs while retaining the source
stage's exact 1-GiB and HLS stage's exact 8-GiB own limits. Fresh source and
HLS validation must precede another link attempt; historical pins are never
rewritten to pass. Revisions: simulator main `341ad41`, actual runtime branch
`07f8863`, G+R guard `7975080` and peer fix `196060f`, Spine shell `9e5cb2b`.

Three historical G+R outputs received independently copied Vivado IP caches from
the corresponding completed old build. These are tool-validated compilation
caches, not old bitstreams or substituted cache XOs. Each output's
`ip-cache-seed.json` records the original directory and a byte-matched file
inventory; the copies share no writable hardlinks with the original evidence:

| New output | Original cache under `gr-prefetch-blocking-axis-trif-20261024` | Inventory SHA-256 |
| --- | --- | --- |
| `route-v3/sssp` | `route-slr-v2/sssp/ip_cache` | `67103cdd3d326d0df4213f142062edcef2e90ebe1271b142ab034346cf389006` |
| `route-v2/cc` | `route-slr-v2/cc/ip_cache` | `1e298e57f60c171fb4ddf99aa54d49162a484f5993b71a25ba9466b5dc84104d` |
| `route-v4/respr` | `route-live-v1/respr/ip_cache` | `95a4a97b7f06830eb713eb4fa7a243161918628475e650b2d7e403c6aaf5cb19` |

On 2026-10-25 the current, still-queued `route-zfs-v2` CC and ResPR outputs
received private copies from the same original caches above. The retained
helper, `seed-queued-ip-cache.py` under the live root, holds the supervisors'
shared `compiler-reservations/admission.lock`. Before and after copying it
checks the supervisor's live PID/start identity, waiting status, absent
admission lease and absent compiler outputs. Thus it cannot seed a compiler
that has already been admitted. It verifies the exact prior member set and
each file's size/SHA-256, and rejects shared writable inodes.

| Current output | Files | Logical bytes | New seed-report SHA-256 |
| --- | ---: | ---: | --- |
| `route-zfs-v2/cc` | 848 | 937262532 | `71da84390731441152ca71db2917b01345602f85fe0ea0bbf3b0f4e78be6245c` |
| `route-zfs-v2/respr` | 909 | 1439763700 | `e14849683a398ff63bc29a1fdd40fb5f1f1a80f1c268f42e50ec5e661006867c` |

Both `ip-cache-seed.json` reports retain the full initial file inventory,
source-inventory hash and helper hash
`8a74d96cda17e6af361ff5f04e35e6131eb920524cd8c61af4d4f35682e99a64`.
The two finite 2-GiB/zero-swap copy jobs peaked below 12 MiB. No current
kernel XO, configuration or pinned runner was changed, and neither running
SSSP nor Spine project was touched. Vivado validates fingerprints and may
update its private cache after admission; these inventories are the seed
state, not claims about its eventual contents or FPGA timing.

Each compiler tree has a 56-GiB hard cap, 52-GiB high watermark, zero swap
and group OOM termination. Admission preserves 24 GiB of system memory and
counts the complete finite budgets of other admitted builds in addition to
the new build's budget. Historical G+R process
trees peaked around 41--45 GiB. More than one compiler is allowed only when
the live budget admits it; another FPGA tool merely existing is not a block.
Board runs use separately bounded 16--32-GiB groups, the same reserve and a
device lock. Interrupted `v1` attempts were never promoted to passing results.

### Revised SSSP Route Evidence

`route-zfs-v2/sssp/results.json` reached `ROUTED_NOT_BOARD_TESTED` on
2026-10-25. The compiler exited zero with no watchdog stop or cgroup memory
events. The new bounded-cache xclbin SHA-256 is
`ed674b033c738506bd8ac32da9ab2b51e3e70e8925113aed048f50eb35dbf11e`.
Its metadata records DATA 150 MHz and HBM 450 MHz; neither was reduced.

The final `hw_bb_locked_timing_summary_routed.rpt` under
`work/link/vivado/vpl/prj/prj.runs/impl_1/` reports setup WNS +0.002 ns,
TNS zero and no setup-failing endpoints; hold WNS is +0.009 ns, THS zero
and no hold-failing endpoints. All user-specified timing constraints are met.
Earlier negative slack in intermediate route messages is not the final
timing result. This gate proves routing, not FPGA correctness or speedup.
The matrix started the SSSP AU task for this exact binary after separate
board and finite-memory admission. No paired sample had passed at this checkpoint.

### Spine Wrapper Failure And Artifact Audit

The sparse ResPR compiler returned zero, generated its xclbin and printed the
terminal `BUILD_PASS` marker. Only afterward, generic `runtime.execute`
misclassified `compile-route` as a C++ dependency-producing command and tried
to open the nonexistent `respr.d`. The original `FAILED_RETAINED` report,
manifest and logs are unchanged. This is a wrapper failure, not a compiler
failure or a passed board test; no dummy dependency file was created.

`spine_recovery.py` checks the exact successful command, absence of watchdog
or OOM failure, all original input hashes, clean source commit, sparse-apply
selector, build provenance, terminal success marker, actual xclbin kernels
and clock metadata. It writes a fresh audit that includes original evidence
hashes. Four focused regression tests pass; together with the cache and
export tests, the suite passes 18 tests. The real audit used a 2-GiB/zero-swap
group and peaked at 125.5 MiB.

The new xclbin SHA-256 is
`b6cb210342029a77233740e7aeffea354d19757ebb68431b0fc993bef59bd15b`.
Its unscaled routed summary has setup WNS -0.007 ns, TNS -0.014 ns and three
failing endpoints; hold WNS is +0.009 ns with no failing hold endpoints.
Vivado automatically scaled `hbm_aclk` from 450 to 448.6 MHz; xclbin metadata
records 448 MHz. DATA remains 150 MHz. This is not timing closure at the
requested HBM clock. The board matrix retains actual clocks and requires
correctness independently. No timing constraints or live G+R runner pins
were modified to obtain this audit. The dependency-phase bug itself remains
in the frozen original runner and must be corrected before reusing that
runner for another Spine build, after live builds release their source pins.

The independent AU board smoke passed using this exact binary, the frozen
515281-vertex graph, eight insertions and the resident wall-time boundary.
The checked log records 52.6317 ms and zero propagation iterations: correction
and final-state validation completed, but this batch did not exercise a
nonzero residual propagation. This single run establishes neither a speedup
nor repeated timing or all-workload correctness. Actual DATA/HBM metadata
remain 150/448 MHz. The 16-GiB/zero-swap group had no OOM events; the sampled
host-tree RSS peak was 2472880 KiB. Three smoke-log rejection tests bring the
cache/export/recovery/smoke suite to 21 passing tests.

```bash
python3 -m validation.cache_extent.spine_recovery \
  --source <retained-failed-wrapper-directory> \
  --output <fresh-audit-directory>

# In a 16-GiB max / 14-GiB high / zero-swap systemd group, with group OOM kill:
python3 -m validation.cache_extent.spine_smoke \
  --plan <current-frozen-matrix-plan> --output <fresh-smoke-directory>
```

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
python3 /home/chuxiao/spine-cycle-sim/spine-cycle-sim-production-board/spine_cycle_sim/experiments/host_memory.py
systemctl --user status gr-cache-extent-source-zfs-20261025-v3.service \
  spine-cache-study-respr-zfs-20261025-v1.service \
  gr-cache-extent-sssp-zfs-20261025-v2.service \
  gr-cache-extent-cc-zfs-20261025-v2.service \
  gr-cache-extent-respr-zfs-20261025-v2.service \
  gr-cache-extent-matrix-zfs-20261025-v3.service
```

The simulator repository's companion guide is
`docs/experiments/comparisons/grasu_regraph_stage_validation/evaluation_impact/cache_extent/README.md`.
It separates source-grounded component predictions from hardware timing.

## Terminal Delivery

After the matrix terminates, create one reviewable folder:

```bash
python3 -m validation.cache_extent.delivery \
  --matrix <terminal-matrix/results.json> --output <fresh-delivery-directory>
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
