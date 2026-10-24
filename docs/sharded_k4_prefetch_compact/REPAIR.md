# Schedule And Integration Repair

This is the active task log for the default-off simulator-aligned HLS profile.
The [contract and source map](README.md) remain authoritative. Earlier raw
evidence is immutable; every synthesis attempt gets a fresh output directory.
The paper and frozen simulator predictions are not being changed.

## Acceptance Gates

| Gate | Current state |
| --- | --- |
| Functional equivalence | Three-format adapter (396 cases) and exhaustive compactor tests pass after packed-directory and split-bank changes; connected Gather and integer Apply need fresh reruns |
| Adapter scheduling | Prefix retry exports XO in 75.66 seconds, estimates 78.31 MHz; directory fill II=4 and bank readers II=36 remain; split-bank retry pending |
| Apply scheduling | Earlier integer Apply XO estimates 144.82 MHz vs requested 150 MHz |
| Finite channels and stalls | Unbounded vendor C streams are insufficient; bounded protocol tests and RTL evidence required |
| Physical integration | Direct-ingress projection exceeds 32; choose and account for actual sharing rather than raising the audit limit |
| Complete hardware | Not newly linked, routed or board tested; no performance result follows from component export |

Do not promote an unmet gate to a pass. HLS frequency estimates are not
post-route timing. Full-system acceptance requires the actual interfaces,
clock, state semantics, completion boundary and correctness-checked output.

## Current Iteration

The four-level prefix retry (`7876b8a`) passes all adapter/compactor checks and
exports the XO. Estimated clock improves from 62.91 to 78.31 MHz, but still
fails the 150-MHz gate. HLS reassociates prefix arithmetic and reports a
12.770-ns compactor path. The next attempt disables expression rebalancing
in that function rather than declaring this solved.

The bank reader now separates requests and responses into DATAFLOW processes,
as supported by [Vitis HLS 2024.1 manual burst](https://docs.amd.com/r/2024.1-English/ug1399-vitis-hls/Using-Manual-Burst).
Explicit parent and returned-or-reserved line limits remain 16 and 512.
Parent credit returns after response consumption; line credit returns only
after the join consumes that line. Finite internal descriptor/credit FIFOs
are depth 16. C-only locking protects the vendor model's shared pointer map.

Directory tiles now hold 128 packed 512-bit words rather than 1024 individual
64-bit rows. This retains two 8-KiB tiles and row contents, while replacing
eight writes per response with one. The join extracts at most two packed
words for eight consecutive rows. The ignored array partition is removed.
Three-format independent adapter and exhaustive compactor tests pass in
`/data/chuxiao/checks/adapter-split-bank-20261024/`; synthesis is pending.

Raw prefix evidence is retained in
`/data/chuxiao/builds/gr-prefetch-compact-trif-prefix-valid-20261024/`.
The earlier `...-prefix-20261024/` attempt failed before Vitis invocation
because dependency-root environment variables were absent. Neither attempt
is a route or board test. No OOM was recorded.

Subsequent work targets join/segment registration, compactor feedback timing,
integer Apply timing and explicit physical sharing.
Any changed timing or arbitration contract must be documented and propagated
to a separate simulator profile before claiming matching behavior.

## Prediction Boundary

Failure to realize a simulator topology in this FPGA does not by itself make
the simulator a best-case bound. Such a claim needs explicit optimistic
assumptions and a justified lower bound on G+R latency, plus a same-workload,
same-state, same-convergence comparison to Spine. No tenfold advantage is
assumed by this repair task.
