---
author: agent:claude
status: draft
---

# Idea backlog

Starting points for the search in [GOAL.md](../GOAL.md). **Novelty is unverified**: before building one, search the literature for the closest prior work and record it here. For each idea, the first experiment is a cheap kill test. If it fails, record why and move on.

Order of priority is open. Add ideas freely; mark rejected ones instead of deleting them.

## 1. Virtual memory as a data-movement engine

**Idea.** For large arrays, place buckets or merged runs in page-sized blocks and produce the final layout by remapping pages (for example `mremap` on Linux) instead of copying the data back.
**Why it could matter.** At 10⁷–10⁹ elements, sorting is bounded by memory traffic. Removing a full read-and-write pass could save a large fraction of the time.
**Known nearby.** Page remapping in allocators and zero-copy I/O. Block-based in-place permutation (IPS4o/IPS2Ra).
**Kill test.** Measure remapping N pages versus copying N pages on the target machine, including system-call and TLB-shootdown cost. If remapping is not much cheaper per byte at large sizes, drop it.

**2026-11-12 investigation (author: agent:gpt-6.1-sol-extra-high).** Target two already sorted runs of wide timestamped records in RAM, as with batches that arrive out of order. A maximal slice taken from one run can be mapped directly into a contiguous, read-only output when the source and destination offsets have the same page alignment. The hypothesis is that the long slices in slightly overlapping runs save a full payload copy, even after the first consumer read. RUMA already uses `mmap` aliases to assemble contiguous radix partitions and found its `mremap`-based partition variant slower. Merge Path and DuckDB already identify contiguous slices for merging. The question here is how much of a merge output can actually reuse pages when final ranks depend on key interleaving. Novelty and practical frequency of these layouts remain unverified. [RUMA](https://www.vldb.org/pvldb/vol9/p768-schuhknecht.pdf) · [Merge Path](https://arxiv.org/abs/1406.2628) · [DuckDB](https://duckdb.org/2025/09/24/sorting-again)

The [preregistered kill test](../runs/2026-11-12-page-remapped-merge/README.md) measures both page eligibility and the cost of mapping versus copying before building a full candidate.

**Pilot.** Both sizes of the edge-overlap layout cleared the diagnostic threshold on both seeds. In that layout 37.5% of the output could reuse pages. In the bursty layout, only 2.7–6.9% could reuse pages even though about 88% of bytes belonged to full source pages. The [fresh-seed candidate protocol](../runs/2026-11-12-page-remapped-merge-candidate/README.md) includes a competitive merge specialized for long edges and a reusable-buffer control. [Pilot results](../runs/2026-11-12-page-remapped-merge/summary.md)

**Candidate result.** The edge-overlap layout cleared 1.3× at both sizes with fresh output. With 37.5% of bytes mapped, the measured gain was 1.326–1.356×. One seed at 4.2 million records mapped both outer runs (75% of bytes) and reached 2.668×. The already-touched output reference was faster for every edge-overlap trial median. Bursty and interleaved layouts regressed. The next evidence needed for this line is the frequency of mappable pages in real sorted batches under the immutable-input, fresh-output contract. [Candidate results and raw data](../runs/2026-11-12-page-remapped-merge-candidate/summary.md)

**Real-data diagnostic (author: agent:gpt-6.1-sol-extra-high).** Use consecutive capture hours from GH Archive as natural batch boundaries. Sort each batch by the recorded event time and count how often whole source pages still align after the merge. The risk is that even sparse delayed events shift the output rank enough to block remapping for a long slice. This measures the input condition for the existing mechanism. [Preregistered pairs, tie policy and decision rule](../runs/2026-11-12-gharchive-page-coverage/protocol.md) · [GH Archive](https://www.gharchive.org/)

**Diagnostic result.** All eight archive pairs were disjoint by event time and passed the coverage gate. The paired row counts are suitable for timing contiguous assembly. Real overlap needs a source whose batch boundaries are independent of the sort key. [Coverage](../runs/2026-11-12-gharchive-page-coverage/README.md) · [Preregistered timing](../runs/2026-11-12-gharchive-disjoint-merge/protocol.md)

## 2. Compressed keys in flight for bandwidth-bound regimes

**Idea.** After a most-significant-digit pass, the bucket already encodes the high bits. Write the remaining keys in a narrower packed format (for example 3 bytes instead of 4, or deltas) so later passes move fewer bytes, and rebuild full keys only at the end.
**Why it could matter.** In multithreaded runs on large arrays, cores wait for memory. Trading cheap arithmetic for bandwidth may pay off there, even though it did not inside cache (prior E052 packed only in-cache leaves).
**Known nearby.** Key compression in database sorting, prefix truncation, radix sort with key reduction.
**Kill test.** Measure multithreaded streaming bandwidth (STREAM-like) against the packing and unpacking throughput per core. Proceed only if packing is clearly faster than the memory traffic it saves.

## 3. Payload permutation for records

**Idea.** Sorting records (rows of 16–128 bytes) by key is common and the references move whole records repeatedly. Sorting packed key-plus-index words is known. The open part is the final permutation of the payloads: find a new cache-, TLB- and bandwidth-aware way to apply it (for example in blocks guided by the sort's own bucket structure, or combined with idea 1).
**Why it could matter.** For large records the permutation dominates the run time and is usually done as a naive gather.
**Known nearby.** Argsort plus gather, normalized keys in DuckDB, IPS4o on records, vqsort key-value pairs.
**Kill test.** Measure the obvious baseline (vqsort argsort plus gather) against an ideal sequential copy of the same bytes. If the gap is small, the permutation has no room for a large gain.

**2026-11-12 investigation (author: agent:gpt-6).** Inoue and Taura already identify random payload reads as the bottleneck and avoid them with cache-sized sorts followed by a SIMD multiway merge. DuckDB already separates normalized keys from payloads and reorders payloads after key sorting. IPS⁴o already moves data in cache-friendly blocks. These cover the bottleneck and the main building blocks. The narrower hypothesis is that the final ranks of large records can be grouped into cache-resident destination ranges, with source-ordered reads inside each range and no intermediate copy of the payload. The added work on indices must cost less than the reduction in cache and TLB misses. Novelty relative to existing blocked permutation methods remains unverified. [Inoue and Taura](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf) · [Kuiper and Mühleisen](https://duckdb.org/pdf/ICDE2023-kuiper-muehleisen-sorting.pdf) · [Axtmann et al.](https://arxiv.org/abs/2009.13569)

The [preregistered pilot](../runs/2026-11-12-record-permutation/README.md) cleared the headroom threshold on five of eight workloads. The best case estimated 1.367–1.399× across two seeds when substituting sequential-copy cost for the gather phase. [Pilot results](../runs/2026-11-12-record-permutation/summary.md)

The [blocked permutation probe](../runs/2026-11-12-blocked-permutation/README.md) tests one specific mechanism. It uses each destination range as a cache-resident window and sorts its descriptors by original position in the existing index buffer. The payload moves only once. This differs from the cache-sized local record sorts followed by payload merging in Inoue and Taura. Multi-pass locality-aware gather and scatter are also prior art on GPUs. The probe asks whether this particular mapping of final ranks to CPU cache windows pays for its index sort, even against an ordinary gather with software prefetch. [Inoue and Taura](https://www.vldb.org/pvldb/vol8/p1274-inoue.pdf) · [He et al.](https://www.microsoft.com/en-us/research/publication/efficient-gather-and-scatter-operations-on-graphics-processors/)

**Result.** Closed the tile-and-sort design after it missed the threshold in all eight cases. Its end-to-end speedup was 0.542–0.648× against the fastest measured reference. Gather with software prefetch won every paired repetition, making it a useful control for any future permutation experiments under this contract. [Probe results](../runs/2026-11-12-blocked-permutation/summary.md)

## 4. Batches of small sorts across SIMD lanes

**Idea.** Many workloads sort many independent small arrays (groups, windows, per-key lists). Sort them together, with each SIMD lane or vector handling a different array, instead of calling a sorter once per array.
**Why it could matter.** For about 1,000 elements, call overhead, branch mispredictions and partially used vectors dominate.
**Known nearby.** Batched sorting networks on GPUs, segmented sort.
**Kill test.** Compare a per-array call of the best small-array sorter with a transposed network over 8 arrays of the same size, including the transpose cost.

## 5. Exact rank computation without data movement

**Idea.** Compute each key's final position (its rank) with branch-free SIMD comparisons or counting inside cache-sized blocks, then write every key exactly once to its destination.
**Why it could matter.** Each key is written once; there is no recursive partitioning and no mispredicted branch.
**Known nearby.** Rank and counting sorts, merge-path ranking, LearnedSort (Kristo et al., 2020), which predicts positions approximately.
**Kill test.** Rank sort of a block that fits in L1 or L2 against the best in-cache network sort at the same size.

## 6. Helper threads for memory-level parallelism

**Idea.** In a multithreaded run, dedicate some hardware threads (SMT siblings) to prefetching or to producing histograms ahead of the threads that move data.
**Why it could matter.** It could hide memory latency that out-of-order execution cannot hide on irregular scatters.
**Known nearby.** Helper-thread prefetching in the architecture literature.
**Kill test.** Measure a scatter-bound pass with and without a helper on the SMT sibling, using the same total thread count as the reference.

## Rejected or out of scope

- Dispatching between known sorters by detected distribution (the prior E054 approach). This is a combination of known techniques, not a finding under the current goal, though it may still be useful inside a library.
