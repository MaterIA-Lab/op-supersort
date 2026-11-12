# Progress

A living summary of what has been tried and what was learned, written for people. The detailed, agent-oriented state is in [notes/agent-brief.md](notes/agent-brief.md). The final summary will go in [SUMMARY.md](SUMMARY.md) when the project closes.

_Last updated: 2026-11-12._

## Where we are

Two ideas have been tested since the goal was reset on 12 November 2026. One is closed. The other gives a first gain that only holds under specific conditions. No relevant finding under the [goal](GOAL.md) has been confirmed yet.

## What works so far

**Merging sorted batches by remapping memory pages (promising).** Merging two already-sorted batches of large records usually means copying every byte into a new output. When long stretches of an input already sit at the right place relative to a page boundary, the program can ask the operating system to show those pages in the output instead of copying them. On synthetic data where two batches overlap only at their edges, this was 1.33–1.36× faster than the best merge into a new output, and 2.67× in one case where three quarters of the output could be reused.

The caveats matter:

- If the caller already has a ready output buffer, an ordinary merge is faster: the new method took 1.4–2.7× as long in that case.
- When batches interleave closely, few pages can be reused and the method is 14–18% slower.
- It was tested only on synthetic data, on Linux under WSL2. How often real data (logs, time series) has this shape is still unknown.

## What does not work

- **Reordering large records in cache-sized tiles.** After sorting the keys, records were written in blocks sized to fit the CPU cache. This was 1.5–1.8× slower overall than simply copying each record to its place. The extra bookkeeping costs more than the better memory access saves. A simple copy that asks the CPU to fetch upcoming records early (software prefetch) was the fastest method every time.
- **Patching the fastest existing sorter for random numbers** (prior research). Eighteen attempts to replace a single phase of vqsort for random 32-bit numbers all fell short. See [prior research](notes/prior-research.md).

## What comes next

- Check how often real sorted batches overlap in a way that lets pages be reused.
- Test other ideas from the [backlog](notes/ideas.md): compressed keys for large arrays, sorting many small arrays together, rank computation and helper threads.

## All experiments

Generated from the run logs by `scripts/build_progress.py`. Newest first.

<!-- RUNS:START -->
6 runs: 1 promising, 1 failed, 2 diagnostic, 2 setup.

| Date | Run | Verdict | Result | What we learned |
|---|---|---|---|---|
| 2026-11-12 17:33 | [Page-remapped merge candidate](runs/2026-11-12-page-remapped-merge-candidate/) | 🟡 promising | 1.326–2.668× on edge-overlap runs (2/4 cases ≥1.3×, 0/4 ≥1.5× on both seeds) | Mapping aligned input pages into the output beat the best fresh-output merge of two sorted runs of 128-byte records by 1.33–1.36×, and by 2.67× when 75% of the output was mapped. It lost to a merge into an already-touched buffer (0.36–0.74×) and regressed on bursty and interleaved runs (0.82–0.86×). Synthetic data only. |
| 2026-11-12 17:21 | [Page-remapped merge pilot](runs/2026-11-12-page-remapped-merge/) | 🔎 diagnostic | 1.52–1.59× estimated for edge overlap; at most 1.08× for bursty runs | Mapping pages instead of copying them pays off from 64 KiB extents upwards (4 KiB extents lose). In a merge only page-aligned slices qualify, which was 37.5% of the output when two runs overlap at the edges and 3–7% for bursty runs. |
| 2026-11-12 16:48 | [Blocked record permutation probe](runs/2026-11-12-blocked-permutation/) | ❌ failed | 0.542–0.648× (0/8 cases ≥1.3×) | Writing records in cache-sized destination tiles after sorting their descriptors by source made the permutation 1.67–2.14× slower than a plain gather. The extra descriptor sort costs more than the locality saves. Gather with software prefetch won every repetition. |
| 2026-11-12 16:06 | [Record permutation headroom pilot](runs/2026-11-12-record-permutation/) | 🔎 diagnostic | 1.29–1.40× estimated headroom; 5/8 cases ≥1.3× on both seeds | Gathering the payload takes 51–68% of an indirect sort of 64- and 128-byte records, so a permutation as cheap as a sequential copy would give about 1.3–1.4×. Enough room to try a candidate, with little margin. |
| 2026-11-12 15:37 | [Viability review and repository reset](runs/2026-11-12-repo-reset/) | ⚙️ setup | — | Judged the original goal (25% faster in 90% of a large benchmark matrix) very unlikely to be reached, replaced it with an open search for new mechanisms and archived the prior research. |
| 2026-11-12 14:57 | [Continuity smoke test](runs/2026-11-12-smoke/) | ⚙️ setup | — | The prior local runner still compiles and runs on Windows with GCC 16.1 and sorts 1,000 uint32 keys correctly. Not an evaluation of the goal. |
<!-- RUNS:END -->
