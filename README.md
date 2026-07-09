# GraSU + ReGraph Integration Workspace

This repository is a lightweight integration workspace for comparing:

```text
GraSU dynamic graph update + ReGraph static graph compute
```

against the Spine end-to-end dynamic SSSP path.

The source projects are referenced from the existing local trees instead of being
vendored here:

```text
repos/GraSU   -> /home/chuxiao/GraSU
repos/ReGraph -> /home/chuxiao/ReGraph
```

## Initial Source State

- GraSU: `/home/chuxiao/GraSU`
  - branch: `codex/explore-grasu-u55c`
  - reference commit at workspace creation: `ce7aaf4`
- ReGraph: `/home/chuxiao/ReGraph`
  - current local tree is not a git repository

## Layout

```text
docs/       Experiment plans and notes
repos/      Relative symlinks to GraSU and ReGraph
scripts/    Reusable environment and check helpers
workloads/  Shared generated graph/update inputs
results/    Local run outputs, ignored by git except .gitkeep
```

## First Goal

Build a fair baseline for:

```text
Spine update + SSSP
vs
GraSU update + ReGraph compute
```

The first fair comparison should use unit-weight graphs so Spine SSSP and
ReGraph BFS-like execution can be interpreted consistently. A stricter weighted
SSSP comparison will require adding an SSSP UDF to ReGraph.

## Quick Check

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_workspace.sh
```

