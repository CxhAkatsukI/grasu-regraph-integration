# Resident FullPR Convergence

## Scope

The opt-in `--resident-fullpr` suffix selects a continuous resident-update test
in `tools/sharded_k4_pagerank_native_host.cpp`. It changes host initialization,
termination and validation only. It does not change the HLS kernels, PMA ABI,
sharding, stream connections or bitstream. The default FullPR path remains the
historical uniform-initialized, fixed-three-sweep diagnostic and now identifies
its actual initial state explicitly. Those diagnostics are not resident-update
speedups.

The new mode uses 128 old-graph CPU sweeps and requires the resulting rank to
have global L1 fixed-point residual at most `1e-6`. Both systems must use the same
old graph, batch, directed vertex domain, damping `0.85`, dangling redistribution
and global L1 termination rule. The independent new-graph CPU reference starts
from that old rank and must converge within 256 sweeps. These CPU preparations
are outside the timed window. Edge weights do not enter PageRank.

## Measurement

Initial graph, old rank, old degree and batch are preloaded. The existing wall
timer starts immediately before the GraSU update launches. Updated degrees,
source preparation, adapter/gather/apply execution, round-status transfers,
host decisions/relaunch and final rank/degree readback are inside the continuous
window. It is not full CPU setup latency. Neither CPU validation nor result-file
writing is inside the window. Event sums are diagnostic, not a substitute for
the continuous wall time.

The apply kernel already reports global L1 rank delta, so no new counter or
bitstream is needed for termination. The host stops at delta `<= 1e-6`, at most
256 sweeps. Nonfinite statistics, failure to converge, final degree mismatch,
per-vertex rank error above `2e-5`, global reference L1 error above `2e-4`, or
probability-mass error above `1e-3` reject the run. The fixed Spine counterpart
uses the same thresholds but computes L1 from its actual full-state readback.
G+R's in-kernel floating reduction and Spine's host double reduction can differ
near the threshold. Report actual iteration counts; do not force a matching
number of rounds or hide either readback policy.

## Reproduction And Gates

```bash
bash scripts/build_weighted_pma_native_host.sh --pipeline-mode sharded-k4 \
  --algorithm full_pagerank --row-line-read --out-dir /data/chuxiao/fresh-fullpr-host

/data/chuxiao/fresh-fullpr-host/sharded_k4_full_pagerank_native_host \
  --prepare-only <graph> <unused-result> --resident-fullpr

# Only after a fixed artifact passes routing/ABI/clock admission and a card lease:
/data/chuxiao/fresh-fullpr-host/sharded_k4_full_pagerank_native_host \
  <admitted-xclbin> <graph> <result> --resident-fullpr

OUT_DIR=/data/chuxiao/fresh-four-host-gate \
  bash scripts/check_sharded_k4_native_host.sh --row-line-read
```

The four-host gate builds all algorithms, checks legacy six-partition CPU
preparations and the new FullPR preparation, exercises a separate pure C++
reference test, and rejects incompatible flags before opening a device. Its
claim is offboard host/reference correctness only, not FPGA performance or
equivalence to published ReGraph. New board smokes, repeated matched-input
timings and evidence-reader admission remain separate gates.
