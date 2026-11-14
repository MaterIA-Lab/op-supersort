# Progress

A living summary of what has been tried and what was learned, written for people. The detailed, agent-oriented state is in [notes/agent-brief.md](notes/agent-brief.md). The final summary will go in [SUMMARY.md](SUMMARY.md) when the project closes.

_Last updated: 2026-11-14._

## Where we are

Page remapping on Linux remains promising when sorted ranges line up with the output pages. Recent tests ruled out three specific Windows or AVX2 implementations. A small sample of real taxi trips produced almost disjoint batches, leaving the performance of remapping on substantially overlapping data open under the [research goal](GOAL.md).

## What works so far

**Merging sorted batches by remapping memory pages (promising).** Merging two already-sorted batches of large records usually means copying every byte into a new output. When long stretches of an input already sit at the right place relative to a page boundary, the program can ask the operating system to show those pages in the output instead of copying them. For synthetic batches that overlap at their edges, the speedup over the best merge into a new output was 1.33–1.36× when 37.5% of the output was reused. One seed reached 2.67× by reusing 75%. [Measured results and raw data](runs/2026-11-12-page-remapped-merge-candidate/summary.md)

The caveats matter:

- With a reusable output buffer already in memory, an ordinary merge was faster in all four edge-overlap comparisons. The remapping method took about 1.4–2.7× as long.
- Bursty and closely interleaved batches let the prototype reuse few or zero pages. It took 16–22% longer than the best fresh-output reference on those layouts.
- The overlapping tests used synthetic data and one thread on a Ryzen 7 5800X under WSL2. Eight pairs of public GitHub event batches had disjoint time ranges. [Archive coverage diagnostic](runs/2026-11-12-gharchive-page-coverage/README.md)

**Assembling disjoint archive batches.** With real batch sizes and synthetic record payloads, remapping was at least 1.5× faster than copying into a new output in seven of eight cases. With an already-resident buffer, remapping cleared 1.5× in the two cases where nearly every page lined up. This measures assembly of two already-ordered ranges. [Measured results](runs/2026-11-12-gharchive-disjoint-merge/summary.md)

## What does not work

- **Reordering large records in cache-sized tiles.** Sorting the keys and then writing records in tiles took 54–85% longer overall than the fastest measured reference. The combined cost of planning and moving records erased the estimated gain. A gather that asks the CPU to fetch upcoming records early (software prefetch) won all 48 paired repetitions. [Measured results and raw data](runs/2026-11-12-blocked-permutation/summary.md)
- **Grouping source reads without sorting the index inside each tile.** The cheaper grouping approach still took about 23% longer than the best measured read-ahead reference on 8.4 million 16-byte rows. [Windows record benchmark](runs/2026-11-14-record-permutation/README.md)
- **Remapping on Windows with a reusable copy buffer available.** For blocks of 64 KiB, mapping and a first read took 95–112 ms. Streaming copy and a first read took 43–44 ms. First access through the mapped addresses also erased the advantage of sub-millisecond setup with 2 MiB blocks. [Windows remapping benchmark](runs/2026-11-14-page-remap/README.md)
- **Computing ranks in registers for groups of four.** The rank method took 5–37% longer than the fastest direct AVX2 references on the primary batches. [Stable four-record benchmark](runs/2026-11-14-four-row-ranks/README.md)
- **Patching the fastest existing sorter for random numbers** (prior research). Eighteen attempts to replace a single phase of vqsort for random 32-bit numbers all fell short. See [prior research](notes/prior-research.md).

## What comes next

- Screen a denser source with distinct batch and event clocks. The 6,433-trip taxi sample had one overlapping weekly pair, with only four rows in the overlap. Selecting a different page offset did not improve page reuse for that pair. [Taxi batch diagnostic](runs/2026-11-14-taxi-page-coverage/README.md)
- Measure the remaining early tests from the [backlog](notes/ideas.md), including compressed keys for bandwidth-limited arrays and helper threads. Any further small-batch work should be compared with a direct SIMD network.

## All experiments

Generated from the run logs by `scripts/build_progress.py`. Newest first.

<!-- RUNS:START -->
12 runs: 2 promising, 4 failed, 4 diagnostic, 2 setup.

| Date | Run | Verdict | Result | What we learned |
|---|---|---|---|---|
| 2026-11-14 16:11 | [Page reuse in completed taxi-trip batches](runs/2026-11-14-taxi-page-coverage/) | 🔎 diagnostic | 1/12 weekly pairs overlapped and 0/12 put at least 5% of rows in the overlap | Only one of twelve weekly pairs overlapped in pickup time. Four rows of that pair fell inside the overlap, and choosing the output offset did not increase its page reuse. |
| 2026-11-14 15:57 | [Stable rank inversion for four-record groups](runs/2026-11-14-four-row-ranks/) | ❌ failed | 0.731–0.952× across two primary seeds | Computing ranks and inverting them in AVX2 registers took 5–37% longer than the fastest direct SIMD reference on the primary batches. The extra work still cost time in the cache-resident control. |
| 2026-11-14 15:45 | [Windows page remapping and first read](runs/2026-11-14-page-remap/) | ❌ failed | 0.394–0.453× across two primary seeds | For 64 KiB blocks, Windows remapping and a first read took 2.21–2.54× the time of streaming copy and a first read. The first access to the new virtual addresses dominated even when larger blocks made the remap calls fast. |
| 2026-11-14 15:37 | [Record permutation by source band](runs/2026-11-14-record-permutation/) | ❌ failed | 0.814× across two primary seeds | Grouping reads by source band took about 23% longer on the primary batch. Preparing the groups and moving rows together took longer than reading ahead in the original layout. |
| 2026-11-12 18:34 | [Page remapping on GH Archive batch sizes](runs/2026-11-12-gharchive-disjoint-merge/) | 🟡 promising | 1.431–7.252× fresh (7/8 ≥1.5×); 2/8 resident ≥1.5× | On eight disjoint pairs with batch sizes and order derived from GH Archive, remapping beat every fresh-output reference. It beat the resident-buffer references in the two cases where almost all pages could be mapped. Real overlapping arrivals remain untested. |
| 2026-11-12 18:25 | [GH Archive page coverage](runs/2026-11-12-gharchive-page-coverage/) | 🔎 diagnostic | 8/8 pairs passed 37.5% coverage; 0/8 had timestamp overlap | All eight registered archive pairs had disjoint event-time ranges. Between 48.25% and nearly 100% of the modeled bytes can be remapped, so these inputs measure assembly of preordered ranges and leave overlap untested. |
| 2026-11-12 17:33 | [Page-remapped merge candidate](runs/2026-11-12-page-remapped-merge-candidate/) | 🟡 promising | 1.326–2.668× on edge-overlap runs (2/4 cases ≥1.3×, 0/4 ≥1.5× on both seeds) | Mapping aligned input pages into the output beat the best fresh-output merge of two sorted runs of 128-byte records by 1.33–1.36×, and by 2.67× when 75% of the output was mapped. It lost to a merge into an already-touched buffer (0.36–0.74×) and regressed on bursty and interleaved runs (0.82–0.86×). Synthetic data only. |
| 2026-11-12 17:21 | [Page-remapped merge pilot](runs/2026-11-12-page-remapped-merge/) | 🔎 diagnostic | 1.52–1.59× estimated for edge overlap; at most 1.08× for bursty runs | Mapping pages instead of copying them pays off from 64 KiB extents upwards (4 KiB extents lose). In a merge only page-aligned slices qualify, which was 37.5% of the output when two runs overlap at the edges and 3–7% for bursty runs. |
| 2026-11-12 16:48 | [Blocked record permutation probe](runs/2026-11-12-blocked-permutation/) | ❌ failed | 0.542–0.648× (0/8 cases ≥1.3×) | Rewriting and sorting descriptors and then moving the records in cache-sized tiles took 1.67–2.14× as long as the original gather phase. The probe measured those costs together. Gather with software prefetch won all 48 paired repetitions. |
| 2026-11-12 16:06 | [Record permutation headroom pilot](runs/2026-11-12-record-permutation/) | 🔎 diagnostic | 1.29–1.40× estimated headroom; 5/8 cases ≥1.3× on both seeds | Gathering the payload takes 51–68% of an indirect sort of 64- and 128-byte records, so a permutation as cheap as a sequential copy would give about 1.3–1.4×. Enough room to try a candidate, with little margin. |
| 2026-11-12 15:37 | [Viability review and repository reset](runs/2026-11-12-repo-reset/) | ⚙️ setup | — | Judged the original goal (25% faster in 90% of a large benchmark matrix) very unlikely to be reached, replaced it with an open search for new mechanisms and archived the prior research. |
| 2026-11-12 14:57 | [Continuity smoke test](runs/2026-11-12-smoke/) | ⚙️ setup | — | The prior local runner still compiles and runs on Windows with GCC 16.1 and sorts 1,000 uint32 keys correctly. Not an evaluation of the goal. |
<!-- RUNS:END -->
