# ReGraph Algorithm Policy `sw_emu` Evidence

- Vitis: 2024.1 build 5074859
- Platform: `xilinx_u55c_gen3x16_xdma_3_202210_1`
- Requested kernel clock: 200 MHz
- Source branch before commit: `codex/map-reduce-algorithm-hls`
- Parent source commit: `a927186446b61163bba04e3e263f370fa0e32d63`
- Build root: `/data/tmp/chuxiao/regraph_algorithm_policy_sw_emu_precommit_a927186_20260726`
- Claim class: `synthesizable_policy_core_not_full_system_native`

All three `v++ --target sw_emu --compile` commands exited with status zero:

| Profile | XO bytes | SHA-256 |
|---|---:|---|
| weighted SSSP | 3,850 | `d7e872e73a9837c2d5474805bce54aac280feec8282888eb2b4e009a661977dc` |
| Full PageRank | 3,849 | `a0d10a229b745f84353b6e85c21e53bdec9659bcd99316070acadf092e6a58ea` |
| thresholded residual PageRank | 3,849 | `ccdfe4109267b9e982f7e2522af17de21501a9b4655703de3a3736db8655920c` |

The build root retains the generated compile commands, complete Vitis logs,
reports, and XOs. This evidence establishes software-emulation compilability;
it does not establish synthesized resource use, routed timing, or whole-system
native behavior.
