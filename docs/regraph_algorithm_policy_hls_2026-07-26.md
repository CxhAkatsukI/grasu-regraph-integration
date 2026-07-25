# ReGraph Algorithm Policy HLS Core

## Scope

This milestone adds a common eight-lane source-map, edge-map/reduce, and apply
arithmetic interface for:

- weighted SSSP;
- Full PageRank with float32 damping and dangling-share input;
- thresholded residual PageRank with float32 rank/residual state.

The implementation is an isolated synthesizable policy core. It proves that
the algorithm arithmetic represented by the cycle simulator has a concrete HLS
implementation and allows per-policy incremental resource/timing comparison.
It is not a complete GraSU + ReGraph xclbin and must not be reported as native
whole-system performance.

## Contracts

The core processes eight independent 32-bit lanes per beat. Full PageRank uses
one 32-bit rank state word and external ping-pong storage. Residual PageRank
uses one 32-bit rank and one 32-bit signed residual word per vertex. PageRank
uses float32 bit patterns, matching the architecture oracle in
`spine-cycle-sim`.

The PMA adapter now has three mutually exclusive output modes:

- legacy unit-weight edge-property encoding;
- full `dst19 + weight12` weighted encoding for SSSP;
- destination-only projection for PageRank.

Destination-only projection happens in the hardware adapter. The PMA remains
full-word weighted for update matching, and no host conversion array is added.

## Reproduction

Run functional tests:

```bash
cd /home/chuxiao/grasu-regraph-integration
scripts/check_pma_to_regraph_adapter.sh
scripts/check_regraph_algorithm_policy.sh
python3 tests/test_prepare_algorithm_policy_hls_build.py
```

Generate all three 200 MHz U55C compile jobs:

```bash
cd /home/chuxiao/grasu-regraph-integration
scripts/prepare_algorithm_policy_hls_build.sh \
  --target hw \
  --algorithm all \
  --kernel-frequency 200 \
  --build-root /data/tmp/chuxiao/regraph_algorithm_policy_hw_20260726
```

Then run the generated `compile_commands.sh`. The resulting HLS reports and XOs
are incremental policy-core PPA evidence. A Full/Residual PageRank claim becomes
native only after the policy, dangling reduction, degree maintenance, state
storage, host iteration/frontier control, and PMA adapter profile are integrated
and validated in one xclbin.

## Current Evidence

Vitis 2024.1 software-emulation compilation passed for all three profiles at a
requested 200 MHz HLS clock. The generated XOs were:

| Profile | Bytes | SHA-256 |
|---|---:|---|
| weighted SSSP | 3,850 | `d7e872e73a9837c2d5474805bce54aac280feec8282888eb2b4e009a661977dc` |
| Full PageRank | 3,849 | `a0d10a229b745f84353b6e85c21e53bdec9659bcd99316070acadf092e6a58ea` |
| thresholded residual PageRank | 3,849 | `ccdfe4109267b9e982f7e2522af17de21501a9b4655703de3a3736db8655920c` |

These small software-emulation XOs do not contain synthesized PPA data. The
generated `hw` jobs are the required next evidence tier.
