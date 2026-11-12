# Progress

A living summary of what has been tried and what was learned, written for people. The detailed, agent-oriented state is in [notes/agent-brief.md](notes/agent-brief.md). The final summary will go in [SUMMARY.md](SUMMARY.md) when the project closes.

_Last updated: 2026-11-12._

## Where we are

Two ideas have been tested since the goal was reset on 12 November 2026. The blocked record permutation was ruled out. Page remapping showed a gain in a specific synthetic workload. Practical relevance and novelty still need evidence under the [research goal](GOAL.md).

## What works so far

**Merging sorted batches by remapping memory pages (promising).** Merging two already-sorted batches of large records usually means copying every byte into a new output. When long stretches of an input already sit at the right place relative to a page boundary, the program can ask the operating system to show those pages in the output instead of copying them. For synthetic batches that overlap at their edges, the speedup over the best merge into a new output was 1.33–1.36× when 37.5% of the output was reused. One seed reached 2.67× by reusing 75%. [Measured results and raw data](runs/2026-11-12-page-remapped-merge-candidate/summary.md)

The caveats matter:

- With a reusable output buffer already in memory, an ordinary merge was faster in all four edge-overlap comparisons. The remapping method took about 1.4–2.7× as long.
- Bursty and closely interleaved batches let the prototype reuse few or zero pages. It took 16–22% longer than the best fresh-output reference on those layouts.
- The tests used synthetic data and one thread on a Ryzen 7 5800X under WSL2. How often real data (logs, time series) has this shape is still unknown.

## What does not work

- **Reordering large records in cache-sized tiles.** Sorting the keys and then writing records in tiles took 54–85% longer overall than the fastest measured reference. The combined cost of planning and moving records erased the estimated gain. A gather that asks the CPU to fetch upcoming records early (software prefetch) won all 48 paired repetitions. [Measured results and raw data](runs/2026-11-12-blocked-permutation/summary.md)
- **Patching the fastest existing sorter for random numbers** (prior research). Eighteen attempts to replace a single phase of vqsort for random 32-bit numbers all fell short. See [prior research](notes/prior-research.md).

## What comes next

- Measure how many bytes in real sorted batches are eligible for remapping. This depends on both the lengths of the contiguous slices and how they line up in the merged output. [Candidate contract and reproduction](runs/2026-11-12-page-remapped-merge-candidate/README.md)
- Test other ideas from the [backlog](notes/ideas.md): compressed keys for large arrays, sorting many small arrays together, rank computation and helper threads.

## All experiments

Generated from the run logs by `scripts/build_progress.py`. Newest first.

<!-- RUNS:START -->
6 runs: 1 promising, 1 failed, 2 diagnostic, 2 setup.

| Date | Run | Verdict | Result | What we learned |
|---|---|---|---|---|
| 2026-11-12 17:33 | [Page-remapped merge candidate](runs/2026-11-12-page-remapped-merge-candidate/) | 🟡 promising | 1.326–2.668× on edge-overlap runs (2/4 cases ≥1.3×, 0/4 ≥1.5× on both seeds) | Mapping aligned input pages into the output beat the best fresh-output merge of two sorted runs of 128-byte records by 1.33–1.36×, and by 2.67× when 75% of the output was mapped. It lost to a merge into an already-touched buffer (0.36–0.74×) and regressed on bursty and interleaved runs (0.82–0.86×). Synthetic data only. |
| 2026-11-12 17:21 | [Page-remapped merge pilot](runs/2026-11-12-page-remapped-merge/) | 🔎 diagnostic | 1.52–1.59× estimated for edge overlap; at most 1.08× for bursty runs | Mapping pages instead of copying them pays off from 64 KiB extents upwards (4 KiB extents lose). In a merge only page-aligned slices qualify, which was 37.5% of the output when two runs overlap at the edges and 3–7% for bursty runs. |
| 2026-11-12 16:48 | [Blocked record permutation probe](runs/2026-11-12-blocked-permutation/) | ❌ failed | 0.542–0.648× (0/8 cases ≥1.3×) | Rewriting and sorting descriptors and then moving the records in cache-sized tiles took 1.67–2.14× as long as the original gather phase. The probe measured those costs together. Gather with software prefetch won all 48 paired repetitions. |
| 2026-11-12 16:06 | [Record permutation headroom pilot](runs/2026-11-12-record-permutation/) | 🔎 diagnostic | 1.29–1.40× estimated headroom; 5/8 cases ≥1.3× on both seeds | Gathering the payload takes 51–68% of an indirect sort of 64- and 128-byte records, so a permutation as cheap as a sequential copy would give about 1.3–1.4×. Enough room to try a candidate, with little margin. |
| 2026-11-12 15:37 | [Viability review and repository reset](runs/2026-11-12-repo-reset/) | ⚙️ setup | — | Judged the original goal (25% faster in 90% of a large benchmark matrix) very unlikely to be reached, replaced it with an open search for new mechanisms and archived the prior research. |
| 2026-11-12 14:57 | [Continuity smoke test](runs/2026-11-12-smoke/) | ⚙️ setup | — | The prior local runner still compiles and runs on Windows with GCC 16.1 and sorts 1,000 uint32 keys correctly. Not an evaluation of the goal. |
<!-- RUNS:END -->
