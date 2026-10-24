# Schedule And Integration Repair

This is the active task log for the default-off simulator-aligned HLS profile.
The [contract and source map](README.md) remain authoritative. Earlier raw
evidence is immutable; every synthesis attempt gets a fresh output directory.
The paper and frozen simulator predictions are not being changed.

## Acceptance Gates

| Gate | Current state |
| --- | --- |
| Functional equivalence | Existing three-format adapter, exhaustive compactor, connected Gather and integer Apply tests pass at `bc3dc06`; rerun after each functional change |
| Adapter scheduling | XO exported, but estimated 62.91 MHz vs requested 150 MHz; directory fill II=4 and bank readers II=36 vs requested 1 |
| Apply scheduling | Earlier integer Apply XO estimates 144.82 MHz vs requested 150 MHz |
| Finite channels and stalls | Unbounded vendor C streams are insufficient; bounded protocol tests and RTL evidence required |
| Physical integration | Direct-ingress projection exceeds 32; choose and account for actual sharing rather than raising the audit limit |
| Complete hardware | Not newly linked, routed or board tested; no performance result follows from component export |

Do not promote an unmet gate to a pass. HLS frequency estimates are not
post-route timing. Full-system acceptance requires the actual interfaces,
clock, state semantics, completion boundary and correctness-checked output.

## Current Iteration

The first repair targets the compactor's reported sixteen-addition serial
prefix chain. A four-level parallel prefix computes the same stable ranks
without changing capacity, filtering, output order or publication credits.
Functional and synthesis results are pending for this edit.

Subsequent work targets bank request/response independence, directory banking,
join/segment registration, integer Apply timing and explicit physical sharing.
Any changed timing or arbitration contract must be documented and propagated
to a separate simulator profile before claiming matching behavior.

## Prediction Boundary

Failure to realize a simulator topology in this FPGA does not by itself make
the simulator a best-case bound. Such a claim needs explicit optimistic
assumptions and a justified lower bound on G+R latency, plus a same-workload,
same-state, same-convergence comparison to Spine. No tenfold advantage is
assumed by this repair task.
