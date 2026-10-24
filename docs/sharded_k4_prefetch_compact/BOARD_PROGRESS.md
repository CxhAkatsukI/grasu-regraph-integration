# Actual-Frequency Board Campaign

## Scope

The October 24 board campaign accepts the packaged HBM frequency rather than
requiring the requested 450 MHz. This is an explicit measurement-policy change,
not a successful 450-MHz signoff. No simulator timing coefficient is adjusted.
The fixed-clock failures and earlier build artifacts remain intact.

The fresh SSSP xclbin is:

`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/route-slr-v2/sssp/grasu_regraph_weighted_pma_native_sharded_k4.hw.xclbin`

Its SHA-256 is
`babe48e3bf3cc87b6f06b3e3ccf696dadd4b9f8bfcf0c1629a67a115e4ba39be`.
The build metadata reports 150-MHz compute and 440.1-MHz HBM; the xclbin records
integer 440-MHz HBM. The diagnostic clock checker only validates metadata,
not measured board frequency or physical timing closure.

Four real FPGA correctness smokes passed: tiny update, tiny algorithm,
six-partition update and six-partition algorithm. These smokes do not establish
the full eight-graph performance matrix.

## Active Work

All paths below are relative to
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/`.

| Work | Service | Evidence directory |
| --- | --- | --- |
| G+R CC link | `gr-blocking-route-slr-v2-cc` | `route-slr-v2/cc/` |
| G+R ResPR link | `gr-route-live-v1-respr` | `route-live-v1/respr/` |
| Spine sparse ResPR build | `spine-live-v1-respr` | `spine-live-v1/respr/` |
| Eight-graph paired board tests | `gr-actual-frequency-matrix-v2-{sssp,cc,respr}` | `actual-frequency-matrix-v2/{sssp,cc,respr}/` |

CC and ResPR measurements wait for their required binaries, then use the same
exclusive device lock as SSSP. They do not wait for a fixed-450-MHz gate. Read
each `execution.json` for current state; a running service is not a finished
result. The separate FullPR route remains lower priority.

The common measurement runner is `actual_frequency_campaign.py`, with
`board_runtime.py` owning service-cgroup memory monitoring and pidfd cleanup.
Each board worker has 16-GiB maximum, 14-GiB high watermark, no swap and group
OOM kill, and enforces a 40-GiB live available-memory reserve. Builds use their
own containment. Large available memory allows builds and board tests to run
concurrently; no idle-max reservation sum gates these new board workers.

An earlier attempt in `actual-frequency-matrix-v1/` completed AU/SU/WK with
correctness checks, but its global `ps` process scan timed out on larger graphs.
Those failures are retained as monitor failures, not hardware timing results.
Version 2 reruns the complete matrix without reusing those successful values.

## Measurement And Delivery

Both designs start with the same old graph's converged state. The wall-time
window includes the update batch, convergence, host relaunch/orchestration and
final readback. Initial graph loading and old-state convergence are outside.
One warmup pair is excluded; three measured pairs alternate execution order.
Only correctness-admitted pairs enter the ratio of median wall times.
Missing/failed entries remain explicit, never replaced with old measurements.

Spine integer bitstreams are identified separately in the manifests, including
the limitations of historical build provenance. ResPR requires the fresh sparse
Apply build. Different packaged HBM clocks remain visible; wall times are not
silently frequency-normalized.

The simulator repository owns the new Figure 7 handoff at
`docs/evaluation_refresh_20261024/`, including Python plotting source, measured
CSV, report/manifest snapshots, preview, and an explicit partial/final status.
The paper and previous frozen handoffs are not modified.
