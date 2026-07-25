# Weighted PMA-Native `sw_emu` Evidence

This directory proves one narrowly defined claim:

> The complete conversion-free GraSU weighted-PMA to ReGraph weighted-SSSP
> pipeline executes under Vitis `sw_emu` and matches the independent CPU oracle
> for the tracked tiny weighted update workload.

It does not prove real-hardware latency, throughput, energy, resource use,
timing closure, or broad-workload correctness.

The accepted result is in `run.env` and `summary.tsv`; `result.txt` contains all
external-vertex distances. `build_metadata/` records the exact source inputs,
generated compile/link commands, and step logs. The host and xclbin are omitted
for size but are identified by SHA-256 in `run.env`.

Verify the archived files from this directory with:

```bash
sha256sum -c evidence.sha256
```

The eight reported bitsize warnings originate in the inherited GraSU kernels.
They did not cause an oracle mismatch in this run and remain an explicit
synthesis-audit item.
