# Rejected Continuous Directory Candidate

`GRASU_REGRAPH_CONTINUOUS_DIRECTORY=1` selects an experimental single-loop
reader in `kernels/pma_to_regraph_adapter/continuous_directory.hpp`. It requires
the cross-row pipeline and is **off by default**. Do not enable it in routed
production builds: its performance admission failed.

The intended change was to cross cached eight-source directory boundaries
without repeatedly draining the occupied-block reader. It uses the existing
shared AXI master, packet ABI, row format and loaded-segment FIFO. No host sparse
index, extra port or PMA storage transformation is introduced.

Production U55C/150-MHz synthesis with Vitis 2024.1 achieved II=71, not requested
II=1, and estimated 13.845-ns clock period against 6.67 ns. The nested
`read_continuous_sources_loop` schedule records a memory dependency; checking
only the top-level report's empty loop list would miss this. Nine of twelve
full-top AXI RTL cases are slower than the V3 reference. Packet contents and
physical traffic still agree, so a functional PASS is not performance admission.

Functional reproduction, with a fresh output directory:

```bash
bash scripts/check_pma_adapter_cross_row.sh \
  --out-dir /data/chuxiao/experiments/fresh_continuous_directory_functional \
  --continuous-directory
```

Omit the last option to check the unchanged default V3 path. Three edge formats
each pass 254 scenarios/1,482 exact packets in the candidate's C++ check. The
complete production RTL and model control are owned by the simulator repository:

`docs/experiments/comparisons/grasu_regraph_stage_validation/actual_sharded_k4/adapter_optimization/row_line/continuous_directory/README.md`

That package preserves executed source archives, XOs, synthetic AXI traces,
complete model states, compiler identities and the rejection decision. Its
nominal continuous-directory model is explicitly counterfactual: removing a
drain in software does not validate II=1 in this HLS. No candidate route/board
measurement, paper edit or baseline-bitstream replacement was performed.

Next investigate bounded directory tiling/prefetch with an actual realizable
schedule before synchronizing a performance model. This note is not a claim
that the final optimized K4 matches original ReGraph.
