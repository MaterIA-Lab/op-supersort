---
title: Continuity smoke test
date: 2026-11-12 14:57
verdict: setup
summary: The prior local runner still compiles and runs on Windows with GCC 16.1 and sorts 1,000 uint32 keys correctly. Not an evaluation of the goal.
model: not captured
cost: not captured
---

# Continuity smoke test — 2026-11-12

Checked that the prior local runner compiles and executes in the new preparation workspace on Windows with GCC 16.1. The run used 1,000 `uint32` elements, `uniform` and `few`, seeds 271 and 811, five algorithms and three measured repetitions. All outputs were checked by the runner against `std::sort`; 60 timed samples were recorded.

This is a technical smoke test, not an evaluation of the project goal. It uses a small, incomplete matrix and only one thread, and three repetitions of about 2 µs cannot resolve small differences. The published metadata replaces the local user path with `<local-user>`. Model identifier, token count and cost for this setup session were not captured; do not infer them.

The runner and source snapshots used (`bench.cpp`, bridges, `run.py` and `include/`) were removed from `main` together with the prior research archive. They remain at [commit 195f578](https://github.com/MaterIA-Lab/op-supersort/tree/195f5781c0a1ddbd0fba53db0e47b7b3a18c3555/runs/2026-11-12-smoke). `metadata.json`, `raw.csv` and `summary.md` are kept here.
