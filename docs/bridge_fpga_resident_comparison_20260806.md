# Resident-State Bridge FPGA Comparison (2026-08-06)

## Result

This experiment compares routed Spine and conversion-free GraSU+ReGraph
(G+R) hardware on compacted AskUbuntu real-topology slices. Both systems start
from the converged state of the same old graph, apply the same insertion batch,
and run until their algorithm-specific correctness oracle accepts the result.

Each row is the median of six admitted executions: three with G+R on U55C
device 0 and Spine on device 1, and three with the device assignment swapped.

| Algorithm | Initial graph | Vertices | Directed update records | G+R device window (ms) | Spine device window (ms) | Device-window speedup | G+R setup-inclusive (ms) | Spine setup-inclusive (ms) | Setup-inclusive speedup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Weighted SSSP | 540,000 directed edges | 157,107 | 8 | 500.669 | 8.330 | 60.09x | 501.355 | 128.087 | 3.92x |
| Weighted SSSP | 903,774 reciprocal edges | 156,289 | 16 | 1,522.844 | 6.412 | 237.44x | 1,523.531 | 244.194 | 6.23x |
| Connected components | 540,000 reciprocal edges | 94,931 | 16 | 932.072 | 4.836 | 192.93x | 932.605 | 267.980 | 3.48x |
| Connected components | 903,774 reciprocal edges | 156,289 | 16 | 2,538.354 | 6.490 | 391.07x | 2,538.949 | 308.431 | 8.23x |
| Residual PageRank | 540,000 reciprocal edges | 94,931 | 16 | 585.873 | 195.306 | 3.00x | 586.395 | 325.010 | 1.81x |
| Residual PageRank | 903,774 reciprocal edges | 156,289 | 16 | 959.033 | 160.435 | 5.98x | 959.752 | 252.706 | 3.80x |

All 36 architecture executions passed their own independent oracle and the
matched comparison admission gate. Weighted SSSP is checked against Dijkstra,
CC against CPU component membership, and residual PageRank against the
floating-point residual oracle at a direct per-vertex threshold of `1e-6`.

## Interpretation

The principal result is the **device-window speedup**. G+R's value is the
OpenCL event envelope from the PMA update through the final ReGraph kernel;
Spine's value includes maintenance input/output migration plus the complete
iterative algorithm device window. It is conservative for Spine because its
window includes those transfers while G+R's event envelope does not include
host convergence readback.

The **setup-inclusive speedup** additionally exposes the current host launch,
buffer migration, convergence readback, and final result migration performed
after resident state construction. It is the conservative current-system
number. Static graph construction, old-state convergence, xclbin programming,
and initial resident-state upload are excluded on both sides.

The much larger SSSP and CC device-window differences are structurally
consistent with the hardware traces. The current G+R design has four GraSU PMA
update engines but one shared ReGraph pipeline. For every superstep it processes
the complete PMA slot stream once for each destination partition. Spine starts
from its device-maintenance dirty-source frontier and propagates only the
realized differential work. Residual PageRank narrows the difference because
Spine's residual correction and propagation computation dominates its dynamic
window.

The two sizes are different topology slices, not a controlled size sweep. Their
ratio must not be interpreted as asymptotic scaling. The reciprocal workloads
contain eight logical undirected insertions represented as 16 directed update
records. External vertex IDs are compacted; this preserves topology but not the
original physical-ID address locality.

## Semantic alignment

- SSSP and CC preload the converged old-graph state on both architectures.
- Spine consumes the dirty source list emitted by device maintenance on the
  first dynamic iteration. G+R activates the corresponding update sources;
  subsequent active frontiers are device generated.
- SSSP final distances must exactly match Dijkstra. Asynchronous intermediate
  states are checked for monotonicity and for never undershooting the final
  shortest distance.
- CC labels are compared by component membership because G+R internally
  reorders vertices.
- Residual PageRank starts from the same old-graph rank and degree state. G+R
  performs source preparation and correction on device. The routed Spine image
  does not contain that correction kernel, so its equivalent host computation
  and full state write are explicitly included in
  `host_dynamic_preparation_ms` and the setup-inclusive result.
- SSSP/CC resident incremental execution is admitted only for pure insertions
  (and non-increasing weights on G+R SSSP). Unsupported deletion/increase cases
  fall back to cold execution instead of silently using an invalid monotonic
  update path.

## Hardware identity

- Platform: two `xilinx_u55c_gen3x16_xdma_3_202210_1` cards.
- Kernel target frequency: 150 MHz.
- Spine host source: `5e915ccc3984d7af31546ee6ee933461edd27844`.
- G+R host source: `c66dc5a293c95f6a784123627dc607880912d9a4`, clean at run time.
- G+R routed HLS source: `bb2bd3bf41ae14117fc38979c7fd188e907b85b2`.
- Every run records host, xclbin, workload, and run-log SHA-256 values.

The routed xclbins predate the resident-state host changes. This is valid here:
resident baseline values and initial active sources are existing host-visible
kernel inputs; no kernel interface or datapath changed.

## Reproduction

Prepare the compacted real-topology workloads and host binaries:

```bash
cd /home/chuxiao/grasu-regraph-integration
scripts/prepare_bridge_fpga_workloads.sh
scripts/prepare_bridge_resident_hosts.sh
```

Run the original and swapped device assignments three times each:

```bash
ROOT=/data/tmp/chuxiao/matched_fpga_bridge_resident_final_20260806
for repeat in 1 2 3; do
  scripts/run_matched_fpga_matrix.sh \
    --matrix configs/bridge_fpga_resident_matrix_20260806.tsv \
    --out-dir "$ROOT/repeat${repeat}"
  scripts/run_matched_fpga_matrix.sh \
    --matrix configs/bridge_fpga_resident_matrix_20260806.tsv \
    --out-dir "$ROOT/swap_repeat${repeat}" \
    --gr-device 1 --spine-device 0
done
```

Aggregate only correctness-admitted rows:

```bash
python3 scripts/aggregate_matched_fpga_repeats.py \
  --summary "$ROOT/repeat1/summary.tsv" \
  --summary "$ROOT/repeat2/summary.tsv" \
  --summary "$ROOT/repeat3/summary.tsv" \
  --summary "$ROOT/swap_repeat1/summary.tsv" \
  --summary "$ROOT/swap_repeat2/summary.tsv" \
  --summary "$ROOT/swap_repeat3/summary.tsv" \
  --require-samples 6 --output "$ROOT/aggregate.tsv"
```

Tracked compact evidence is in
`docs/evidence/bridge_fpga_resident_20260806/`. Complete per-run logs remain at
`/data/tmp/chuxiao/matched_fpga_bridge_resident_final_20260806/`.

## Claim boundary

This is strong routed-FPGA evidence for approximately one-million-edge,
compacted real-topology **insertion** workloads. It is not yet evidence for the
paper's full graph set, original external-ID locality, deletion propagation,
weight increases, or a device-side Spine residual-correction kernel. Full
PageRank is not part of this bridge result.
