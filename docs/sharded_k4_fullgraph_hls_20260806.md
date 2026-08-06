# Destination-Sharded K4 Full-Graph HLS Baseline

## Evidence boundary

This branch replaces the earlier `K4-shared` baseline that rescanned one
global PMA for every destination partition.  The new baseline stores one PMA
shard per destination partition.  Every edge in a shard carries a local
19-bit destination, while the ReGraph frontend restores the global
destination using the shard base.  Across one propagation round, the PMA
frontends therefore scan each physical edge image once in total rather than
once per destination partition.

The implementation has four work-conserving
`PMA adapter -> little gather` frontends and one shared
`frontend mux -> merger -> apply -> HBM wrapper` downstream.  It is not four
complete ReGraph replicas.  Destination shards are assigned to frontend
`partition_id % 4`; a frontend can start its next shard after its previous
shard completes, and finite AXIS FIFOs backpressure frontends waiting for the
shared downstream.

Evidence is promoted in four separate steps:

1. source and host correctness, including a six-partition `dst19` boundary;
2. successful HLS compilation of every kernel;
3. routed xclbin with archived timing, utilization, connectivity, and hashes;
4. real-U55C correctness followed by matched resident-state comparison.

Completion of an earlier step is never treated as evidence for a later one.

## Fixed hardware profile

| Item | Frozen value |
| --- | --- |
| FPGA | Alveo U55C |
| Kernel clock target | 150 MHz |
| PMA destination ABI | local `dst19`, partition size 65,536 |
| Maximum partitions | 255 (control ABI) |
| GraSU lanes | four update/search lanes |
| ReGraph frontends | four PMA adapter/source-gather frontends |
| ReGraph downstream | one shared mux/merger/apply/HBM path |
| PMA HBM placement | pseudo-channels 0--22, lane-aware ranges |
| Source mirrors | HBM 23 and 24 |
| PageRank rank/residual/degree | HBM 25/26/27 |
| SSSP/CC state | HBM 30 |
| Handoff | direct AXIS stream; no converted edge array |

The lane ranges are `[0,6)`, `[6,12)`, `[12,18)`, and `[18,23)`.  A
largest-first capacity planner places every PMA/update/row/binary region and
rejects a workload before programming the board if any 512 MiB pseudo-channel
would overflow.

## Frozen full-graph matrix

All rows use insertion batch 8.  CC uses reciprocal edges, so its physical
update count is 16.  Residual PageRank uses the direct per-vertex
`epsilon=1e-6` policy.  SSSP sources are frozen median-degree cohort members
from the materialization manifest, not selected after observing performance.

| Graph | Vertices | SSSP edges/source | CC edges | ResPR edges |
| --- | ---: | ---: | ---: | ---: |
| AU | 515,281 | 390,847 / 11 | 679,246 | 826,848 |
| SU | 567,316 | 616,118 / 23 | 1,061,248 | 1,075,035 |
| WK | 1,140,149 | 1,142,352 / 0 | 2,032,558 | 2,190,639 |
| SO | 6,024,271 | 23,724,166 / 32 | 41,008,044 | 28,299,669 |
| PK | 1,632,803 | 44,603,928 / 64 | 44,603,928 | 44,603,928 |
| LJ | 4,847,571 | 85,702,474 / 71 | 85,702,474 | 85,703,436 |
| LJ08 | 5,363,260 | 99,028,542 / 26 | 99,028,542 | 99,028,616 |
| R19 | 524,288 | 15,483,485 / 113 | 29,732,038 | 15,672,181 |

The generated manifest is rooted at:

```text
/data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/manifest.json
```

It contains 24 SHA-256-identified rows and must report `status=pass` before a
matrix can be generated.  A compact, reviewable copy of those identities is
tracked at
`docs/evidence/sharded_k4_fullgraph_20260806/workloads.tsv`.

## Reproduction

Source and host checks:

```bash
cd /home/chuxiao/grasu-regraph-integration
git switch codex/sharded-k4-fullgraph-hls
python3 -m unittest discover -s tests -v
./scripts/check_sharded_k4_native_host.sh
```

Recreate or verify the frozen workloads without retaining all input edges in
memory:

```bash
python3 scripts/prepare_fullgraph_fpga_workloads.py \
  --out-dir /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806
```

The largest SSSP input can be capacity-checked under a hard 24 GiB host-memory
ceiling.  This verifies the 82-shard layout and the 23-channel placement before
an xclbin or board is involved:

```bash
ulimit -v 25165824
/data/tmp/chuxiao/sharded_k4_hosts_5d501d9/weighted_sssp/\
sharded_k4_sssp_native_host \
  --prepare-only \
  /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/\
lj08_weighted_sssp_insert_u8.graph \
  /tmp/lj08_sssp.txt 26 256
```

The accepted output is archived at
`docs/evidence/sharded_k4_fullgraph_20260806/lj08_sssp_preflight.txt`.

Run the routed SSSP artifact on the AU full-graph row.  This row has eight
destination shards, so it exercises the full-graph path beyond the legacy
four-partition limit:

```bash
./scripts/run_pma_native_hw.sh \
  --algorithm weighted_sssp \
  --host /data/tmp/chuxiao/sharded_k4_hosts_5d501d9/weighted_sssp/\
sharded_k4_sssp_native_host \
  --xclbin /data/tmp/chuxiao/\
grasu_regraph_sharded_k4_sssp_hw_b8d2ba3_20260806/build/\
grasu_regraph_weighted_pma_native_sharded_k4.hw.xclbin \
  --graph /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/\
au_weighted_sssp_insert_u8.graph \
  --out-dir /data/tmp/chuxiao/sharded_k4_fpga_smoke_20260806/au_sssp \
  --device-index 0 --source 11 --max-supersteps 256 --timeout 1800
```

The accepted log, run environment, summary, and hashes are archived at
`docs/evidence/sharded_k4_fullgraph_20260806/sssp_u55c_au`.  The per-vertex
result file is omitted from Git; its SHA-256 remains in `evidence.sha256`.

The routed CC artifact is exercised with the same protocol on AU:

```bash
./scripts/run_pma_native_hw.sh \
  --algorithm connected_components \
  --host /data/tmp/chuxiao/sharded_k4_hosts_5d501d9/connected_components/\
sharded_k4_cc_native_host \
  --xclbin /data/tmp/chuxiao/\
grasu_regraph_sharded_k4_cc_hw_d886f42_20260806/build/\
grasu_regraph_connected_components_pma_native_sharded_k4.hw.xclbin \
  --graph /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/\
au_connected_components_insert_u8.graph \
  --out-dir /data/tmp/chuxiao/sharded_k4_fpga_smoke_20260807/au_cc \
  --device-index 0 --source 0 --max-supersteps 256 --timeout 1800
```

Its compact evidence is archived at
`docs/evidence/sharded_k4_fullgraph_20260806/cc_u55c_au`.

The three hardware build roots are:

```text
/data/tmp/chuxiao/grasu_regraph_sharded_k4_sssp_hw_b8d2ba3_20260806
/data/tmp/chuxiao/grasu_regraph_sharded_k4_cc_hw_d886f42_20260806
/data/tmp/chuxiao/grasu_regraph_sharded_k4_respr_hw_d886f42_20260806
```

Each root contains `compile_commands.sh`, `link_command.sh`, `manifest.env`,
and generated reports.  Vitis links are run one at a time because Vivado
implementation is the dominant host-memory consumer.

After all three routed xclbins exist, bind the fail-closed matrix:

```bash
python3 scripts/prepare_fullgraph_fpga_matrix.py \
  --workload-manifest \
    /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/manifest.json \
  --host-root /data/tmp/chuxiao/sharded_k4_hosts_5d501d9 \
  --sssp-xclbin <SSSP_XCLBIN> \
  --cc-xclbin <CC_XCLBIN> \
  --respr-xclbin <RESPR_XCLBIN> \
  --output /data/tmp/chuxiao/fullgraph_fpga_matrix_20260806.tsv
```

During incremental bring-up, `--algorithm` may be repeated to bind an explicit
algorithm subset.  Only the selected algorithms' xclbins are required; omitting
the option retains the strict complete-matrix default.  For example, the routed
CC artifact can be exercised on all eight graphs while ResPR is still routing:

```bash
python3 scripts/prepare_fullgraph_fpga_matrix.py \
  --workload-manifest \
    /data/tmp/chuxiao/fullgraph_fpga_workloads_20260806/manifest.json \
  --host-root /data/tmp/chuxiao/sharded_k4_hosts_5d501d9 \
  --algorithm connected_components \
  --cc-xclbin /data/tmp/chuxiao/\
grasu_regraph_sharded_k4_cc_hw_d886f42_20260806/build/\
grasu_regraph_connected_components_pma_native_sharded_k4.hw.xclbin \
  --output /data/tmp/chuxiao/fullgraph_cc_fpga_matrix_20260807.tsv
```

Run the correctness-gated comparison with automatic memory-safe scheduling:

```bash
./scripts/run_matched_fpga_matrix.sh \
  --matrix /data/tmp/chuxiao/fullgraph_fpga_matrix_20260806.tsv \
  --out-dir /data/tmp/chuxiao/fullgraph_fpga_runs_20260806 \
  --execution-mode auto \
  --gr-memory-gib 64 \
  --spine-memory-gib 64 \
  --memory-reserve-gib 16
```

`auto` uses both U55C boards concurrently only when `MemAvailable` exceeds
both process ceilings plus the reserve.  Otherwise it runs the two
architectures serially.  Each process also inherits a hard virtual-memory
ceiling.  During execution, a one-second guard continues to sample
`MemAvailable`; if another build or experiment consumes the reserve, it
terminates the complete isolated process group and records exit 125 instead of
risking a host OOM.  An allocation failure, guard trip, timeout, oracle
mismatch, missing timing field, or missing artifact rejects the row.

## Current status

As of 2026-08-06, 22 unit tests, all four native hosts, the six-partition ABI
check, all 24 workload materializations, and all three algorithm-specific XO
sets pass.  LJ08 SSSP (5.36M vertices, 99.03M initial edges) also passes host
preflight under a 24 GiB hard ceiling: 82 destination shards map to 23 HBM
pseudo-channels with 6.56 GB allocated in total and 295 MB in the fullest
channel.

The SSSP xclbin routes successfully at 150 MHz with zero failed nets and zero
timing violations.  Routed user logic uses 151,950 LUTs, 175,539 registers,
429 BRAMs, 256 URAMs, and no DSPs; final WNS/WHS are +0.003/+0.009 ns.  Its
xclbin SHA-256 and copied implementation reports are archived under
`docs/evidence/sharded_k4_fullgraph_20260806/sssp`.

The same artifact passes the real-U55C weighted-SSSP matrix on all eight
frozen graphs.  Both architectures start from the old graph's converged
resident state, apply the same insertion batch, execute until the independent
oracle converges, and include current host orchestration in the reported
setup-inclusive window.  Every row below is one correctness-admitted execution;
the values are not yet multi-run medians.

| Graph | G+R setup-inclusive (ms) | Spine setup-inclusive (ms) | G+R / Spine |
| --- | ---: | ---: | ---: |
| AU | 2,065.321 | 127.418 | 16.21x |
| SU | 3,399.388 | 116.905 | 29.08x |
| WK | 5,676.505 | 106.656 | 53.22x |
| SO | 137,677.538 | 137.556 | 1,000.88x |
| PK | 23,006.391 | 186.083 | 123.64x |
| LJ | 274,702.199 | 185.380 | 1,481.83x |
| LJ08 | 223,831.252 | 142.916 | 1,566.17x |
| R19 | 2,202.999 | 116.802 | 18.86x |

The complete summary, launch status, matrix, and hashes of the untracked raw
logs/results are archived under
`docs/evidence/sharded_k4_fullgraph_20260806/sssp_fullgraph_u55c`.  These
results validate the direction and magnitude variation of the SSSP advantage
on routed hardware.  Statistical claims still require repeated runs and must
not substitute kernel-only ratios for the setup-inclusive ratios above.

The matched Spine host at commit `3678ad4` now loads resident baselines through
the same hot/cold family classifier and multi-level serializer consumed by the
routed kernel.  A real-U55C PK SSSP run passes with 1,632,803 vertices,
44,603,928 initial edges, 16 cold destination partitions, 248,899 hot
vertices, and 24,321,670 hot edges.  Maintenance and both propagation rounds
pass with zero overflow or task error; setup-inclusive dynamic latency is
185.608 ms.  This closes the previous host-only cold-family capacity rejection
for PK.  Compact evidence is archived under
`docs/evidence/sharded_k4_fullgraph_20260806/spine_sssp_u55c_pk`.

The CC xclbin routes with 151,453 LUTs, 170,219 registers, 429 BRAMs, 256
URAMs, and no DSPs.  The user kernel clock closes at 150 MHz with +0.340 ns
WNS.  A fixed platform HBM path misses 450 MHz by 0.060 ns, so Vitis selects
438.2 MHz for `hbm_aclk`; this platform-clock adjustment is recorded rather
than represented as user-kernel timing closure.  The xclbin passes a real-U55C
AU gate with 515,281 vertices, 679,246 resident edges, eight destination
shards, 16 physical insertions, and zero mismatches.  The run starts from the
old graph's converged CC state, uses four frontends and one shared downstream,
and has no conversion stage.

The corrected ResPR PMA DDR kernel has `II=1` and estimated `205.47 MHz`; the
prior shared-bundle result (`II=140`) is rejected.  Its routed artifact and
board-run correctness gate remain pending.  The CC/ResPR eight-graph matched
matrices remain pending until the ResPR board gate passes.
