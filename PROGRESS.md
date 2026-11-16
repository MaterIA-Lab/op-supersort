# Progress

A living summary of what has been tried and what was learned, written for people. The detailed, agent-oriented state is in [notes/agent-brief.md](notes/agent-brief.md). The final summary will go in [SUMMARY.md](SUMMARY.md) when the project closes.

_Last updated: 2026-11-16._

## Where we are

Page remapping on Linux remains promising when sorted batches already have shareable pages. In a fuller test on two Linux machines, producing both batches and their merged view by adjusting page placement sped up the operation by 1.23–1.28× at 128 and 256 MiB with 2% overlap. The eight fresh cases fell below the 1.30× research target. [Research goal](GOAL.md) · [Linux producer benchmark](runs/2026-11-16-linux-producer-placement/README.md)

## What works so far

**Merging sorted batches by remapping memory pages (promising).** Merging two already-sorted batches of large records usually means copying every byte into a new output. When long stretches of an input already sit at the right place relative to a page boundary, the program can ask the operating system to show those pages in the output instead of copying them. For synthetic batches that overlap at their edges, the speedup over the best merge into a new output was 1.33–1.36× when 37.5% of the output was reused. One seed reached 2.67× by reusing 75%. [Measured results and raw data](runs/2026-11-12-page-remapped-merge-candidate/summary.md)

The caveats matter:

- With a reusable output buffer already in memory, an ordinary merge was faster in all four edge-overlap comparisons. The remapping method took about 1.4–2.7× as long.
- Bursty and closely interleaved batches let the prototype reuse few or zero pages. It took 16–22% longer than the best fresh-output reference on those layouts.
- The overlapping tests used synthetic data and one thread on a Ryzen 7 5800X under WSL2. Eight pairs of public GitHub event batches had disjoint time ranges. [Archive coverage diagnostic](runs/2026-11-12-gharchive-page-coverage/README.md)

**Assembling disjoint archive batches.** With real batch sizes and synthetic record payloads, remapping was at least 1.5× faster than copying into a new output in seven of eight cases. With an already-resident buffer, remapping cleared 1.5× in the two cases where nearly every page lined up. This measures assembly of two already-ordered ranges. [Measured results](runs/2026-11-12-gharchive-disjoint-merge/summary.md)

## What does not work

- **Producing both batches with new Linux mappings.** The shifted layout reused about 98% of the fused output. Building the two batches took 80–84% of the total time. Setting up pages early saved time in the first read, with at most a 2.2 ms reduction in the total. Every fresh case missed the speed target. [Linux producer benchmark](runs/2026-11-16-linux-producer-placement/README.md)
- **Shifting each input's starting position in a Windows producer.** With 2% overlap, choosing offsets doubled the fraction of bytes eligible for reuse. Producing both batches and the merged view still took 1.84–2.43 times as long as copying directly, including the first read. [Producer benchmark](runs/2026-11-16-producer-page-placement/README.md)
- **Reusing whole pages when records from both sources alternate frequently.** More than 99% of the rows in each monthly airport pair fell within the common time range. The longest stretch from one input was 17 rows. It takes 32 rows to fill one page at 128 bytes per row. [Flight coverage diagnostic](runs/2026-11-16-flight-overlap/README.md)
- **Compressing four-byte keys to three bytes between passes.** With eight workers and two intermediate memory transfers, the estimated gain after compression and reconstruction was 1.09–1.18×. The screen used sequential copying and missed the 1.30× gate in all four cases. [Bandwidth screen](runs/2026-11-15-compressed-key-bandwidth/README.md)
- **Dedicating one of two hardware threads to prefetch records.** On two permutations of 256 MiB, the best helper took 180–182 ms. Splitting the copy across the same two threads took 102–114 ms. [Helper-thread benchmark](runs/2026-11-15-smt-gather-helper/README.md)
- **Reordering large records in cache-sized tiles.** Sorting the keys and then writing records in tiles took 54–85% longer overall than the fastest measured reference. The combined cost of planning and moving records erased the estimated gain. A gather that asks the CPU to fetch upcoming records early (software prefetch) won all 48 paired repetitions. [Measured results and raw data](runs/2026-11-12-blocked-permutation/summary.md)
- **Grouping source reads without sorting the index inside each tile.** The cheaper grouping approach still took about 23% longer than the best measured read-ahead reference on 8.4 million 16-byte rows. [Windows record benchmark](runs/2026-11-14-record-permutation/README.md)
- **Remapping on Windows with a reusable copy buffer available.** For blocks of 64 KiB, mapping and a first read took 95–112 ms. Streaming copy and a first read took 43–44 ms. First access through the mapped addresses also erased the advantage of sub-millisecond setup with 2 MiB blocks. [Windows remapping benchmark](runs/2026-11-14-page-remap/README.md)
- **Computing ranks in registers for groups of four.** The rank method took 5–37% longer than the fastest direct AVX2 references on the primary batches. [Stable four-record benchmark](runs/2026-11-14-four-row-ranks/README.md)
- **Patching the fastest existing sorter for random numbers** (prior research). Eighteen attempts to replace a single phase of vqsort for random 32-bit numbers all fell short. See [prior research](notes/prior-research.md).

## What comes next

- For page remapping, look for an actual workflow that already writes its sorted batches into shareable pages. The airport traces provide realistic overlapping layouts to screen for such a workflow. [Flight coverage diagnostic](runs/2026-11-16-flight-overlap/README.md)
- Test other mechanisms that can remove a full memory pass or move a working set into cache. Any further small-batch work should be compared with a direct SIMD network. [Idea backlog](notes/ideas.md)

## All experiments

Generated from the run logs by `scripts/build_progress.py`. Newest first.

<!-- RUNS:START -->
17 runs: 2 promising, 7 failed, 6 diagnostic, 2 setup.

| Date | Run | Verdict | Result | What we learned |
|---|---|---|---|---|
| 2026-11-16 15:15 | [Producing two batches and their merged view on Linux](runs/2026-11-16-linux-producer-placement/) | ❌ failed | 1.231–1.280× on the eight holdout cases, with 0/8 meeting the 77% time limit | Adjusted page placement was 1.231–1.280× as fast as the best direct writer across eight fresh edge-overlap cases on two Linux runners. Every case missed the 1.30× target, and building the two batches took 80–84% of the remapping time. |
| 2026-11-16 13:34 | [Placing both batches for page reuse during a stable merge](runs/2026-11-16-producer-page-placement/) | ❌ failed | 0.412–0.543× against the fastest direct method | With 2% overlap, independent placement doubled reusable coverage from 49% to about 98%. The Windows implementation took 1.84–2.43 times as long as the best direct reference when producing both batches and the merged result. |
| 2026-11-16 13:02 | [Page reuse when real flight batches overlap](runs/2026-11-16-flight-overlap/) | 🔎 diagnostic | 0 eligible pages in 36 heavily interleaved pairs | The 36 monthly airport pairs had more than 99% of rows in the shared time interval. Even the longest single-source stretch was shorter than one page. Selecting each input's alignment nearly doubled median reusable coverage for lightly overlapping weekly batches. |
| 2026-11-15 15:26 | [Helper-thread prefetch for scattered records](runs/2026-11-15-smt-gather-helper/) | ❌ failed | 0.564–0.629× against the fastest split gather | The best helper took 180–182 ms on two threads of one core. Giving each thread half the output took 102–114 ms for the same 256 MiB permutation. |
| 2026-11-15 15:16 | [Bandwidth screen for three-byte sorting keys](runs/2026-11-15-compressed-key-bandwidth/) | 🔎 diagnostic | 1.086–1.178× estimated across four primary cases | With eight workers, a transfer-only estimate including conversion reached 1.086–1.178×. All four primary cases missed the 1.30× gate before any sorting work was charged. |
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
